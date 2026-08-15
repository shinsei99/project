"""案件（projects）の最小 CRUD。agent_tools/project_tools.py から利用する。

案件は「物件名・顧客名」などで会話やTODOを束ねる単位。まずは検索・作成・更新の最小機能。
"""
from db.connection import get_conn, query, query_one

OPEN_PROJECT_STATUSES = ["進行中", "保留"]


def search(keyword: str = None, limit: int = 30):
    if keyword:
        kw = f"%{keyword}%"
        return query(
            "SELECT * FROM projects WHERE name LIKE ? OR customer LIKE ? "
            "ORDER BY updated_at DESC LIMIT ?",
            (kw, kw, limit),
        )
    return query("SELECT * FROM projects ORDER BY updated_at DESC LIMIT ?", (limit,))


def get(project_id: int):
    return query_one("SELECT * FROM projects WHERE id=?", (project_id,))


def get_or_create(name: str, customer: str = None, room_id: int = None) -> int:
    """同名案件があれば流用（重複作成しない）。無ければ作成し id を返す。"""
    row = query_one("SELECT id FROM projects WHERE name=?", (name,))
    if row:
        return row["id"]
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO projects (name, customer, room_id, status) VALUES (?, ?, ?, '進行中')",
            (name, customer, room_id),
        )
        pid = cur.lastrowid
        conn.execute(
            "INSERT INTO project_events (project_id, event_type, note) VALUES (?, 'created', ?)",
            (pid, name),
        )
        return pid


def update(project_id: int, updates: dict, note: str = None) -> bool:
    allowed = {k: v for k, v in updates.items()
               if k in ("name", "customer", "status", "room_id")}
    if not allowed:
        return False
    set_clause = ", ".join(f"{k}=?" for k in allowed)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE projects SET {set_clause}, updated_at=datetime('now') WHERE id=?",
            (*allowed.values(), project_id),
        )
        conn.execute(
            "INSERT INTO project_events (project_id, event_type, note) VALUES (?, 'update', ?)",
            (project_id, note or ",".join(allowed.keys())),
        )
    return True


def tasks_of(project_id: int):
    return query("SELECT * FROM tasks WHERE project_id=? ORDER BY id", (project_id,))
