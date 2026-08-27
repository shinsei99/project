"""メールアーカイバのデータベース層（SQLite）。

設計の要点:

- **本文の原本は .eml ファイル**（`data/raw/<account>/<folder>/<uid>.eml`）。DBには検索・一覧に
  必要な情報と、原本への相対パス・SHA256 を持つ。サーバーから消す判断は「原本がディスクに
  実在し、SHA256 が一致すること」を毎回その場で確かめてから行う（DBの行があるだけでは消さない）。
- **UIDVALIDITY を必ず持つ。** IMAP の UID はフォルダの UIDVALIDITY が変わると意味が変わる。
  ここを見ずに UID で消すと **まったく別のメールを消す**。messages の一意キーに含めている。
- 全文検索は FTS5 の **trigram** トークナイザ。日本語は空白で区切られないため unicode61 では
  「請求書」のような部分一致が取れない。trigram は3文字以上の部分一致が効く（SQLite 3.34+）。
  2文字以下の語は LIKE にフォールバックする（`search()` が自動で振り分ける）。
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

SCHEMA_VERSION = 1

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
  id         INTEGER PRIMARY KEY,
  name       TEXT NOT NULL UNIQUE,   -- 設定上の呼び名（例: shin）
  host       TEXT NOT NULL,
  port       INTEGER NOT NULL DEFAULT 993,
  username   TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS folders (
  id             INTEGER PRIMARY KEY,
  account_id     INTEGER NOT NULL REFERENCES accounts(id),
  raw_name       TEXT NOT NULL,      -- IMAP修正UTF-7。サーバーへ送る名前
  name           TEXT NOT NULL,      -- 表示用（UTF-8にデコード済み）
  uidvalidity    INTEGER,
  last_seen_uid  INTEGER NOT NULL DEFAULT 0,
  last_synced_at TEXT,
  UNIQUE(account_id, raw_name)
);

CREATE TABLE IF NOT EXISTS messages (
  id                INTEGER PRIMARY KEY,
  account_id        INTEGER NOT NULL REFERENCES accounts(id),
  folder_id         INTEGER NOT NULL REFERENCES folders(id),
  uid               INTEGER NOT NULL,
  uidvalidity       INTEGER NOT NULL,
  message_id        TEXT,             -- Message-ID ヘッダ。削除直前の本人確認に使う
  subject           TEXT,
  from_name         TEXT,
  from_addr         TEXT,
  to_addrs          TEXT,
  cc_addrs          TEXT,
  date_utc          TEXT,             -- ISO8601(UTC)。文字列のまま並べ替えられる形
  size_bytes        INTEGER NOT NULL DEFAULT 0,
  flags             TEXT,
  body_text         TEXT,             -- 検索・表示用の平文（原本は raw_path）
  has_attachments   INTEGER NOT NULL DEFAULT 0,
  raw_path          TEXT NOT NULL,    -- data/ からの相対パス
  raw_sha256        TEXT NOT NULL,
  synced_at         TEXT NOT NULL,    -- ★ローカルへ取り込んだ日時（UTC ISO8601）
  server_state      TEXT NOT NULL DEFAULT 'present',  -- present / deleted / gone / local
                                                    --   local = Mail.app から取り込んだIMAP管理外。
                                                    --   削除候補（present）に一生入らない
  server_deleted_at TEXT,
  UNIQUE(account_id, folder_id, uidvalidity, uid)
);

CREATE INDEX IF NOT EXISTS idx_messages_synced   ON messages(synced_at);
CREATE INDEX IF NOT EXISTS idx_messages_date     ON messages(date_utc DESC);
CREATE INDEX IF NOT EXISTS idx_messages_from     ON messages(from_addr);
CREATE INDEX IF NOT EXISTS idx_messages_state    ON messages(server_state);
CREATE INDEX IF NOT EXISTS idx_messages_msgid    ON messages(message_id);

CREATE TABLE IF NOT EXISTS attachments (
  id           INTEGER PRIMARY KEY,
  message_id   INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  filename     TEXT NOT NULL,
  content_type TEXT,
  size_bytes   INTEGER NOT NULL DEFAULT 0,
  path         TEXT NOT NULL,        -- data/ からの相対パス
  sha256       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attachments_msg ON attachments(message_id);

-- サーバー側で何を消したかの台帳。消したあとで「本当に手元にあるか」を追える
CREATE TABLE IF NOT EXISTS delete_log (
  id           INTEGER PRIMARY KEY,
  message_row  INTEGER,              -- messages.id（行が消えても記録は残す）
  account_id   INTEGER NOT NULL,
  folder       TEXT NOT NULL,
  uid          INTEGER NOT NULL,
  uidvalidity  INTEGER NOT NULL,
  msgid_header TEXT,
  subject      TEXT,
  size_bytes   INTEGER,
  raw_path     TEXT,
  raw_sha256   TEXT,
  mode         TEXT NOT NULL,        -- dry-run / deleted / skipped
  reason       TEXT,
  at           TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_delete_log_at ON delete_log(at DESC);

CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
  subject, addrs, body, tokenize='trigram'
);

-- 意味検索用のベクトル。1メール1行（モデルを変えたら作り直す前提で model も持つ）。
-- vec は float32 を正規化して並べた生バイト（コサイン=内積で引ける）。
CREATE TABLE IF NOT EXISTS embeddings (
  message_id INTEGER PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
  model      TEXT NOT NULL,
  dim        INTEGER NOT NULL,
  vec        BLOB NOT NULL,
  made_at    TEXT NOT NULL
);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def connect(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    # check_same_thread=False … Streamlit は再実行のたびに別スレッドで動くことがあり、
    # 使い回した接続が「SQLite objects created in a thread can only be used in that same
    # thread」で落ちる（2026-08-20に実データで発生）。書き込みは短いトランザクションだけで、
    # 実質1人しか触らないので、SQLite自身のロックに任せてスレッド制限を外す
    conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO meta(key, value) VALUES('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()


# ---------------------------------------------------------------- accounts

def upsert_account(conn: sqlite3.Connection, name: str, host: str, port: int, username: str) -> int:
    cur = conn.execute("SELECT id FROM accounts WHERE name=?", (name,))
    row = cur.fetchone()
    if row:
        conn.execute(
            "UPDATE accounts SET host=?, port=?, username=? WHERE id=?",
            (host, port, username, row["id"]),
        )
        conn.commit()
        return int(row["id"])
    cur = conn.execute(
        "INSERT INTO accounts(name, host, port, username, created_at) VALUES(?,?,?,?,?)",
        (name, host, port, username, utcnow()),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_accounts(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    return conn.execute("SELECT * FROM accounts ORDER BY name").fetchall()


# ---------------------------------------------------------------- folders

def upsert_folder(conn: sqlite3.Connection, account_id: int, raw_name: str, name: str) -> sqlite3.Row:
    conn.execute(
        "INSERT OR IGNORE INTO folders(account_id, raw_name, name) VALUES(?,?,?)",
        (account_id, raw_name, name),
    )
    conn.commit()
    return conn.execute(
        "SELECT * FROM folders WHERE account_id=? AND raw_name=?", (account_id, raw_name)
    ).fetchone()


def set_folder_uidvalidity(conn: sqlite3.Connection, folder_id: int, uidvalidity: int) -> None:
    conn.execute("UPDATE folders SET uidvalidity=? WHERE id=?", (uidvalidity, folder_id))
    conn.commit()


def update_folder_progress(conn: sqlite3.Connection, folder_id: int, last_uid: int) -> None:
    conn.execute(
        "UPDATE folders SET last_seen_uid=MAX(last_seen_uid, ?), last_synced_at=? WHERE id=?",
        (last_uid, utcnow(), folder_id),
    )
    conn.commit()


def list_folders(conn: sqlite3.Connection, account_id: Optional[int] = None) -> List[sqlite3.Row]:
    if account_id is None:
        return conn.execute("SELECT * FROM folders ORDER BY name").fetchall()
    return conn.execute(
        "SELECT * FROM folders WHERE account_id=? ORDER BY name", (account_id,)
    ).fetchall()


# ---------------------------------------------------------------- messages

def message_exists(conn: sqlite3.Connection, account_id: int, folder_id: int,
                   uidvalidity: int, uid: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM messages WHERE account_id=? AND folder_id=? AND uidvalidity=? AND uid=?",
        (account_id, folder_id, uidvalidity, uid),
    ).fetchone()
    return row is not None


def insert_message(conn: sqlite3.Connection, m: Dict[str, Any]) -> int:
    """1通を登録する。**同じトランザクションで FTS も入れる**（片方だけ入る状態を作らない）。"""
    cols = ("account_id", "folder_id", "uid", "uidvalidity", "message_id", "subject",
            "from_name", "from_addr", "to_addrs", "cc_addrs", "date_utc", "size_bytes",
            "flags", "body_text", "has_attachments", "raw_path", "raw_sha256", "synced_at",
            "server_state", "server_deleted_at")
    cur = conn.execute(
        "INSERT INTO messages ({}) VALUES ({})".format(
            ",".join(cols), ",".join("?" * len(cols))),
        tuple(m.get(c) if c != "server_state" else (m.get("server_state") or "present")
              for c in cols),
    )
    mid = int(cur.lastrowid)
    addrs = " ".join(filter(None, [m.get("from_name") or "", m.get("from_addr") or "",
                                   m.get("to_addrs") or "", m.get("cc_addrs") or ""]))
    conn.execute(
        "INSERT INTO messages_fts(rowid, subject, addrs, body) VALUES(?,?,?,?)",
        (mid, m.get("subject") or "", addrs, m.get("body_text") or ""),
    )
    return mid


def insert_attachment(conn: sqlite3.Connection, message_row: int, filename: str,
                      content_type: str, size_bytes: int, path: str, sha256: str) -> None:
    conn.execute(
        "INSERT INTO attachments(message_id, filename, content_type, size_bytes, path, sha256) "
        "VALUES(?,?,?,?,?,?)",
        (message_row, filename, content_type, size_bytes, path, sha256),
    )


def attachments_of(conn: sqlite3.Connection, message_row: int) -> List[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM attachments WHERE message_id=? ORDER BY filename", (message_row,)
    ).fetchall()


# ---------------------------------------------------------------- 検索

def search(conn: sqlite3.Connection, q: str = "", sender: str = "",
           folder_id: Optional[int] = None, account_id: Optional[int] = None,
           date_from: str = "", date_to: str = "",
           state: str = "all", has_attach: bool = False,
           direction: str = "all", fts_expr: str = "",
           limit: int = 200, offset: int = 0) -> Tuple[List[sqlite3.Row], int]:
    """全文検索＋絞り込み。戻り値は (行, 総件数)。

    q は3文字以上なら FTS5(trigram)、2文字以下なら LIKE を使う（trigramは3文字未満を索引できない）。
    fts_expr を渡すと、q の代わりに**生の FTS5 MATCH 式**をそのまま使う
    （AI検索が組み立てる `"水道局" AND ("質疑" OR "協議")` のような式を通すため）。
    """
    where: List[str] = []
    params: List[Any] = []
    join = ""
    order = "m.date_utc DESC"

    q = (q or "").strip()
    fts_expr = (fts_expr or "").strip()
    if fts_expr:
        join = "JOIN messages_fts f ON f.rowid = m.id"
        where.append("messages_fts MATCH ?")
        params.append(fts_expr)
    elif q:
        if len(q) >= 3:
            join = "JOIN messages_fts f ON f.rowid = m.id"
            where.append("messages_fts MATCH ?")
            params.append('"' + q.replace('"', '""') + '"')
            order = "m.date_utc DESC"
        else:
            like = "%" + q + "%"
            where.append("(m.subject LIKE ? OR m.body_text LIKE ? OR m.from_addr LIKE ?)")
            params += [like, like, like]

    if sender.strip():
        like = "%" + sender.strip() + "%"
        where.append("(m.from_addr LIKE ? OR m.from_name LIKE ?)")
        params += [like, like]
    if folder_id:
        where.append("m.folder_id=?")
        params.append(folder_id)
    if account_id:
        where.append("m.account_id=?")
        params.append(account_id)
    if date_from:
        where.append("m.date_utc >= ?")
        params.append(date_from)
    if date_to:
        where.append("m.date_utc <= ?")
        params.append(date_to)
    if state in ("present", "deleted", "gone", "local"):
        where.append("m.server_state=?")
        params.append(state)
    if has_attach:
        where.append("m.has_attachments=1")

    # 受信／送信の絞り込み。サーバーごとにフォルダ名が違う（Sent / Sent Messages /
    # Sent Items / INBOX.Sent / 送信済み …）ので、フォルダ名で判定する。
    # 送信 = 名前に sent または 送信 を含む。受信 = 送信でも下書きでもないフォルダ全部
    # （daikyocorp は受信を独自フォルダに振り分けているため「INBOX だけ」にはできない）。
    SENT_LIKE = "(LOWER(name) LIKE '%sent%' OR name LIKE '%送信%')"
    DRAFT_LIKE = "(LOWER(name) LIKE '%draft%' OR name LIKE '%下書き%')"
    if direction == "sent":
        where.append("m.folder_id IN (SELECT id FROM folders WHERE " + SENT_LIKE + ")")
    elif direction == "received":
        where.append("m.folder_id IN (SELECT id FROM folders WHERE NOT " +
                     SENT_LIKE + " AND NOT " + DRAFT_LIKE + ")")

    sql_where = ("WHERE " + " AND ".join(where)) if where else ""
    base = "FROM messages m {join} {w}".format(join=join, w=sql_where)

    total = conn.execute("SELECT COUNT(*) AS c " + base, params).fetchone()["c"]
    rows = conn.execute(
        "SELECT m.*, fo.name AS folder_name, a.name AS account_name " + base.replace(
            "FROM messages m", "FROM messages m JOIN folders fo ON fo.id=m.folder_id "
                               "JOIN accounts a ON a.id=m.account_id") +
        " ORDER BY {} LIMIT ? OFFSET ?".format(order),
        params + [limit, offset],
    ).fetchall()
    return rows, int(total)


def get_message(conn: sqlite3.Connection, message_row: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT m.*, fo.name AS folder_name, fo.raw_name AS folder_raw, a.name AS account_name "
        "FROM messages m JOIN folders fo ON fo.id=m.folder_id JOIN accounts a ON a.id=m.account_id "
        "WHERE m.id=?", (message_row,)
    ).fetchone()


# ---------------------------------------------------------------- 削除候補

def deletable_candidates(conn: sqlite3.Connection, account_id: int, days: int,
                         folder_id: Optional[int] = None,
                         keep_flagged: bool = True, keep_unseen: bool = True,
                         before_date: str = "",
                         limit: Optional[int] = None) -> List[sqlite3.Row]:
    """`synced_at` から days 日以上が経ち、まだサーバーに在ると記録されているメールを返す。

    before_date を渡すと、さらに「メールの日付（date_utc）がそれより前」のものだけに絞る。
    サーバーの保存期間を「直近1年」にする用途（1年より前をサーバーから消す）で使う。

    ここで返るのは**候補**。実際に消してよいかは sync.py 側で
    「原本ファイルの実在」「SHA256一致」「UIDVALIDITY一致」「Message-ID一致」を確かめて決める。
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    sql = ["SELECT m.*, fo.raw_name AS folder_raw, fo.name AS folder_name, "
           "fo.uidvalidity AS folder_uidvalidity FROM messages m "
           "JOIN folders fo ON fo.id=m.folder_id "
           "WHERE m.account_id=? AND m.server_state='present' AND m.synced_at <= ?"]
    params: List[Any] = [account_id, cutoff]
    if before_date:
        # date_utc が空（日付不明）のメールは「1年より前」と断定できないので消さない
        sql.append("AND m.date_utc IS NOT NULL AND m.date_utc <> '' AND m.date_utc < ?")
        params.append(before_date)
    if folder_id:
        sql.append("AND m.folder_id=?")
        params.append(folder_id)
    if keep_flagged:
        sql.append("AND (m.flags IS NULL OR m.flags NOT LIKE '%\\Flagged%')")
    if keep_unseen:
        sql.append("AND (m.flags LIKE '%\\Seen%')")
    sql.append("ORDER BY m.folder_id, m.uid")
    if limit:
        sql.append("LIMIT {}".format(int(limit)))
    return conn.execute(" ".join(sql), params).fetchall()


