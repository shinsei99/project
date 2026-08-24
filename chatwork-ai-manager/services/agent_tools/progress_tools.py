"""Progress Tool。定時処理（13/18/翌10時）が「確認/催促すべきTODO」を抽出する。

kind:
  due_soon    … 期限が近い(既定24h以内)＋本日期限で未完了     … 13:00向け
  overdue     … 期限超過で未完了                              … 汎用
  stale       … 一定日数(既定3日)動きがない未完了              … 汎用
  carryover   … 前日以前が期限/前日から未完了のまま繰り越し    … 翌10:00向け
  today_open  … 本日期限＋未着手＋期限未設定全件（終業前確認）  … 18:00向け
  due_reminder… 期限日の前日で未完了（前日が休業日なら当日）      … 期限リマインド向け(TASK-20260824-001)
"""
import datetime

from db.connection import get_conn, query
from services import settings, tasks as T
from services.agent_tools import format_tools


# 定時確認(10/13/18時)は「AI確認待ち」の未完了TODOも対象に含める（TASK-20260818-006）。
# OPEN_STATUSES自体は変えない（ダッシュボード集計等、AI確認待ちを含めたくない既存呼び出しがあるため）。
_ATTENTION_STATUSES = T.OPEN_STATUSES + [T.STATUS_AI_CONFIRM]


def _open_ph():
    return ",".join("?" * len(_ATTENTION_STATUSES)), list(_ATTENTION_STATUSES)


def _fmt(rows):
    return [{
        "id": t["id"], "content": t["content"], "assignee": t["assignee_name"],
        "assignee_account_id": t["assignee_account_id"],
        "requester": t["requester"], "due_date": t["due_date"], "status": t["status"],
        "room_id": t["room_id"], "check_count": t["check_count"],
        "escalation_stage": t["escalation_stage"], "last_check_at": t["last_check_at"],
        "last_progress_at": t["last_progress_at"],
        "last_activity_at": t["last_activity_at"], "source_message_id": t["source_message_id"],
        "skip_check": t["skip_check"], "skip_check_reason": t["skip_check_reason"],
    } for t in rows]


def tasks_needing_attention(kind="overdue", limit=50):
    today = datetime.date.today().isoformat()
    ph, params = _open_ph()
    # skip_check=1 のTODOは全種別の定時確認から除外（社外待ち等で確認しても意味がない場合。TASK-20260817-013）
    skip = "AND COALESCE(skip_check, 0) = 0 "
    if kind == "overdue":
        rows = query(f"SELECT * FROM tasks WHERE due_date IS NOT NULL AND due_date < ? "
                     f"AND status IN ({ph}) {skip}ORDER BY due_date LIMIT ?", (today, *params, limit))
    elif kind == "due_soon":
        rows = query(f"SELECT * FROM tasks WHERE due_date IS NOT NULL AND due_date <= ? "
                     f"AND status IN ({ph}) {skip}ORDER BY due_date LIMIT ?", (today, *params, limit))
    elif kind == "today_open":
        # 本日期限 or 未着手 or 期限未設定（期限未設定は毎日18時の確認対象に常に含める）
        rows = query(f"SELECT * FROM tasks WHERE (due_date = ? OR status='未着手' OR due_date IS NULL) "
                     f"AND status IN ({ph}) {skip}ORDER BY (due_date IS NULL), due_date LIMIT ?",
                     (today, *params, limit))
    elif kind == "carryover":
        # 期限超過（前日以前が期限で未完了）に加え、
        # 期限未設定かつ一度もAI確認していない「AI確認待ち」も前日までに進捗確認が取れていないものとして含める（TASK-20260818-005）
        rows = query(f"SELECT * FROM tasks WHERE "
                     f"(due_date < ? OR (due_date IS NULL AND (check_count = 0 OR last_check_at IS NULL))) "
                     f"AND status IN ({ph}) {skip}"
                     f"ORDER BY (due_date IS NULL), due_date LIMIT ?", (today, *params, limit))
    elif kind == "stale":
        stale_days = settings.get_int("stale_days", 3)
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=stale_days)).strftime("%Y-%m-%d %H:%M:%S")
        rows = query(f"SELECT * FROM tasks WHERE status IN ({ph}) "
                     f"{skip}AND COALESCE(last_activity_at, created_at) < ? ORDER BY last_activity_at LIMIT ?",
                     (*params, cutoff, limit))
    elif kind == "due_reminder":
        # 期限日の前日に送るのが原則（carryover_1000と同時刻）。
        # 前日が休業日（年間休暇スケジュールのオレンジ）だった場合は前倒しせず、
        # 休業日をまたいで当日を対象に含める（closing_1800/carryover_1000と同じ休業日判定を流用）。
        from services import holidays as H
        tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        try:
            yesterday_was_holiday = H.is_holiday(yesterday)
        except Exception:
            yesterday_was_holiday = False
        if yesterday_was_holiday:
            rows = query(f"SELECT * FROM tasks WHERE due_date IN (?, ?) "
                         f"AND status IN ({ph}) {skip}ORDER BY due_date LIMIT ?",
                         (tomorrow, today, *params, limit))
        else:
            rows = query(f"SELECT * FROM tasks WHERE due_date = ? "
                         f"AND status IN ({ph}) {skip}ORDER BY due_date LIMIT ?",
                         (tomorrow, *params, limit))
    else:
        return {"ok": False, "error": f"unknown kind: {kind}"}
    tasks = _fmt(rows)
    # formatted: 担当者ごとにグループ化＋状態アイコンで整形済みの文字列（定時TODO確認と同じ見た目）。
    # QAが複数件を一覧で答えるときは、これをそのまま回答本文として使うこと。
    return {"ok": True, "kind": kind, "count": len(rows), "tasks": tasks,
            "formatted": format_tools.format_grouped_task_list(tasks)}


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
