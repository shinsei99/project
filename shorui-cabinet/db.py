# -*- coding: utf-8 -*-
"""書類キャビネットの保存層（SQLite）。

管理の単位は「ファイル」＝ クリアファイル1冊・バインダー1冊・箱1つ。
書類1枚ずつは登録しない（現場では箱まで辿り着ければ十分で、
1枚ずつ登録すると作業が終わらず台帳が続かないため）。

中身の明細は AI が写真から起こしたテキストとして 1つのファイル行に持たせ、
検索は明細も含めた横断LIKEで効かせる。

DBは data/cabinet.db。物件名や所在を含むため data/ は gitignore。
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

# 入れ物の種類
KINDS = ["クリアファイル", "バインダー", "封筒", "箱", "ファイルボックス", "その他"]

# 不動産の紙書類でよく出るもの
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
    """テーブルが無ければ作る。旧「書類1枚ずつ」形式のデータがあればファイル単位へ移す。"""
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

            CREATE TABLE IF NOT EXISTS files (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                label         TEXT NOT NULL,        -- 背表紙・表紙の名前（探すときの目印）
                kind          TEXT DEFAULT '',      -- クリアファイル / バインダー / 箱 など
                location_id   INTEGER,
                spot          TEXT DEFAULT '',      -- 場所内の細かい位置（左から3番目 など）
                properties    TEXT DEFAULT '',      -- 関係する物件名（改行区切り）
                doc_types     TEXT DEFAULT '',      -- 入っている書類種別（カンマ区切り）
                year_from     TEXT DEFAULT '',
                year_to       TEXT DEFAULT '',
                item_count    TEXT DEFAULT '',      -- 点数（おおよそでよい）
                contents      TEXT DEFAULT '',      -- 中身の明細（1行1件）
                summary       TEXT DEFAULT '',
                thumb         TEXT DEFAULT '',
                note          TEXT DEFAULT '',
                created_at    TEXT NOT NULL,
                updated_at    TEXT NOT NULL,
                FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_files_location ON files(location_id);
            CREATE INDEX IF NOT EXISTS idx_files_label    ON files(label);

            -- 取り込みフォルダのパスなど、アプリの設定を1つずつ入れておく
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            );
            """
        )

        # --- 旧形式（documents: 書類1枚ずつ）からの移行 ---
        has_old = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='documents'"
        ).fetchone()
        if has_old:
            rows = conn.execute("SELECT * FROM documents").fetchall()
            for r in rows:
                conn.execute(
                    """INSERT INTO files
                       (label, kind, location_id, spot, properties, doc_types,
                        year_from, year_to, item_count, contents, summary, thumb, note,
                        created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        r["title"], "", r["location_id"], r["container"] or "",
                        r["property_name"] or "", r["doc_type"] or "",
                        (r["doc_date"] or "")[:4], (r["doc_date"] or "")[:4],
                        r["quantity"] or "", r["title"], r["summary"] or "",
                        r["thumb"] or "", r["note"] or "",
                        r["created_at"], r["updated_at"],
                    ),
                )
            conn.execute("DROP TABLE documents")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------- 設定 ----------

def get_setting(key: str, default: str = "") -> str:
    with _connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value or ""),
        )


# ---------- 保管場所 ----------

def list_locations() -> list:
    with _connect() as conn:
        return conn.execute("SELECT * FROM locations ORDER BY sort, name").fetchall()


def add_location(name: str, note: str = ""):
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
    """場所を消してもファイルは残る（location_id が NULL になる）。"""
    with _connect() as conn:
        conn.execute("DELETE FROM locations WHERE id=?", (loc_id,))


def location_counts() -> dict:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT location_id, COUNT(*) AS c FROM files "
            "WHERE location_id IS NOT NULL GROUP BY location_id"
        ).fetchall()
    return {r["location_id"]: r["c"] for r in rows}


# ---------- 物件 ----------

def list_properties() -> list:
    with _connect() as conn:
        return conn.execute("SELECT * FROM properties ORDER BY name").fetchall()


def add_property(name: str, note: str = ""):
    name = (name or "").strip()
    if not name:
        return None
    with _connect() as conn:
        row = conn.execute("SELECT id FROM properties WHERE name = ?", (name,)).fetchone()
        if row:
            return None  # 既存なので新規追加はしていない
        cur = conn.execute(
            "INSERT INTO properties (name, note, created_at) VALUES (?,?,?)",
            (name, note.strip(), _now()),
        )
        return cur.lastrowid


def delete_property(prop_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM properties WHERE id=?", (prop_id,))


# ---------- ファイル（管理の単位） ----------

def add_file(d: dict) -> int:
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO files
               (label, kind, location_id, spot, properties, doc_types,
                year_from, year_to, item_count, contents, summary, thumb, note,
                created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                d.get("label", "").strip() or "（名前なし）",
                d.get("kind", ""),
                d.get("location_id"),
                d.get("spot", "").strip(),
                d.get("properties", "").strip(),
                d.get("doc_types", "").strip(),
                d.get("year_from", "").strip(),
                d.get("year_to", "").strip(),
                d.get("item_count", "").strip(),
                d.get("contents", "").strip(),
                d.get("summary", "").strip(),
                d.get("thumb", ""),
                d.get("note", "").strip(),
                _now(),
                _now(),
            ),
        )
        return cur.lastrowid


def update_file(file_id: int, d: dict) -> None:
    with _connect() as conn:
        conn.execute(
            """UPDATE files SET
               label=?, kind=?, location_id=?, spot=?, properties=?, doc_types=?,
               year_from=?, year_to=?, item_count=?, contents=?, summary=?, note=?, updated_at=?
               WHERE id=?""",
            (
                d.get("label", "").strip() or "（名前なし）",
                d.get("kind", ""),
                d.get("location_id"),
                d.get("spot", "").strip(),
                d.get("properties", "").strip(),
                d.get("doc_types", "").strip(),
                d.get("year_from", "").strip(),
                d.get("year_to", "").strip(),
                d.get("item_count", "").strip(),
                d.get("contents", "").strip(),
                d.get("summary", "").strip(),
                d.get("note", "").strip(),
                _now(),
                file_id,
            ),
        )


def list_unplaced() -> list:
    """保管場所が未設定のファイル。棚番号を後回しにして登録した分がここに溜まる。"""
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM files WHERE location_id IS NULL ORDER BY created_at DESC, label"
        ).fetchall()


def set_location(file_ids: list, location_id, spot: str = "") -> int:
    """複数ファイルの保管場所をまとめて設定する。設定できた件数を返す。"""
    ids = [int(i) for i in file_ids if i]
    if not ids:
        return 0
    with _connect() as conn:
        conn.executemany(
            "UPDATE files SET location_id=?, spot=?, updated_at=? WHERE id=?",
            [(location_id, (spot or "").strip(), _now(), i) for i in ids],
        )
    return len(ids)


def delete_file(file_id: int) -> None:
    with _connect() as conn:
        row = conn.execute("SELECT thumb FROM files WHERE id=?", (file_id,)).fetchone()
        if row and row["thumb"]:
            path = os.path.join(THUMB_DIR, row["thumb"])
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        conn.execute("DELETE FROM files WHERE id=?", (file_id,))


def search_files(
    keyword: str = "",
    doc_type: str = "",
    property_name: str = "",
    location_id=None,
    year: str = "",
) -> list:
    """AND検索。キーワードはスペース区切りで、中身の明細まで含めて横断する。"""
    sql = [
        "SELECT f.*, l.name AS location_name FROM files f "
        "LEFT JOIN locations l ON l.id = f.location_id WHERE 1=1"
    ]
    params: list = []

    for word in (keyword or "").split():
        sql.append(
            " AND (f.label LIKE ? OR f.properties LIKE ? OR f.contents LIKE ?"
            " OR f.summary LIKE ? OR f.doc_types LIKE ? OR f.note LIKE ? OR f.spot LIKE ?)"
        )
        params.extend(["%%%s%%" % word] * 7)

    if doc_type:
        sql.append(" AND f.doc_types LIKE ?")
        params.append("%%%s%%" % doc_type)
    if property_name:
        sql.append(" AND f.properties LIKE ?")
        params.append("%%%s%%" % property_name)
    if location_id:
        sql.append(" AND f.location_id = ?")
        params.append(location_id)
    if year:
        # 年の範囲に含まれるか（年が未入力のファイルは対象外）
        sql.append(
            " AND (f.year_from <> '' AND f.year_from <= ?"
            " AND (f.year_to = '' OR f.year_to >= ?))"
        )
        params.extend([year, year])

    sql.append(" ORDER BY f.label")
    with _connect() as conn:
        return conn.execute("".join(sql), params).fetchall()


def get_file(file_id: int):
    with _connect() as conn:
        return conn.execute(
            "SELECT f.*, l.name AS location_name FROM files f "
            "LEFT JOIN locations l ON l.id = f.location_id WHERE f.id = ?",
            (file_id,),
        ).fetchone()


def stats() -> dict:
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM files").fetchone()["c"]
        locs = conn.execute("SELECT COUNT(*) AS c FROM locations").fetchone()["c"]
        unplaced = conn.execute(
            "SELECT COUNT(*) AS c FROM files WHERE location_id IS NULL"
        ).fetchone()["c"]
        props = conn.execute("SELECT COUNT(*) AS c FROM properties").fetchone()["c"]
    return {"files": total, "locations": locs, "unplaced": unplaced, "properties": props}


def all_doc_types() -> list:
    """既定リスト＋実データで使われている自作の種別。"""
    with _connect() as conn:
        rows = conn.execute("SELECT doc_types FROM files WHERE doc_types <> ''").fetchall()
    used = set()
    for r in rows:
        used.update(t.strip() for t in r["doc_types"].split(",") if t.strip())
    extra = sorted(t for t in used if t not in DEFAULT_DOC_TYPES)
    return DEFAULT_DOC_TYPES + extra
