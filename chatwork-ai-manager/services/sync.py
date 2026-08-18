"""Chatwork → DB の取り込み（ルーム同期・メンバー同期・メッセージポーリング）。

worker のループからも、管理画面の「今すぐ同期」ボタンからも呼べるようにする。
冪等性: messages は PK(message_id) に INSERT OR IGNORE。二重取得しても重複行を作らない。
"""
import re

from db.connection import get_conn, query
from services import analyzer, attachments, outbox, qa, settings
from services.chatwork import ChatworkClient, mention

# Chatwork の記法タグ（[To:..] [rp ..] [qt][info] 等）を除いた質問本文を得るため
_TAG_RE = re.compile(r"\[[^\]]*\]")
# direct チャットで「質問っぽい」と判定するための手がかり
_QUESTION_HINTS = ("？", "?", "教え", "どこ", "どう", "何", "なに", "ですか", "ますか",
                   "まとめ", "調べ", "確認", "どれ", "いつ", "誰", "だれ", "いくら",
                   "とは", "方法", "手順", "次は", "漏れ")


def _strip_tags(body: str) -> str:
    return _TAG_RE.sub("", body or "").strip()


def is_ai_question(body: str, ai_account_id, room_type: str) -> bool:
    """このメッセージが AI への質問かを判定。"""
    if not body:
        return False
    low = body.lower()
    if ai_account_id is not None and f"[to:{ai_account_id}]" in low:
        return True
    if "クロード" in body or "claude" in low or "＠claude" in low:
        return True
    # AI との1対1 direct チャットでは、質問形の発言を質問とみなす
    if room_type == "direct":
        text = _strip_tags(body)
        if text and any(h in text for h in _QUESTION_HINTS):
            return True
        # ★ファイルだけを貼った場合（本文が `[download:...]` だけ）も質問として扱う。
        #   Chatworkのアップロード通知には To も「クロード」も入らないため、
        #   これが無いと **Excelを貼っても黙って無視される**（2026-08-18の指摘）。
        if attachments.chatwork_file_refs(body):
            return True
    return False


def process_questions(client, room, ai_account_id) -> int:
    """未解析メッセージのうち AI への質問を検出し、qa.answer → outbox へ返信を積む。"""
    rid = room["room_id"]
    rows = query(
        "SELECT * FROM messages WHERE room_id=? AND processed=0 ORDER BY send_time, message_id",
        (rid,),
    )
    answered = 0
    for m in rows:
        if ai_account_id is not None and m["account_id"] == ai_account_id:
            continue  # 自分（AI）の発言は対象外
        if not is_ai_question(m["body"], ai_account_id, room["type"]):
            continue
        dedup = f"qa:{m['message_id']}"
        if outbox.has_dedup(dedup):
            continue  # 既に回答済み（二重回答防止）
        question = _strip_tags(m["body"])
        # ★添付ファイル（Excel/Word/PDF/CSV…）があれば中身を読んで質問に足す。
        #   タグを剥がす前の本文から拾う（_strip_tags が [download:..] ごと消すため）
        refs = attachments.chatwork_file_refs(m["body"])
        if refs:
            question = attachments.with_attachments(
                question, attachments.read_chatwork_files(rid, refs))
        prefix = settings.get_setting("ai_prefix", "🤖AI業務マネージャー")
        to = mention(m["account_id"], m["account_name"])
        # 受付確認: エージェント処理（複数ツール反復）は数秒〜数十秒かかることがあるため、
        # ポーリングで検知した時点でまず一報する（LINEのような即レス感を出す）
        ack_dedup = f"ack:{m['message_id']}"
        if not outbox.has_dedup(ack_dedup):
            ack_body = f"{to}\n{prefix}\n\n受付けました。確認しています…"
            ack_id = outbox.enqueue(rid, ack_body, kind="ack", reason="質問受付の一次応答",
                                    to_account_ids=str(m["account_id"]),
                                    related_message_id=m["message_id"], dedup_key=ack_dedup)
            if ack_id:
                outbox.send_one(client, ack_id)
        try:
            res = qa.answer(question, room_id=rid, asker=m["account_name"],
                            asker_account_id=m["account_id"])
        except Exception as e:
            _log_error(rid, e)
            continue
        # 念のため、モデルが宛先/プレフィックスを重複生成していたら除去（本文のみにする）
        ans = re.sub(r"^\s*(?:\[To:\d+\][^\n]*\n?|🤖[^\n]*\n?)+", "", res["answer"]).strip()
        body = f"{to}\n{prefix}\n\n{ans}"
        ob_id = outbox.enqueue(rid, body, kind="qa_reply", reason="@Claudeへの質問に回答",
                               to_account_ids=str(m["account_id"]),
                               related_message_id=m["message_id"], dedup_key=dedup)
        # 質問への返信は即送信（TODO解析を待たせない＝体感速度を上げる）
        if ob_id:
            outbox.send_one(client, ob_id)
        answered += 1
    return answered


