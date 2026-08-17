"""KeyLine の認証。

方針（2026-08-17確定）
    * 社内LAN限定なので外部の認証基盤は使わない。パスワードは自前で持つ
    * 鍵管理用スマホは operator アカウントで**ログインしっぱなし**にする。
      現場で毎回ログインさせない（そのために有効期限を長く取る）
    * 管理者は admin。管理対象の登録・編集、強制返却、利用者管理ができる

なぜセッションをDBに持つか
    署名付きCookieだけだと「発行済みのCookieを後から無効にする」ことができない。
    鍵管理スマホを紛失したときに、その端末だけを即座に締め出せる必要がある。
    → sessions テーブルの行を消せば、そのCookieはその瞬間から使えなくなる。
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from typing import Optional

import db as dbmod

# ---------------------------------------------------------------------------
# パスワード
#
# PBKDF2-HMAC-SHA256。標準ライブラリだけで完結し、追加の依存が要らない。
# 反復回数は保存する文字列に含めるので、後から増やしても古いハッシュを検証できる。
# ---------------------------------------------------------------------------
PBKDF2_ITERATIONS = 480_000     # 2026年時点の目安。上げても既存ハッシュは壊れない
SALT_BYTES = 16


def hash_password(password: str) -> str:
    """'pbkdf2_sha256$<反復回数>$<salt hex>$<hash hex>' の形で返す。"""
    salt = secrets.token_bytes(SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """照合。**必ず compare_digest を使う**（== だとタイミング攻撃の的になる）。"""
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(),
                                 bytes.fromhex(salt_hex), int(iters))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(dk.hex(), hash_hex)


# ---------------------------------------------------------------------------
# セッション
# ---------------------------------------------------------------------------
COOKIE_NAME = "keyline_session"

# 鍵管理スマホはログインしっぱなしにしたいので長く取る。
# 社内LAN内でしか到達できず、盗まれた端末はDBの行を消せば即座に止められる。
SESSION_DAYS = 365


def create_session(con: sqlite3.Connection, user_id: str,
                   user_agent: Optional[str] = None, days: int = SESSION_DAYS) -> str:
    """セッションを作ってトークンを返す。トークンはそのままCookieの値になる。"""
    token = secrets.token_hex(32)          # 256bit。総当たりは現実的に不可能
    con.execute(
        "INSERT INTO sessions (id, user_id, expires_at, user_agent) VALUES (?,?,?,?)",
        (token, user_id, dbmod.ts_plus(days=days), (user_agent or "")[:300]),
    )
    return token


def login(con: sqlite3.Connection, email: str, password: str,
          user_agent: Optional[str] = None) -> Optional[str]:
    """メールとパスワードで認証し、成功ならセッショントークンを返す。失敗は None。

    ★利用者が存在しない場合もダミーのハッシュ検証を通す。
      「即座に失敗が返る＝そのメールは存在しない」と分かってしまうのを防ぐため。
    """
    row = con.execute(
        "SELECT id, password_hash, is_active FROM users WHERE email = ?", (email.strip().lower(),)
    ).fetchone()

    if row is None:
        verify_password(password, hash_password("dummy"))   # 応答時間を揃える
        return None
    if not row["is_active"]:
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    return create_session(con, row["id"], user_agent)


def current_user(con: sqlite3.Connection, token: Optional[str]) -> Optional[sqlite3.Row]:
    """Cookieのトークンから利用者を引く。無効・期限切れ・停止中なら None。

    ここが全アクセス制御の入口。**organization_id もここで確定させ、
    クライアントから送られてきた組織IDは一切信用しない。**
    """
    if not token:
        return None
    row = con.execute(
        """SELECT u.*, s.id AS session_id, s.expires_at
             FROM sessions s JOIN users u ON u.id = s.user_id
            WHERE s.id = ? AND s.expires_at > ? AND u.is_active = 1""",
        (token, dbmod.now_ts()),
    ).fetchone()
    if row is None:
        return None
    # 最終アクセス時刻の更新は1時間に1回で十分（毎回書くとWALが無駄に膨らむ）
    con.execute(
        "UPDATE sessions SET last_seen_at = ? WHERE id = ? AND last_seen_at < ?",
        (dbmod.now_ts(), token, dbmod.ts_plus(hours=-1)),
    )
    return row


def logout(con: sqlite3.Connection, token: Optional[str]) -> None:
    if token:
        con.execute("DELETE FROM sessions WHERE id = ?", (token,))


def purge_expired_sessions(con: sqlite3.Connection) -> int:
    """期限切れセッションの掃除。起動時に1回呼ぶ。"""
    cur = con.execute("DELETE FROM sessions WHERE expires_at <= ?", (dbmod.now_ts(),))
    return cur.rowcount or 0


# ---------------------------------------------------------------------------
# 利用者の作成
# ---------------------------------------------------------------------------
def create_user(con: sqlite3.Connection, organization_id: str, email: str,
                password: str, display_name: str, role: str = "operator") -> str:
    if role not in ("admin", "operator"):
        raise ValueError(f"不正な役割: {role}")
    uid = dbmod.new_id()
    con.execute(
        """INSERT INTO users (id, organization_id, email, password_hash, display_name, role)
           VALUES (?,?,?,?,?,?)""",
        (uid, organization_id, email.strip().lower(), hash_password(password),
         display_name.strip(), role),
    )
    return uid


def set_password(con: sqlite3.Connection, user_id: str, password: str) -> None:
    con.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                (hash_password(password), user_id))
    # パスワードを変えたら、その利用者の既存セッションは全部切る
    con.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


# ---------------------------------------------------------------------------
# アプリの署名鍵（フラッシュメッセージなどに使う）
# ---------------------------------------------------------------------------
def get_secret_key() -> bytes:
    """`.secret_key` を読む。無ければ作る。**gitignore 済み。**"""
    path = dbmod.APP_DIR / ".secret_key"
    if not path.exists():
        path.write_bytes(secrets.token_bytes(32))
        os.chmod(path, 0o600)
    return path.read_bytes()
