"""開発タスク（DEVELOPMENT Agent）の永続化層。

**既存の services/tasks.py（業務TODO）とは別物。** 状態語も別体系なので混同しないこと。
  業務TODO : 未着手 / 進行中 / 確認待ち / 完了 …（社員の仕事）
  開発タスク: RECEIVED / PLANNING / RUNNING / WAITING_USER / TESTING / FAILED / COMPLETED / CANCELLED

全状態をDBに持つ（プロセスメモリに置かない）ので、workerが落ちても再起動で復元できる。
"""
import datetime

from db.connection import get_conn, query, query_one

# ---- 状態 ----
RECEIVED = "RECEIVED"
PLANNING = "PLANNING"
RUNNING = "RUNNING"
WAITING_USER = "WAITING_USER"
TESTING = "TESTING"
FAILED = "FAILED"
COMPLETED = "COMPLETED"
CANCELLED = "CANCELLED"

STATUSES = (RECEIVED, PLANNING, RUNNING, WAITING_USER, TESTING, FAILED, COMPLETED, CANCELLED)
# 実行中とみなす状態（workerが落ちたら復元対象）
ACTIVE_STATUSES = (RECEIVED, PLANNING, RUNNING, TESTING)
# 終わった状態
DONE_STATUSES = (FAILED, COMPLETED, CANCELLED)

KINDS = ("NEW_APP", "EXISTING_APP", "FEATURE_ADD", "BUG_FIX", "UI_CHANGE",
         "API_DEVELOPMENT", "DATABASE_CHANGE", "INVESTIGATION", "OTHER")


def _new_task_id(conn) -> str:
    """TASK-YYYYMMDD-XXX を採番する（同日連番）。"""
    day = datetime.date.today().strftime("%Y%m%d")
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM dev_tasks WHERE task_id LIKE ?", (f"TASK-{day}-%",)
    ).fetchone()
    n = (row["n"] if row else 0) + 1
    while True:
        cand = f"TASK-{day}-{n:03d}"
        if not conn.execute("SELECT 1 FROM dev_tasks WHERE task_id=?", (cand,)).fetchone():
            return cand
        n += 1


def create(request: str, title=None, kind=None, channel="admin", room_id=None,
           line_user_id=None, requester=None, requester_account_id=None,
           project_dir=None, workspace=None) -> dict:
    """開発タスクを受け付ける（実行はしない。worker の dev_runner が拾う）。"""
    if not (request or "").strip():
        raise ValueError("request（依頼内容）が空です")
    kind = kind if kind in KINDS else None
    with get_conn() as conn:
        task_id = _new_task_id(conn)
        conn.execute(
            "INSERT INTO dev_tasks (task_id, title, request, kind, status, project_dir, "
            "workspace, channel, room_id, line_user_id, requester, requester_account_id) "
            "VALUES (?, ?, ?, ?, 'RECEIVED', ?, ?, ?, ?, ?, ?, ?)",
            (task_id, (title or request)[:120], request, kind, project_dir, workspace,
             channel, room_id, line_user_id, requester, requester_account_id),
        )
        conn.execute(
            "INSERT INTO dev_task_events (task_id, event_type, note) VALUES (?, 'created', ?)",
            (task_id, f"受付 channel={channel} requester={requester or '?'}"),
        )
    return get(task_id)


def get(task_id: str):
    row = query_one("SELECT * FROM dev_tasks WHERE task_id=?", (task_id,))
    return dict(row) if row else None


def list_tasks(status=None, limit=50):
    if status:
        rows = query("SELECT * FROM dev_tasks WHERE status=? ORDER BY id DESC LIMIT ?",
                     (status, limit))
    else:
        rows = query("SELECT * FROM dev_tasks ORDER BY id DESC LIMIT ?", (limit,))
    return [dict(r) for r in rows]


def active():
    """未完了（実行待ち/実行中/ユーザー待ち）の開発タスク。"""
    marks = ",".join("?" * (len(ACTIVE_STATUSES) + 1))
    rows = query(
        f"SELECT * FROM dev_tasks WHERE status IN ({marks}) ORDER BY id",
        ACTIVE_STATUSES + (WAITING_USER,),
    )
    return [dict(r) for r in rows]


