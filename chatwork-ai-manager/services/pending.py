"""claudeの詰まり中に受けた依頼を捨てずに預かり、復旧後に自動で処理し切る（Stage 8）。

2026-08-19 の障害では、LINEへ投げた依頼が3回とも**黙って消えた**（dev_tasks にも
tasks にも残らず、13分後に「ClaudeError」とだけ返ってきた）。同じ依頼を人が
投げ直すしかなく、取りこぼしにも気づけない状態だった。

ここが預かるのは「**AIがまだ答えていない質問**」だけ。
業務TODO（tasks）や開発タスク（dev_tasks）とは別物なので混ぜない。

流れ:
  受信 → claudeが詰まっている → enqueue()（＋利用者には「復旧後に自動で処理します」と返す）
                                      ↓
  worker のループ → drain() → qa.answer() → 依頼元（LINE push / Chatwork）へ結果を届ける
"""
from db.connection import get_conn, query, query_one

MAX_ATTEMPTS = 3        # これを超えたら failed にして人に知らせる（無限に叩き続けない）
DRAIN_BATCH = 3         # 1周で流す本数。復旧直後に一気に走らせて枠を食い潰さないため


def enqueue(question: str, channel: str, requester=None, line_user_id=None,
            room_id=None, asker_account_id=None, source_message_id=None,
            dedup_key=None) -> int:
    """依頼を預かる。同じ dedup_key が既にあれば積まない（二重回答の防止）。

    戻り値: 積んだ行の id。既にある/積めなかったときは 0。
    """
    if not (question or "").strip():
        return 0
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO pending_requests "
            "(channel, question, requester, line_user_id, room_id, asker_account_id, "
            " source_message_id, dedup_key) VALUES (?,?,?,?,?,?,?,?)",
            (channel, question, requester, line_user_id, room_id, asker_account_id,
             source_message_id, dedup_key),
        )
        return int(cur.lastrowid or 0)


def queued_count() -> int:
    row = query_one("SELECT COUNT(*) AS n FROM pending_requests WHERE status='queued'")
    return int(row["n"]) if row else 0


def queued(limit: int = 50):
    return query(
        "SELECT * FROM pending_requests WHERE status='queued' "
        "ORDER BY created_at, id LIMIT ?", (limit,))


def _finish(row_id: int, status: str, error=None):
    with get_conn() as conn:
        conn.execute(
            "UPDATE pending_requests SET status=?, last_error=?, "
            "updated_at=datetime('now','localtime'), answered_at=datetime('now','localtime') WHERE id=?",
            (status, (str(error)[:500] if error else None), row_id))


def _bump_attempt(row_id: int, error=None):
    with get_conn() as conn:
        conn.execute(
            "UPDATE pending_requests SET attempts=attempts+1, last_error=?, "
            "updated_at=datetime('now','localtime') WHERE id=?",
            ((str(error)[:500] if error else None), row_id))


def drain(limit: int = DRAIN_BATCH) -> dict:
    """預かった依頼を古い順に処理して結果を届ける。worker のループから呼ぶ。

    claude がまた詰まったら**その場で止める**（残りは次の機会に回す）。
    詰まっている最中に流そうとしても全部失敗するだけなので、無駄打ちしない。
    """
    from services import claude_health

    if claude_health.is_stalled():
        return {}
    rows = queued(limit)
    if not rows:
        return {}
    sent = failed = 0
    for row in rows:
        ok, stalled = _process_one(row)
        if stalled:
            # 復旧していなかった。残りは次回へ。
            return {"sent": sent, "failed": failed, "stalled_again": True}
        if ok:
            sent += 1
        else:
            failed += 1
    return {"sent": sent, "failed": failed}


def _process_one(row) -> tuple:
    """1件処理する。戻り値 (成功したか, 詰まりで中断したか)。"""
    from services import claude_health, qa
    from services.claude_client import ClaudeStalledError

    row_id = row["id"]
    try:
        res = qa.answer(row["question"], room_id=row["room_id"],
                        asker=row["requester"], channel=row["channel"],
                        asker_account_id=row["asker_account_id"],
                        line_user_id=row["line_user_id"])
        answer_text = (res or {}).get("answer") or ""
    except ClaudeStalledError as e:
        claude_health.mark_stalled(str(e))
        _bump_attempt(row_id, e)
        return (False, True)
    except Exception as e:
        _bump_attempt(row_id, e)
        if int(row["attempts"] or 0) + 1 >= MAX_ATTEMPTS:
            _finish(row_id, "failed", e)
            _deliver(row, f"お預かりしていたご依頼を{MAX_ATTEMPTS}回試しましたが、"
                          f"処理できませんでした。\n理由: {type(e).__name__}: {e}\n\n"
                          f"お手数ですが、内容を変えて送り直してください。\n"
                          f"― 元のご依頼 ―\n{row['question'][:300]}")
        return (False, False)

    claude_health.note_success()
    ok = _deliver(row, "お預かりしていたご依頼の結果です。\n\n" + answer_text)
    _finish(row_id, "done" if ok else "failed", None if ok else "送信に失敗")
    return (ok, False)


def _deliver(row, text: str) -> bool:
    """依頼が来た入口へ返す（LINEはpush・Chatworkはoutbox経由）。"""
    from services import line_client, outbox, settings
    from services.chatwork import ChatworkClient, mention

    prefix = settings.get_setting("ai_prefix", "🤖AI業務マネージャー")
    if row["channel"] == "line":
        if not row["line_user_id"]:
            return False
        return line_client.push(row["line_user_id"], f"{prefix}\n\n{text}", label="pending_deliver")
    if row["channel"] == "chatwork":
        if not row["room_id"]:
            return False
        to = ""
        if row["asker_account_id"]:
            to = mention(int(row["asker_account_id"]), row["requester"]) + "\n"
        ob_id = outbox.enqueue(
            row["room_id"], f"{to}{prefix}\n\n{text}", kind="qa_reply",
            reason="詰まり中に預かった依頼への回答",
            to_account_ids=(str(row["asker_account_id"]) if row["asker_account_id"] else None),
            related_message_id=row["source_message_id"],
            dedup_key=f"pending:{row['id']}")
        if not ob_id:
            return False
        try:
            return bool(outbox.send_one(ChatworkClient(), ob_id).get("ok"))
        except Exception:
            return False
    return False
