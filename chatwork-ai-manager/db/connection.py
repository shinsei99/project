"""SQLite 接続ヘルパ。

worker（常時書込）と Streamlit（読み＋一部書込）の 2 プロセスが同一 DB を
共有するため WAL モード＋busy_timeout を必須とする。
"""
import os
import sqlite3
from contextlib import contextmanager

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(APP_DIR, "data")
DB_PATH = os.environ.get("CWAI_DB_PATH", os.path.join(DATA_DIR, "app.db"))


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


@contextmanager
def get_conn():
    """コミット/ロールバックとクローズを自動処理するコンテキストマネージャ。"""
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def query(sql: str, params=()):
    with get_conn() as conn:
        return conn.execute(sql, params).fetchall()


def query_one(sql: str, params=()):
    with get_conn() as conn:
        return conn.execute(sql, params).fetchone()


def execute(sql: str, params=()):
    """単発の書込。lastrowid を返す。"""
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        return cur.lastrowid
