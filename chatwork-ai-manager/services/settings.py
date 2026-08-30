"""settings / processing_state テーブルへのアクセス。"""
from db.connection import get_conn, query_one

VALID_POST_MODES = ("confirm", "semi", "auto")


def get_setting(key: str, default=None):
    row = query_one("SELECT value FROM settings WHERE key=?", (key,))
    return row["value"] if row else default


def set_setting(key: str, value) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings(key, value, updated_at) VALUES (?, ?, datetime('now','localtime')) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=datetime('now','localtime')",
            (key, str(value)),
        )


def get_int(key: str, default: int) -> int:
    try:
        return int(get_setting(key, default))
    except (TypeError, ValueError):
        return default


def post_mode() -> str:
    m = get_setting("post_mode", "confirm")
    return m if m in VALID_POST_MODES else "confirm"


def all_settings() -> dict:
    from db.connection import query
    return {r["key"]: r["value"] for r in query("SELECT key, value FROM settings")}


# --- processing_state（カーソル類） ---
def get_state(key: str, default=None):
    row = query_one("SELECT value FROM processing_state WHERE key=?", (key,))
    return row["value"] if row else default


def set_state(key: str, value) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO processing_state(key, value, updated_at) VALUES (?, ?, datetime('now','localtime')) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=datetime('now','localtime')",
            (key, str(value)),
        )