def mark_server_deleted(conn: sqlite3.Connection, message_row: int) -> None:
    conn.execute(
        "UPDATE messages SET server_state='deleted', server_deleted_at=? WHERE id=?",
        (utcnow(), message_row),
    )


def mark_server_gone(conn: sqlite3.Connection, message_row: int) -> None:
    """サーバー側に既に無かった（他の端末が消した等）。ローカルは残す。"""
    conn.execute("UPDATE messages SET server_state='gone' WHERE id=?", (message_row,))


def log_delete(conn: sqlite3.Connection, row: sqlite3.Row, mode: str, reason: str = "") -> None:
    conn.execute(
        "INSERT INTO delete_log(message_row, account_id, folder, uid, uidvalidity, msgid_header,"
        " subject, size_bytes, raw_path, raw_sha256, mode, reason, at)"
        " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (row["id"], row["account_id"], row["folder_name"] if "folder_name" in row.keys() else "",
         row["uid"], row["uidvalidity"], row["message_id"], row["subject"], row["size_bytes"],
         row["raw_path"], row["raw_sha256"], mode, reason, utcnow()),
    )


def recent_delete_log(conn: sqlite3.Connection, limit: int = 200) -> List[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM delete_log ORDER BY at DESC, id DESC LIMIT ?", (limit,)
    ).fetchall()


