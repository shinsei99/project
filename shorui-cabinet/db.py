# -*- coding: utf-8 -*-
"""書類キャビネットの保存層（SQLite）。

「紙の書類が物理的にどこにあるか」を記録するのが目的なので、
本体はあくまで所在情報。原本ファイルは任意でサムネイルだけ持つ。

DBは data/cabinet.db。物件名や書類の所在を含むため data/ は gitignore。
"""

# 実行環境は system python 3.9（他アプリと同じ）。`str | None` 等の新しい型注釈を
# 3.9 でも書けるようにするため、注釈の評価を遅延させる。
from __future__ import annotations

import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "cabinet.db")
THUMB_DIR = os.path.join(DATA_DIR, "thumbs")

# 不動産の紙書類でよく出るもの。設定タブから増やせる
DEFAULT_DOC_TYPES = [
    "売買契約書",
    "賃貸借契約書",
    "重要事項説明書",
    "管理委託契約書",
    "覚書・合意書",
    "登記簿謄本",
    "図面・間取図",
    "測量図・境界",
    "確認済証・検査済証",
    "見積書・請求書",
    "領収書",
    "鍵預り証",
    "保険証券",
    "納税通知・評価証明",
    "写真・現況資料",
    "その他",
]


def _connect() -> sqlite3.Connection:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(THUMB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """テーブルが無ければ作る。既存DBには影響しない。"""
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS locations (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                name      TEXT NOT NULL UNIQUE,   -- 例: 本社3F 書庫A / 棚2
                note      TEXT DEFAULT '',
                sort      INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS properties (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                name      TEXT NOT NULL UNIQUE,
                note      TEXT DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS documents (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                title         TEXT NOT NULL,
                doc_type      TEXT DEFAULT '',
                property_name TEXT DEFAULT '',      -- 物件名（マスタに無くても自由入力できる）
                doc_date      TEXT DEFAULT '',      -- YYYY-MM-DD（不明なら空）
                counterparty  TEXT DEFAULT '',      -- 相手先・当事者
                summary       TEXT DEFAULT '',
                location_id   INTEGER,              -- 保管場所
                container     TEXT DEFAULT '',      -- ファイル名・箱番号など
                quantity      TEXT DEFAULT '',      -- 部数・冊数など
                thumb         TEXT DEFAULT '',      -- data/thumbs 配下のファイル名
                note          TEXT DEFAULT '',
                created_at    TEXT NOT NULL,
                updated_at    TEXT NOT NULL,
                FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_doc_property ON documents(property_name);
            CREATE INDEX IF NOT EXISTS idx_doc_type     ON documents(doc_type);
            CREATE INDEX IF NOT EXISTS idx_doc_location ON documents(location_id);
            """
        )


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------- 保管場所 ----------

def list_locations() -> list[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM locations ORDER BY sort, name"
        ).fetchall()


def add_location(name: str, note: str = "") -> int | None:
    """同名があれば追加せず既存のidを返す。"""
    name = (name or "").strip()
    if not name:
        return None
    with _connect() as conn:
        row = conn.execute("SELECT id FROM locations WHERE name = ?", (name,)).fetchone()
        if row:
            return row["id"]
        cur = conn.execute(
            "INSERT INTO locations (name, note, sort, created_at) VALUES (?,?,?,?)",
            (name, note.strip(), 0, _now()),
        )
        return cur.lastrowid


def update_location(loc_id: int, name: str, note: str, sort: int) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE locations SET name=?, note=?, sort=? WHERE id=?",
            (name.strip(), note.strip(), sort, loc_id),
        )


def delete_location(loc_id: int) -> None:
    """場所を消しても書類は残る（location_id が NULL になる）。"""
    with _connect() as conn:
        conn.execute("DELETE FROM locations WHERE id=?", (loc_id,))


def location_counts() -> dict[int, int]:
    """保管場所ごとの書類件数。"""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT location_id, COUNT(*) AS c FROM documents "
            "WHERE location_id IS NOT NULL GROUP BY location_id"
        ).fetchall()
    return {r["location_id"]: r["c"] for r in rows}


# ---------- 物件 ----------

def list_properties() -> list[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute("SELECT * FROM properties ORDER BY name").fetchall()


def add_property(name: str, note: str = "") -> int | None:
    name = (name or "").strip()
    if not name:
        return None
    with _connect() as conn:
        row = conn.execute("SELECT id FROM properties WHERE name = ?", (name,)).fetchone()
        if row:
            return row["id"]
        cur = conn.execute(
            "INSERT INTO properties (name, note, created_at) VALUES (?,?,?)",
            (name, note.strip(), _now()),
        )
        return cur.lastrowid


def delete_property(prop_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM properties WHERE id=?", (prop_id,))


# ---------- 書類 ----------

def add_document(d: dict) -> int:
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO documents
               (title, doc_type, property_name, doc_date, counterparty, summary,
                location_id, container, quantity, thumb, note, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                d.get("title", "").strip() or "（無題）",
                d.get("doc_type", ""),
                d.get("property_name", "").strip(),
                d.get("doc_date", ""),
                d.get("counterparty", "").strip(),
                d.get("summary", "").strip(),
                d.get("location_id"),
                d.get("container", "").strip(),
                d.get("quantity", "").strip(),
                d.get("thumb", ""),
                d.get("note", "").strip(),
                _now(),
                _now(),
            ),
        )
        return cur.lastrowid


def update_document(doc_id: int, d: dict) -> None:
    with _connect() as conn:
        conn.execute(
            """UPDATE documents SET
               title=?, doc_type=?, property_name=?, doc_date=?, counterparty=?,
               summary=?, location_id=?, container=?, quantity=?, note=?, updated_at=?
               WHERE id=?""",
            (
                d.get("title", "").strip() or "（無題）",
                d.get("doc_type", ""),
                d.get("property_name", "").strip(),
                d.get("doc_date", ""),
                d.get("counterparty", "").strip(),
                d.get("summary", "").strip(),
                d.get("location_id"),
                d.get("container", "").strip(),
                d.get("quantity", "").strip(),
                d.get("note", "").strip(),
                _now(),
                doc_id,
            ),
        )


def delete_document(doc_id: int) -> None:
    """書類を消すときはサムネイル画像も片付ける。"""
    with _connect() as conn:
        row = conn.execute("SELECT thumb FROM documents WHERE id=?", (doc_id,)).fetchone()
        if row and row["thumb"]:
            path = os.path.join(THUMB_DIR, row["thumb"])
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))


def search_documents(
    keyword: str = "",
    doc_type: str = "",
    property_name: str = "",
    location_id: int | None = None,
    year: str = "",
) -> list[sqlite3.Row]:
    """指定された条件のAND検索。キーワードはスペース区切りで全項目を横断。"""
    sql = [
        "SELECT d.*, l.name AS location_name FROM documents d "
        "LEFT JOIN locations l ON l.id = d.location_id WHERE 1=1"
    ]
    params: list = []

    for word in (keyword or "").split():
        sql.append(
            " AND (d.title LIKE ? OR d.property_name LIKE ? OR d.counterparty LIKE ?"
            " OR d.summary LIKE ? OR d.container LIKE ? OR d.note LIKE ? OR d.doc_type LIKE ?)"
        )
        params.extend([f"%{word}%"] * 7)

    if doc_type:
        sql.append(" AND d.doc_type = ?")
        params.append(doc_type)
    if property_name:
        sql.append(" AND d.property_name = ?")
        params.append(property_name)
    if location_id:
        sql.append(" AND d.location_id = ?")
        params.append(location_id)
    if year:
        sql.append(" AND d.doc_date LIKE ?")
        params.append(f"{year}%")

    sql.append(" ORDER BY d.doc_date DESC, d.id DESC")
    with _connect() as conn:
        return conn.execute("".join(sql), params).fetchall()


def get_document(doc_id: int) -> sqlite3.Row | None:
    with _connect() as conn:
        return conn.execute(
            "SELECT d.*, l.name AS location_name FROM documents d "
            "LEFT JOIN locations l ON l.id = d.location_id WHERE d.id = ?",
            (doc_id,),
        ).fetchone()


def stats() -> dict:
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM documents").fetchone()["c"]
        props = conn.execute(
            "SELECT COUNT(DISTINCT property_name) AS c FROM documents WHERE property_name <> ''"
        ).fetchone()["c"]
        locs = conn.execute("SELECT COUNT(*) AS c FROM locations").fetchone()["c"]
        unplaced = conn.execute(
            "SELECT COUNT(*) AS c FROM documents WHERE location_id IS NULL"
        ).fetchone()["c"]
    return {"documents": total, "properties": props, "locations": locs, "unplaced": unplaced}


def used_doc_types() -> list[str]:
    """既存データで実際に使われている種別（既定リストに無い自作の種別を拾う）。"""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT doc_type FROM documents WHERE doc_type <> '' ORDER BY doc_type"
        ).fetchall()
    return [r["doc_type"] for r in rows]


def all_doc_types() -> list[str]:
    extra = [t for t in used_doc_types() if t not in DEFAULT_DOC_TYPES]
    return DEFAULT_DOC_TYPES + extra
