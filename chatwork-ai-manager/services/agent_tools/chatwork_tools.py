"""Chatwork Tool。既存 messages テーブル / chatwork.py / outbox.py を再利用。

- chatwork_search / get_messages はローカルDB（workerが常時ポーリング保存）を参照。
- chatwork_post_message は outbox 経由（post_mode により自動送信/確認待ち）。AI投稿と分かる接頭辞を付与。
"""
import os

from db.connection import query
from services import outbox, settings


# ── 機密ルーム（2026-08-30 オーナー指示）────────────────────────────────
# 鷲見さんとのダイレクトで別会社の話をする。**その内容を全体チャットへ絶対に出さない。**
#
# ★プロンプトで「言わないで」と頼むだけでは守れない（このリポジトリで前例あり）。
#   **見えないものは漏らせない**ので、SQLの段階で機密ルームを外す。
#
# どの部屋から呼ばれたかは環境変数 CWAI_ROOM_ID で分かる（qa.py が env_extra で渡している）。
#   機密ルームから聞かれた → その部屋は読める（本人同士の会話なので当然）
#   それ以外から聞かれた   → 機密ルームは検索対象から消え、直接読もうとしても断る
#   機密ルームから他室へ投稿しようとした → 断る（外へ持ち出す経路を塞ぐ）

def _company_map() -> dict:
    import json
    try:
        return json.loads(settings.get_setting("room_company_map", "") or "{}")
    except Exception:
        return {}


def _here_company() -> str:
    """いまどの会社の場から呼ばれているか。qa.py が CWAI_COMPANY で渡す。"""
    c = (os.environ.get("CWAI_COMPANY") or "").strip()
    if c:
        return c
    m = _company_map()
    rid = os.environ.get("CWAI_ROOM_ID") or ""
    return (m.get("rooms", {}) or {}).get(str(rid)) or m.get("default") or ""


def _rooms_of(company: str) -> set:
    """その会社の入口になっているルーム。"""
    m = _company_map()
    return {int(k) for k, v in (m.get("rooms", {}) or {}).items()
            if v == company and str(k).isdigit()}


def _other_company_rooms() -> set:
    """いまの会社**以外**のルーム。ここは見せない・書かない。"""
    m = _company_map()
    me = _here_company()
    if not me:
        return set()
    return {int(k) for k, v in (m.get("rooms", {}) or {}).items()
            if v != me and str(k).isdigit()}


# 旧名。既存の呼び出し（scheduler / daily_report）が使っている
def _confidential() -> set:
    """日報・進捗確認から外すルーム＝いまの会社以外のルーム。

    ★呼び出し元に会社の文脈が無い（定時ジョブ）ときは、
      設定 confidential_room_ids のルームを外す（従来どおり）。
    """
    me = _here_company()
    if me:
        return _other_company_rooms()
    raw = settings.get_setting("confidential_room_ids", "") or ""
    return {int(x.strip()) for x in raw.replace("、", ",").split(",") if x.strip().isdigit()}


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
    # ★他社のルームは検索結果に出さない（双方向・2026-08-30 オーナー指示）。
    #   大京商事の場から新誠は見えないし、新誠の場から大京商事も見えない。
    ng = _other_company_rooms()
    if ng:
        sql += " AND room_id NOT IN (%s)" % ",".join("?" * len(ng))
        params += sorted(ng)
    sql += " ORDER BY send_time DESC, message_id DESC LIMIT ?"; params.append(limit)
    rows = query(sql, tuple(params))
    return {"ok": True, "count": len(rows), "messages": [_msg(m) for m in rows]}


def chatwork_get_messages(room_id, limit=30):
    if int(room_id or 0) in _other_company_rooms():
        return {"ok": False, "error":
                "別の会社のルームです。ここからは読めません（room_id=%s／いまの会社=%s）"
                % (room_id, _here_company() or "不明")}
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
    # ★別の会社のルームへは投稿しない（双方向・2026-08-30 オーナー指示）
    if int(room_id or 0) in _other_company_rooms():
        return {"ok": False, "error":
                "別の会社のルームへは投稿できません（送り先=%s／いまの会社=%s）"
                % (room_id, _here_company() or "不明")}
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
