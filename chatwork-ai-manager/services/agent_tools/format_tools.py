"""TODO一覧の共通整形（担当者ごとにグループ化＋状態アイコン）。

もとは scheduler.py の定時TODO確認・週次棚卸しだけが持っていたロジック。
QA(services/qa.py)がユーザーの求めに応じてTODOを一覧するときにこれを使わず、
フラットな箇条書きになってしまっていた（TASK-20260819-003）。
両方から同じ関数を使うことで見た目を一致させる。
"""
from services import tasks as T

STATUS_EMOJI = {
    T.STATUS_TODO: "⬜", T.STATUS_DOING: "🔵", T.STATUS_WAITING: "🟡",
    T.STATUS_AI_CONFIRM: "🟡", T.STATUS_OVERDUE: "🔴", T.STATUS_HOLD: "⏸",
}


def _get(t, key, default=None):
    """sqlite3.Row / dict のどちらで渡されても安全に値を取り出す。"""
    try:
        v = t[key]
        return default if v is None else v
    except (IndexError, KeyError, TypeError):
        return default


def format_task_line(t) -> str:
    due = _get(t, "due_date", "期限未設定")
    status = _get(t, "status")
    emoji = STATUS_EMOJI.get(status, "・")
    requester = _get(t, "requester", "?")
    content = _get(t, "content")
    return f"{emoji} {content}\n　　期限:{due}｜{status}｜依頼:{requester}"


def format_grouped_task_list(tasks, title=None) -> str:
    """担当者ごとにグループ化し、状態アイコン付きで整形する（期限が近い担当者を先に）。

    scheduler.py の定時確認・週次棚卸しと、QA の都度回答で共通利用する。
    """
    if not tasks:
        return "（該当する未完了TODOはありません）"
    groups = {}
    for t in tasks:
        key = _get(t, "assignee") or _get(t, "assignee_name") or "未定"
        groups.setdefault(key, []).append(t)

    def group_sort_key(item):
        _name, ts = item
        dues = [_get(t, "due_date") for t in ts if _get(t, "due_date")]
        return min(dues) if dues else "9999-99-99"

    lines = [title] if title else []
    for assignee, ts in sorted(groups.items(), key=group_sort_key):
        ts_sorted = sorted(ts, key=lambda t: _get(t, "due_date") or "9999-99-99")
        lines.append("")
        lines.append(f"👤 {assignee}（{len(ts_sorted)}件）")
        for t in ts_sorted:
            lines.append(format_task_line(t))
    return "\n".join(lines).strip()