def stats(conn: sqlite3.Connection) -> Dict[str, Any]:
    r = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(size_bytes),0) AS bytes FROM messages"
    ).fetchone()
    present = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(size_bytes),0) AS bytes "
        "FROM messages WHERE server_state='present'"
    ).fetchone()
    deleted = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(size_bytes),0) AS bytes "
        "FROM messages WHERE server_state='deleted'"
    ).fetchone()
    att = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(size_bytes),0) AS bytes FROM attachments"
    ).fetchone()
    return {
        "messages": r["n"], "bytes": r["bytes"],
        "present": present["n"], "present_bytes": present["bytes"],
        "deleted": deleted["n"], "deleted_bytes": deleted["bytes"],
        "attachments": att["n"], "attachment_bytes": att["bytes"],
    }


# ---------------------------------------------------------------- 意味検索ベクトル

def messages_missing_embedding(conn: sqlite3.Connection, model: str,
                               limit: int = 1000) -> List[sqlite3.Row]:
    """まだこのモデルのベクトルが無いメールを返す（件名・本文つき）。"""
    return conn.execute(
        "SELECT m.id, m.subject, m.body_text FROM messages m "
        "LEFT JOIN embeddings e ON e.message_id = m.id AND e.model = ? "
        "WHERE e.message_id IS NULL ORDER BY m.id LIMIT ?",
        (model, limit),
    ).fetchall()


