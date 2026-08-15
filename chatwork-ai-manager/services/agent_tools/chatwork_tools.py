"""Chatwork Tool。既存 messages テーブル / chatwork.py / outbox.py を再利用。

- chatwork_search / get_messages はローカルDB（workerが常時ポーリング保存）を参照。
- chatwork_post_message は outbox 経由（post_mode により自動送信/確認待ち）。AI投稿と分かる接頭辞を付与。
"""
from db.connection import query
from services import outbox, settings


def _msg(m):
    return {"message_id": m["message_id"], "room_id": m["room_id"],
            "from": m["account_name"] or m["account_id"], "account_id": m["account_id"],
            "body": m["body"], "send_time": m["send_time"]}


def chatwork_search(keyword, room_id=None, limit=20):
    if not keyword:
        return {"ok": False, "error": "keyword が必要です"}
    sql = "SELECT * FROM messages WHERE body LIKE ?"
    params = [f"%{keyword}%"]
    if room_id:
        sql += " AND room_id=?"; params.append(room_id)
    sql += " ORDER BY send_time DESC, message_id DESC LIMIT ?"; params.append(limit)
    rows = query(sql, tuple(params))
    return {"ok": True, "count": len(rows), "messages": [_msg(m) for m in rows]}


def chatwork_get_messages(room_id, limit=30):
    rows = query(
        "SELECT * FROM messages WHERE room_id=? ORDER BY send_time DESC, message_id DESC LIMIT ?",
        (room_id, limit),
    )
    rows = list(reversed(rows))
    return {"ok": True, "count": len(rows), "messages": [_msg(m) for m in rows]}


def chatwork_post_message(room_id, body, reason=None, kind="agent_post",
                          to_account_ids=None, related_task_id=None,
                          dedup_key=None, force=False):
    if not room_id or not body:
        return {"ok": False, "error": "room_id と body が必要です"}
    prefix = settings.get_setting("ai_prefix", "🤖AI業務マネージャー")
    if prefix and prefix not in body:
        body = f"{prefix}\n\n{body}"
    ob_id = outbox.enqueue(room_id, body, kind=kind, reason=reason,
                           to_account_ids=to_account_ids, related_task_id=related_task_id,
                           dedup_key=dedup_key)
    if not ob_id:
        return {"ok": True, "queued": False, "note": "重複のためスキップ"}
    mode = settings.post_mode()
    should_send = force or outbox._should_auto_send(mode, kind)
    if should_send:
        from services.chatwork import ChatworkClient
        res = outbox.send_one(ChatworkClient(), ob_id)
        if res.get("ok"):
            return {"ok": True, "sent": True, "outbox_id": ob_id, "message_id": res.get("message_id")}
        return {"ok": False, "sent": False, "outbox_id": ob_id, "error": res.get("reason")}
    return {"ok": True, "sent": False, "queued": True, "outbox_id": ob_id,
            "note": f"post_mode={mode} のため確認待ち（管理画面で承認）"}