def get_ai_account_id(client: ChatworkClient):
    """トークン所有者(=AIとして振る舞うアカウント)の account_id を取得・保存。"""
    from services.settings import get_state, set_state
    cached = get_state("ai_account_id")
    if cached:
        return int(cached)
    me = client.get_me()
    aid = me.get("account_id")
    if aid is not None:
        set_state("ai_account_id", aid)
        set_state("ai_account_name", me.get("name", ""))
    return aid


def sync_rooms(client: ChatworkClient) -> int:
    """参加している全ルームを rooms テーブルへ upsert（monitored は保持）。"""
    rooms = client.get_rooms()
    with get_conn() as conn:
        for r in rooms:
            conn.execute(
                "INSERT INTO rooms (room_id, name, type, updated_at) "
                "VALUES (?, ?, ?, datetime('now')) "
                "ON CONFLICT(room_id) DO UPDATE SET name=excluded.name, type=excluded.type, "
                "updated_at=datetime('now')",
                (r.get("room_id"), r.get("name"), r.get("type")),
            )
    return len(rooms)


def sync_members_if_stale(client: ChatworkClient, room_id: int, max_age_sec: int = 3600) -> int:
    """メンバー同期は毎サイクル不要なので間引く（API節約・レイテンシ削減）。"""
    key = f"members_synced_at:{room_id}"
    last = settings.get_state(key)
    now = __import__("time").time()
    if last:
        try:
            if now - float(last) < max_age_sec:
                return -1  # スキップ
        except ValueError:
            pass
    n = sync_members(client, room_id)
    settings.set_state(key, now)
    return n


def sync_members(client: ChatworkClient, room_id: int) -> int:
    members = client.get_members(room_id)
    with get_conn() as conn:
        for m in members:
            conn.execute(
                "INSERT INTO members (room_id, account_id, name, role, updated_at) "
                "VALUES (?, ?, ?, ?, datetime('now')) "
                "ON CONFLICT(room_id, account_id) DO UPDATE SET name=excluded.name, "
                "role=excluded.role, updated_at=datetime('now')",
                (room_id, m.get("account_id"), m.get("name"), m.get("role")),
            )
    return len(members)


def poll_room(client: ChatworkClient, room_id: int) -> int:
    """1 ルームの新着を取得し messages へ保存。新規に保存した件数を返す。"""
    msgs = client.get_messages(room_id, force=True)
    if not msgs:
        return 0
    new_count = 0
    max_mid = None
    with get_conn() as conn:
        for m in msgs:
            acc = m.get("account") or {}
            cur = conn.execute(
                "INSERT OR IGNORE INTO messages "
                "(message_id, room_id, account_id, account_name, body, send_time) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (str(m.get("message_id")), room_id, acc.get("account_id"),
                 acc.get("name"), m.get("body"), m.get("send_time")),
            )
            if cur.rowcount:
                new_count += 1
            mid = str(m.get("message_id"))
            if max_mid is None or _mid_gt(mid, max_mid):
                max_mid = mid
        if max_mid is not None:
            conn.execute("UPDATE rooms SET last_message_id=? WHERE room_id=?", (max_mid, room_id))
    return new_count


def _mid_gt(a: str, b: str) -> bool:
    """Chatwork message_id は数字文字列。数値比較で大小判定。"""
    try:
        return int(a) > int(b)
    except (TypeError, ValueError):
        return str(a) > str(b)


def monitored_rooms():
    return query("SELECT * FROM rooms WHERE monitored=1 ORDER BY room_id")


def run_cycle(client: ChatworkClient, ai_account_id=None) -> dict:
    """1 サイクル: 監視ルームを同期→ポーリング→解析。サマリを返す。"""
    if ai_account_id is None:
        ai_account_id = get_ai_account_id(client)
    rooms = monitored_rooms()
    polled, created, updated, analyzed, answered = 0, 0, 0, 0, 0
    for room in rooms:
        rid = room["room_id"]
        try:
            sync_members_if_stale(client, rid)
            polled += poll_room(client, rid)
            # 質問への回答は解析より先に（analyze が processed を立てる前に未処理を見る）
            answered += process_questions(client, room, ai_account_id)
            res = analyzer.analyze_room(rid, ai_account_id)
            created += res.get("created", 0)
            updated += res.get("updated", 0)
            analyzed += res.get("analyzed", 0)
        except Exception as e:  # 1 ルームの失敗で全体を止めない
            _log_error(rid, e)
    # post_mode に従って outbox を送信（qa_reply は confirm でも送信）
    sent = 0
    try:
        sent = outbox.process_auto(client)
    except Exception as e:
        _log_error(None, e)
    return {"rooms": len(rooms), "polled": polled, "analyzed": analyzed,
            "created": created, "updated": updated, "answered": answered, "sent": sent}


def _log_error(room_id, exc):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO ai_analysis_logs (room_id, kind, error) VALUES (?, 'cycle_error', ?)",
            (room_id, f"{type(exc).__name__}: {exc}"),
        )