def next_queued():
    """次に実行すべきタスク（古い順に1件）。"""
    row = query_one("SELECT * FROM dev_tasks WHERE status='RECEIVED' ORDER BY id LIMIT 1")
    return dict(row) if row else None


def claim(task_id: str) -> bool:
    """RECEIVED → RUNNING を排他的に確保する（2つのtickが同じタスクを走らせない）。"""
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE dev_tasks SET status='RUNNING', started_at=datetime('now'), "
            "attempts=attempts+1, updated_at=datetime('now') "
            "WHERE task_id=? AND status='RECEIVED'",
            (task_id,),
        )
        claimed = cur.rowcount == 1
        if claimed:
            conn.execute(
                "INSERT INTO dev_task_events (task_id, event_type, note) VALUES (?, 'status', ?)",
                (task_id, "RECEIVED → RUNNING"),
            )
    return claimed


def set_status(task_id: str, status: str, note=None, **fields) -> None:
    """状態と付随情報を更新する。fields は dev_tasks の列名（result/error/session_id 等）。"""
    if status not in STATUSES:
        raise ValueError(f"未知の状態: {status}")
    allowed = {"result", "error", "question", "answer", "session_id", "project_dir",
               "kind", "title", "log_path", "workspace", "finished_at"}
    sets, params = ["status=?", "updated_at=datetime('now')"], [status]
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k}=?")
            params.append(v)
    if status in DONE_STATUSES and "finished_at" not in fields:
        sets.append("finished_at=datetime('now')")
    params.append(task_id)
    with get_conn() as conn:
        conn.execute(f"UPDATE dev_tasks SET {', '.join(sets)} WHERE task_id=?", params)
        conn.execute(
            "INSERT INTO dev_task_events (task_id, event_type, note) VALUES (?, 'status', ?)",
            (task_id, note or status),
        )


def add_event(task_id: str, event_type: str, note: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO dev_task_events (task_id, event_type, note) VALUES (?, ?, ?)",
            (task_id, event_type, (note or "")[:4000]),
        )


def events(task_id: str, limit=100):
    rows = query(
        "SELECT * FROM dev_task_events WHERE task_id=? ORDER BY id DESC LIMIT ?",
        (task_id, limit),
    )
    return [dict(r) for r in rows]


def answer(task_id: str, answer_text: str) -> dict:
    """WAITING_USER のタスクにユーザー回答を渡し、実行待ちに戻す（同じTaskを再開する）。"""
    t = get(task_id)
    if not t:
        raise ValueError(f"開発タスクが見つかりません: {task_id}")
    if t["status"] != WAITING_USER:
        raise ValueError(f"{task_id} は回答待ちではありません（現在: {t['status']}）")
    prev = t.get("answer") or ""
    merged = (prev + "\n" if prev else "") + answer_text
    with get_conn() as conn:
        conn.execute(
            "UPDATE dev_tasks SET status='RECEIVED', answer=?, question=NULL, "
            "updated_at=datetime('now') WHERE task_id=?",
            (merged, task_id),
        )
        conn.execute(
            "INSERT INTO dev_task_events (task_id, event_type, note) VALUES (?, 'answer', ?)",
            (task_id, answer_text[:2000]),
        )
    return get(task_id)


def cancel(task_id: str, reason=None) -> dict:
    t = get(task_id)
    if not t:
        raise ValueError(f"開発タスクが見つかりません: {task_id}")
    if t["status"] in DONE_STATUSES:
        return t
    set_status(task_id, CANCELLED, note=reason or "ユーザーによる中止")
    return get(task_id)


def latest_for(channel=None, room_id=None, line_user_id=None):
    """「さっきのアプリ」を解決するための直近タスク。"""
    sql = "SELECT * FROM dev_tasks WHERE 1=1"
    params = []
    if channel:
        sql += " AND channel=?"
        params.append(channel)
    if room_id:
        sql += " AND room_id=?"
        params.append(room_id)
    if line_user_id:
        sql += " AND line_user_id=?"
        params.append(line_user_id)
    sql += " ORDER BY id DESC LIMIT 1"
    row = query_one(sql, tuple(params))
    return dict(row) if row else None
