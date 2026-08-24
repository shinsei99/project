"""TODO（tasks）の CRUD と状態遷移。状態変化は必ず task_events に記録する。"""
from db.connection import get_conn, query, query_one

# 状態（§9）
STATUS_TODO = "未着手"
STATUS_DOING = "進行中"
STATUS_WAITING = "確認待ち"
STATUS_DONE = "完了"
STATUS_OVERDUE = "期限超過"
STATUS_HOLD = "保留"
STATUS_CANCEL = "キャンセル"
STATUS_AI_CONFIRM = "AI確認待ち"

ALL_STATUSES = [STATUS_TODO, STATUS_DOING, STATUS_WAITING, STATUS_DONE,
                STATUS_OVERDUE, STATUS_HOLD, STATUS_CANCEL, STATUS_AI_CONFIRM]
# 「未完了」とみなす状態（監督・放置チェック対象）
OPEN_STATUSES = [STATUS_TODO, STATUS_DOING, STATUS_WAITING, STATUS_OVERDUE, STATUS_HOLD]

_TASK_FIELDS = [
    "content", "project_id", "customer", "assignee_account_id", "assignee_name",
    "requester", "due_date", "due_raw", "priority", "status", "progress",
    "done_condition", "room_id", "source_message_id", "ai_reason", "ai_confidence",
    "conf_assignee", "conf_due", "conf_done", "conf_project", "is_speculative", "dedup_key",
    "skip_check", "skip_check_reason",
]


def create_task(data: dict) -> int:
    """TODO を作成し、task_events に created を記録。task_id を返す。"""
    fields = {k: data.get(k) for k in _TASK_FIELDS if k in data}
    fields.setdefault("content", data.get("content", ""))
    fields.setdefault("status", STATUS_TODO)
    cols = ", ".join(fields.keys())
    ph = ", ".join(["?"] * len(fields))
    with get_conn() as conn:
        cur = conn.execute(
            f"INSERT INTO tasks ({cols}, last_activity_at) VALUES ({ph}, datetime('now'))",
            tuple(fields.values()),
        )
        task_id = cur.lastrowid
        conn.execute(
            "INSERT INTO task_events (task_id, event_type, to_status, note, evidence_message_id) "
            "VALUES (?, 'created', ?, ?, ?)",
            (task_id, fields.get("status"), fields.get("ai_reason"),
             fields.get("source_message_id")),
        )
    return task_id


def update_status(task_id: int, to_status: str, note: str = None,
                  evidence_message_id: str = None, progress: int = None) -> None:
    row = get_task(task_id)
    if not row:
        return
    from_status = row["status"]
    with get_conn() as conn:
        if progress is not None:
            conn.execute(
                "UPDATE tasks SET status=?, progress=?, updated_at=datetime('now'), "
                "last_activity_at=datetime('now') WHERE id=?",
                (to_status, progress, task_id),
            )
        else:
            conn.execute(
                "UPDATE tasks SET status=?, updated_at=datetime('now'), "
                "last_activity_at=datetime('now') WHERE id=?",
                (to_status, task_id),
            )
        conn.execute(
            "INSERT INTO task_events (task_id, event_type, from_status, to_status, note, evidence_message_id) "
            "VALUES (?, 'status_change', ?, ?, ?, ?)",
            (task_id, from_status, to_status, note, evidence_message_id),
        )


def update_fields(task_id: int, updates: dict, note: str = None,
                  evidence_message_id: str = None) -> None:
    allowed = {k: v for k, v in updates.items() if k in _TASK_FIELDS}
    if not allowed:
        return
    set_clause = ", ".join(f"{k}=?" for k in allowed)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE tasks SET {set_clause}, updated_at=datetime('now'), "
            f"last_activity_at=datetime('now') WHERE id=?",
            (*allowed.values(), task_id),
        )
        conn.execute(
            "INSERT INTO task_events (task_id, event_type, note, evidence_message_id) "
            "VALUES (?, 'update', ?, ?)",
            (task_id, note or ",".join(allowed.keys()), evidence_message_id),
        )


