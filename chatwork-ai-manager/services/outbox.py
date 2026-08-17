"""AI投稿キュー（§34-35）。

すべての投稿は一旦 outbox に積み、post_mode に従って送信する:
  - confirm : 送信しない（管理画面で人が承認）
  - semi    : 定型（進捗確認・催促・Q&A返信）は自動、その他は保留
  - auto    : すべて自動送信
dedup_key(UNIQUE) で同一催促・同一メッセージへの二重投稿を防ぐ。
"""
from db.connection import get_conn, query, query_one
from services import settings

# semi モードで自動送信してよい種別（定型・低リスク）
SEMI_AUTO_KINDS = {"progress_check", "overdue", "stale", "report"}
# post_mode に関係なく常に送信してよい種別（社員の質問への直接返信・受付確認は保留しない）
# dev_report: 本人が依頼した開発タスクの進捗・完了報告（AIの自発投稿ではないため保留しない）
ALWAYS_SEND_KINDS = {"qa_reply", "ack", "dev_report"}


def enqueue(room_id, body, kind, reason=None, to_account_ids=None,
            related_task_id=None, related_message_id=None, dedup_key=None) -> int:
    """投稿を outbox に積む。dedup_key 衝突時は積まず既存 id を返す（None もあり）。"""
    mode = settings.post_mode()
    with get_conn() as conn:
        if dedup_key:
            existing = conn.execute(
                "SELECT id FROM outbox WHERE dedup_key=?", (dedup_key,)
            ).fetchone()
            if existing:
                return existing["id"]
        cur = conn.execute(
            "INSERT INTO outbox (room_id, to_account_ids, body, reason, kind, "
            "related_task_id, related_message_id, status, mode, dedup_key) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)",
            (room_id, to_account_ids, body, reason, kind, related_task_id,
             related_message_id, mode, dedup_key),
        )
        return cur.lastrowid


def has_dedup(dedup_key) -> bool:
    if not dedup_key:
        return False
    return query_one("SELECT 1 FROM outbox WHERE dedup_key=?", (dedup_key,)) is not None


def pending(limit=200):
    return query("SELECT * FROM outbox WHERE status='pending' ORDER BY id DESC LIMIT ?", (limit,))


def recent(limit=100):
    return query("SELECT * FROM outbox WHERE status!='pending' ORDER BY id DESC LIMIT ?", (limit,))


def get(outbox_id):
    return query_one("SELECT * FROM outbox WHERE id=?", (outbox_id,))


def update_body(outbox_id, body):
    with get_conn() as conn:
        conn.execute("UPDATE outbox SET body=? WHERE id=?", (body, outbox_id))


def discard(outbox_id):
    with get_conn() as conn:
        conn.execute("UPDATE outbox SET status='discarded' WHERE id=?", (outbox_id,))


def send_one(client, outbox_id) -> dict:
    """1 件を実際に Chatwork へ投稿。結果を outbox に反映。"""
    row = get(outbox_id)
    if not row or row["status"] == "sent":
        return {"ok": False, "reason": "not-pending"}
    try:
        mid = client.post_message(row["room_id"], row["body"])
        with get_conn() as conn:
            conn.execute(
                "UPDATE outbox SET status='sent', chatwork_message_id=?, sent_at=datetime('now') WHERE id=?",
                (mid, outbox_id),
            )
        return {"ok": True, "message_id": mid}
    except Exception as e:
        with get_conn() as conn:
            conn.execute("UPDATE outbox SET status='failed', error=? WHERE id=?",
                         (f"{type(e).__name__}: {e}", outbox_id))
        return {"ok": False, "reason": str(e)}


def _should_auto_send(mode, kind) -> bool:
    if kind in ALWAYS_SEND_KINDS:
        return True
    if mode == "auto":
        return True
    if mode == "semi" and kind in SEMI_AUTO_KINDS:
        return True
    return False


def process_auto(client) -> int:
    """post_mode に従い、送信すべき pending を自動送信。送信件数を返す。

    qa_reply（社員の質問への直接返信）は confirm モードでも送信する。
    """
    mode = settings.post_mode()
    sent = 0
    for row in pending():
        if _should_auto_send(mode, row["kind"]):
            res = send_one(client, row["id"])
            if res.get("ok"):
                sent += 1
    return sent
