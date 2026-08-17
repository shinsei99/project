"""KeyLine のDB層。

ここに置くもの / 置かないもの
    * SQLite への接続と、マイグレーションの適用まではここ
    * 貸出・返却のような業務ロジックは services.py 側（Phase 4）

なぜ SQLite なのか
    社内LAN限定・利用者は自社の社員だけ（同時書き込みは多くて数人）という前提のため。
    サーバーを1台も建てずに済み、バックアップはファイルをコピーするだけで終わる。
    将来 SaaS 化して Postgres へ移すときのために、SQL は PG に寄せて書いてある。
"""

from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
MIGRATIONS_DIR = APP_DIR / "migrations"
DEFAULT_DB_PATH = APP_DIR / "data" / "keyline.db"

# ---------------------------------------------------------------------------
# 時刻とID
#
# 時刻は必ずUTCのISO8601（'2026-08-17T10:32:05.123Z'）で持つ。
# 文字列のまま辞書順で正しく時系列に並ぶので、SQLの比較・ソートがそのまま使える。
# 画面に出すときだけ日本時間へ直す（to_local）。DBには絶対にローカル時刻を入れない
# ——サマータイムの無い日本でも、時刻の意味が曖昧な列は後で必ず事故になる。
#
# ★ミリ秒まで持つ理由（2026-08-17に実際に踏んだ）
#   当初は秒精度だったが、同じ秒に貸出→返却→貸出が起きると ORDER BY checkout_at の
#   順序が決まらず、履歴の最新1件を取り違えた。貸出履歴は監査記録なので、
#   並び順が一意に決まらないのは欠陥。SQLite 側も strftime('%...%fZ') で揃えてある。
#
# ★秒精度とミリ秒精度を混ぜてはいけない。
#   '...05.123Z' < '...05Z'（'.' < 'Z'）となり、文字列比較の順序が壊れる。
# ---------------------------------------------------------------------------
TS_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"   # strptime 用（%f は1〜6桁を受け付ける）
JST = timezone(timedelta(hours=9))


def _fmt(dt: datetime) -> str:
    """DB保存形式にする。ミリ秒3桁で SQLite の strftime('%f') と桁数を揃える。"""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def now_ts() -> str:
    """現在時刻をDB保存形式（UTC・ISO8601・ミリ秒）で返す。"""
    return _fmt(datetime.now(timezone.utc))


def ts_plus(hours: float = 0, days: float = 0, minutes: float = 0) -> str:
    """現在時刻からの相対時刻をDB保存形式で返す（返却予定の既定値などに使う）。"""
    return _fmt(datetime.now(timezone.utc) + timedelta(hours=hours, days=days, minutes=minutes))


def to_local(ts: str | None) -> datetime | None:
    """DBの文字列を日本時間の datetime に直す。表示の直前でだけ使うこと。"""
    if not ts:
        return None
    try:
        dt = datetime.strptime(ts, TS_FMT)
    except ValueError:
        # ミリ秒の無い値が紛れ込んでも表示だけは壊さない（本来は入らないはず）
        dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
    return dt.replace(tzinfo=timezone.utc).astimezone(JST)


def to_utc_ts(dt: datetime) -> str:
    """日本時間などの datetime を DB保存形式（UTC文字列）に直す。"""
    return _fmt(dt.astimezone(timezone.utc))


def fmt_local(ts: str | None, fmt: str = "%Y/%m/%d %H:%M") -> str:
    """画面表示用の文字列にする。値が無ければ '-'。"""
    dt = to_local(ts)
    return dt.strftime(fmt) if dt else "-"


def new_id() -> str:
    """主キー用のUUID。Postgres の uuid 型へそのまま移せる形にしておく。"""
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# 接続
# ---------------------------------------------------------------------------
def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    """接続を作る。**アプリ内でSQLiteを開く経路はこの関数だけにすること。**

    PRAGMA を毎回ここで設定するのが要点。SQLite の外部キーは
    **接続ごとに既定でOFF**で、設定を忘れた接続からは制約が丸ごと効かなくなる。
    """
    path = Path(db_path) if db_path else Path(os.environ.get("KEYLINE_DB", DEFAULT_DB_PATH))
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(
        str(path),
        # 貸出が重なったときに即エラーを返さず、最大5秒は書き込みロックを待つ
        timeout=5.0,
        isolation_level=None,  # 自動コミットを切り、トランザクションを自分で張る
    )
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")     # ★接続ごとに必要
    con.execute("PRAGMA journal_mode = WAL")    # 読み取りが書き込みでブロックされない
    con.execute("PRAGMA synchronous = NORMAL")
    con.execute("PRAGMA busy_timeout = 5000")
    return con


class Conflict(Exception):
    """他の人に先を越された（二重貸出・二重返却）。呼び出し側が現場向けの文言に直す。"""


# ---------------------------------------------------------------------------
# マイグレーション
# ---------------------------------------------------------------------------
def migrate(con: sqlite3.Connection, migrations_dir: Path | None = None) -> list[str]:
    """未適用の .sql を名前順に当てる。適用したファイル名を返す。"""
    d = migrations_dir or MIGRATIONS_DIR
    con.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
               filename   TEXT PRIMARY KEY,
               applied_at TEXT NOT NULL
           )"""
    )
    done = {r["filename"] for r in con.execute("SELECT filename FROM schema_migrations")}
    applied: list[str] = []
    for f in sorted(d.glob("*.sql")):
        if f.name in done:
            continue

        # 1ファイル＝1トランザクション。途中で落ちたら中途半端な形で残さない。
        #
        # ★BEGIN / COMMIT を **スクリプトの中に書く**のが要点。
        #   executescript() は「実行前に暗黙のCOMMITを発行する」仕様なので、
        #   con.execute("BEGIN") で外から囲んでも、その場でトランザクションが
        #   閉じてしまい 'cannot commit - no transaction is active' で落ちる。
        #   適用済みの記録まで同じスクリプトに入れて、DDLと記録を一括で確定させる。
        #   （SQLite は DDL もトランザクションに入るので、失敗すれば全部戻る）
        fname = f.name.replace("'", "''")
        script = (
            "BEGIN;\n"
            f"{f.read_text(encoding='utf-8')}\n"
            f"INSERT INTO schema_migrations (filename, applied_at)"
            f" VALUES ('{fname}', '{now_ts()}');\n"
            "COMMIT;"
        )
        con.executescript(script)
        applied.append(f.name)
    return applied


def get_db(db_path: str | Path | None = None) -> sqlite3.Connection:
    """接続して、必要ならマイグレーションまで済ませた接続を返す。"""
    con = connect(db_path)
    migrate(con)
    return con


if __name__ == "__main__":
    import sys

    con = connect(sys.argv[1] if len(sys.argv) > 1 else None)
    applied = migrate(con)
    print(f"適用: {applied if applied else '（なし・最新です）'}")
    tables = [r["name"] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )]
    print("テーブル:", ", ".join(tables))