def mark_progress_reported(task_id: int) -> None:
    """担当者からの進捗報告（progress_update/completion）を記録する。

    last_check_at（AIが確認した日時）とは別軸。定時確認(closing_1800/carryover_1000等)が
    同一TODOに対し、本日中かつ直近のAI確認より後に届いた進捗報告を無視して重ねて
    「進捗はいかがですか」と催促しないための判定に使う（TASK-20260824-002）。
    """
    with get_conn() as conn:
        conn.execute("UPDATE tasks SET last_progress_at=datetime('now') WHERE id=?", (task_id,))


def touch_activity(task_id: int, note: str = None, evidence_message_id: str = None) -> None:
    """状態は変えず「動きがあった」ことだけ記録（放置タイマーのリセット）。"""
    with get_conn() as conn:
        conn.execute("UPDATE tasks SET last_activity_at=datetime('now') WHERE id=?", (task_id,))
        if note:
            conn.execute(
                "INSERT INTO task_events (task_id, event_type, note, evidence_message_id) "
                "VALUES (?, 'comment', ?, ?)",
                (task_id, note, evidence_message_id),
            )


# ---- 参照 ----
def get_task(task_id: int):
    return query_one("SELECT * FROM tasks WHERE id=?", (task_id,))


def get_events(task_id: int):
    return query("SELECT * FROM task_events WHERE task_id=? ORDER BY id", (task_id,))


def open_tasks_in_room(room_id: int, include_ai_confirm: bool = False):
    """同一ルームの未完了 TODO（analyzer の文脈・重複判定用）。

    include_ai_confirm=True で status=AI確認待ち も含める（グローバルな OPEN_STATUSES
    自体は変えない。ダッシュボード集計等、AI確認待ちを含めたくない既存呼び出しがあるため。
    §既知の残課題 TASK-20260818-006 と同じ「呼び出し側で局所拡張する」パターン）。
    呼び出し側にAI確認待ちのTODOが見えないと、それへの進捗報告を target_task_id で
    紐付けられず、イベントが無言で捨てられる（2026-08-19 TASK-20260819-002 で実害確認）。
    """
    statuses = OPEN_STATUSES + [STATUS_AI_CONFIRM] if include_ai_confirm else OPEN_STATUSES
    ph = ",".join("?" * len(statuses))
    return query(
        f"SELECT * FROM tasks WHERE room_id=? AND status IN ({ph}) ORDER BY id",
        (room_id, *statuses),
    )


def open_tasks_all():
    """全ルーム横断の未完了 TODO（週次棚卸しレポート用。期限の有無を問わず全件）。"""
    ph = ",".join("?" * len(OPEN_STATUSES))
    return query(
        f"SELECT * FROM tasks WHERE status IN ({ph}) "
        f"ORDER BY room_id, (due_date IS NULL), due_date",
        tuple(OPEN_STATUSES),
    )


def find_by_dedup_key(dedup_key: str):
    if not dedup_key:
        return None
    return query_one("SELECT * FROM tasks WHERE dedup_key=? ORDER BY id DESC LIMIT 1", (dedup_key,))


def list_tasks(status: str = None, room_id: int = None, limit: int = 500):
    sql = "SELECT * FROM tasks WHERE 1=1"
    params = []
    if status:
        sql += " AND status=?"
        params.append(status)
    if room_id:
        sql += " AND room_id=?"
        params.append(room_id)
    sql += " ORDER BY (due_date IS NULL), due_date, id DESC LIMIT ?"
    params.append(limit)
    return query(sql, tuple(params))


def counts_by_status() -> dict:
    rows = query("SELECT status, COUNT(*) AS n FROM tasks GROUP BY status")
    return {r["status"]: r["n"] for r in rows}