def store_embeddings(conn: sqlite3.Connection, model: str, dim: int,
                     items: List[Tuple[int, bytes]]) -> None:
    """items = [(message_id, vec_bytes), ...] をまとめて保存（既存は置き換え）。"""
    now = utcnow()
    conn.executemany(
        "INSERT INTO embeddings(message_id, model, dim, vec, made_at) "
        "VALUES(?,?,?,?,?) ON CONFLICT(message_id) DO UPDATE SET "
        "model=excluded.model, dim=excluded.dim, vec=excluded.vec, made_at=excluded.made_at",
        [(mid, model, dim, vec, now) for mid, vec in items],
    )
    conn.commit()


def embedding_count(conn: sqlite3.Connection, model: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) AS n FROM embeddings WHERE model=?", (model,)
    ).fetchone()["n"]


def load_all_embeddings(conn: sqlite3.Connection, model: str) -> Tuple[List[int], List[bytes]]:
    """このモデルの全ベクトルを (message_idの列, vecバイトの列) で返す。"""
    ids: List[int] = []
    vecs: List[bytes] = []
    for row in conn.execute(
            "SELECT message_id, vec FROM embeddings WHERE model=? ORDER BY message_id",
            (model,)):
        ids.append(row["message_id"])
        vecs.append(row["vec"])
    return ids, vecs


def messages_by_ids(conn: sqlite3.Connection, ids: List[int]) -> List[sqlite3.Row]:
    """id のリストで本文つきに引き直す（順序は呼び出し側で並べ替える）。"""
    if not ids:
        return []
    marks = ",".join("?" for _ in ids)
    return conn.execute(
        "SELECT m.*, fo.name AS folder_name, a.name AS account_name "
        "FROM messages m JOIN folders fo ON fo.id=m.folder_id "
        "JOIN accounts a ON a.id=m.account_id WHERE m.id IN ({})".format(marks),
        ids,
    ).fetchall()
