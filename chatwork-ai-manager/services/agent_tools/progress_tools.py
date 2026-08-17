"""Progress Tool。定時処理（13/18/翌10時）が「確認/催促すべきTODO」を抽出する。

kind:
  due_soon    … 期限が近い(既定24h以内)＋本日期限で未完了     … 13:00向け
  overdue     … 期限超過で未完了                              … 汎用
  stale       … 一定日数(既定3日)動きがない未完了              … 汎用
  carryover   … 前日以前が期限/前日から未完了のまま繰り越し    … 翌10:00向け
  today_open  … 本日期限＋未着手＋期限未設定全件（終業前確認）  … 18:00向け
  due_reminder… 期限のN日前(既定2日)で未完了                   … 期限リマインド向け
"""
import datetime

from db.connection import get_conn, query
from services import settings, tasks as T


def _open_ph():
    return ",".join("?" * len(T.OPEN_STATUSES)), list(T.OPEN_STATUSES)


def _fmt(rows):
    return [{
        "id": t["id"], "content": t["content"], "assignee": t["assignee_name"],
        "assignee_account_id": t["assignee_account_id"],
        "requester": t["requester"], "due_date": t["due_date"], "status": t["status"],
        "room_id": t["room_id"], "check_count": t["check_count"],
        "escalation_stage": t["escalation_stage"], "last_check_at": t["last_check_at"],
        "last_activity_at": t["last_activity_at"], "source_message_id": t["source_message_id"],
    } for t in rows]


def tasks_needing_attention(kind="overdue", limit=50):
    today = datetime.date.today().isoformat()
    ph, params = _open_ph()
    if kind == "overdue":
        rows = query(f"SELECT * FROM tasks WHERE due_date IS NOT NULL AND due_date < ? "
                     f"AND status IN ({ph}) ORDER BY due_date LIMIT ?", (today, *params, limit))
    elif kind == "due_soon":
        rows = query(f"SELECT * FROM tasks WHERE due_date IS NOT NULL AND due_date <= ? "
                     f"AND status IN ({ph}) ORDER BY due_date LIMIT ?", (today, *params, limit))
    elif kind == "today_open":
        # 本日期限 or 未着手 or 期限未設定（期限未設定は毎日18時の確認対象に常に含める）
        rows = query(f"SELECT * FROM tasks WHERE (due_date = ? OR status='未着手' OR due_date IS NULL) "
                     f"AND status IN ({ph}) ORDER BY (due_date IS NULL), due_date LIMIT ?",
                     (today, *params, limit))
    elif kind == "carryover":
        rows = query(f"SELECT * FROM tasks WHERE due_date IS NOT NULL AND due_date < ? "
                     f"AND status IN ({ph}) ORDER BY due_date LIMIT ?", (today, *params, limit))
    elif kind == "stale":
        stale_days = settings.get_int("stale_days", 3)
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=stale_days)).strftime("%Y-%m-%d %H:%M:%S")
        rows = query(f"SELECT * FROM tasks WHERE status IN ({ph}) "
                     f"AND COALESCE(last_activity_at, created_at) < ? ORDER BY last_activity_at LIMIT ?",
                     (*params, cutoff, limit))
    elif kind == "due_reminder":
        reminder_days = settings.get_int("due_reminder_days", 2)
        target = (datetime.date.today() + datetime.timedelta(days=reminder_days)).isoformat()
        rows = query(f"SELECT * FROM tasks WHERE due_date = ? "
                     f"AND status IN ({ph}) ORDER BY due_date LIMIT ?", (target, *params, limit))
    else:
        return {"ok": False, "error": f"unknown kind: {kind}"}
    return {"ok": True, "kind": kind, "count": len(rows), "tasks": _fmt(rows)}


def record_check(task_id, escalation_stage=None):
    """AIが進捗確認したことを記録（確認回数++・最終確認日時・エスカレーション段階）。"""
    with get_conn() as conn:
        if escalation_stage is not None:
            conn.execute("UPDATE tasks SET check_count=check_count+1, "
                         "last_check_at=datetime('now'), escalation_stage=? WHERE id=?",
                         (escalation_stage, task_id))
        else:
            conn.execute("UPDATE tasks SET check_count=check_count+1, "
                         "last_check_at=datetime('now') WHERE id=?", (task_id,))
    return {"ok": True, "task_id": task_id}
