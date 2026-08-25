"""設定の読み込み。

パスワードを git に入れないため、設定は `.env.mail-archiver`（このフォルダ直下・gitignore）か
環境変数から読む。`.env.mail-archiver.example` を写して使う。

macOS のキーチェーンに入れておくこともできる（平文をディスクに置きたくないとき）:

    security add-generic-password -a shin@daikyocorp.co.jp -s mail-archiver -w
    # .env 側は IMAP_PASSWORD を空にして IMAP_PASSWORD_KEYCHAIN=mail-archiver と書く
"""
from __future__ import annotations

import os
import subprocess
from typing import Dict, Optional

APP_DIR = os.path.dirname(os.path.abspath(__file__))
# 既定の設定ファイル。`MAIL_ARCHIVER_ENV` で1本だけ差し替えられる
ENV_FILE = os.environ.get("MAIL_ARCHIVER_ENV") or os.path.join(APP_DIR, ".env.mail-archiver")
ENV_PREFIX = ".env.mail-archiver."


def _read_env_file(path):
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _setting(key, default):
    """優先順: 環境変数 > .env > 既定値。パスの決定は import 時に済ませる。"""
    return os.environ.get(key) or _read_env_file(ENV_FILE).get(key) or default


# ─────────────────────────────────────────────────────────────────────────────
# 置き場の分離（2026-08-20 決定）
#
#   原本(.eml)・添付・サイドカー  → ARCHIVE_STORE_DIR（**個人Dropbox**を想定）
#   SQLite の索引                → ARCHIVE_DB_PATH（**必ずローカル**）
#
# **DBを同期フォルダに置いてはいけない。** SQLite は本体・WAL・shm の複数ファイルを
# 同時に書くので、書き込み途中でDropboxが持っていくと壊れる。原本は書いたら二度と
# 書き換えない（write-once）ので同期と喧嘩しない。DBが壊れても
# `python3 sync.py --rebuild` で原本から作り直せる。
# ─────────────────────────────────────────────────────────────────────────────
DATA_DIR = (os.environ.get("MAIL_ARCHIVER_DATA_DIR")
            or _setting("ARCHIVE_STORE_DIR", os.path.join(APP_DIR, "data")))
DB_PATH = (os.environ.get("MAIL_ARCHIVER_DB")
           or _setting("ARCHIVE_DB_PATH", os.path.join(APP_DIR, "local", "mail.db")))
RAW_DIR = os.path.join(DATA_DIR, "raw")
ATTACH_DIR = os.path.join(DATA_DIR, "attachments")

DEFAULTS = {
    "MAIL_ACCOUNT": "default",
    "IMAP_HOST": "",
    "IMAP_PORT": "993",
    "IMAP_USER": "",
    "IMAP_PASSWORD": "",
    "IMAP_PASSWORD_KEYCHAIN": "",
    "IMAP_SSL": "1",
    # ssl / starttls / none。空なら「993ならSSL・143ならSTARTTLS」と決める。
    # Apple Mail の「ポート143＋SSLを使う」は STARTTLS のこと（143にSSLで繋ぐと落ちる）
    "IMAP_SECURITY": "",
    # ★削除は既定で無効。有効にしても実行時に --delete --yes が要る（三重の鍵）
    "ARCHIVE_DELETE_ENABLED": "0",
    "ARCHIVE_DELETE_DAYS": "14",
    "ARCHIVE_EXCLUDE_FOLDERS": "Trash,Deleted Messages,Junk,ゴミ箱,迷惑メール",
    # 画面のパスワード。LANに出すときは必須（未設定なら画面を出さない）
    "UI_PASSWORD": "",
}


def _keychain_password(service: str, account: str) -> Optional[str]:
    try:
        r = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
            capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return None


def account_env_files() -> list:
    """設定ファイルを全部返す（既定の1本 ＋ `.env.mail-archiver.<slug>`）。

    アカウントごとに1ファイルにしてある。1本の中に7アカウント分を詰め込むより、
    「どれを使って走らせたか」がコマンドに残るほうが事故が少ない（消す操作があるため）。
    """
    files = []
    if os.path.exists(ENV_FILE):
        files.append(ENV_FILE)
    for name in sorted(os.listdir(APP_DIR)):
        if not name.startswith(ENV_PREFIX) or name.endswith(".example"):
            continue
        path = os.path.join(APP_DIR, name)
        if path not in files:
            files.append(path)
    return files


def env_file_for(slug: str) -> str:
    """`--account <slug>` からファイル名を決める。"""
    path = os.path.join(APP_DIR, ENV_PREFIX + slug)
    if not os.path.exists(path):
        raise FileNotFoundError(
            "そのアカウントの設定がありません: {}\n"
            "いまあるもの: {}".format(
                path, ", ".join(slugs()) or "（なし）"))
    return path


def slugs() -> list:
    out = []
    for p in account_env_files():
        base = os.path.basename(p)
        out.append(base[len(ENV_PREFIX):] if base.startswith(ENV_PREFIX)
                   else (_read_env_file(p).get("MAIL_ACCOUNT") or "default"))
    return out


def load(env_file: Optional[str] = None) -> Dict[str, str]:
    """設定を読む。

    `env_file` を明示したときは**環境変数で上書きしない**。複数アカウントを順に回すとき、
    シェルに残った `IMAP_USER` などが全アカウントに被さって別のサーバーへ
    別のユーザーで繋ぎにいく事故を防ぐため。
    """
    cfg = dict(DEFAULTS)
    cfg.update(_read_env_file(env_file or ENV_FILE))
    if env_file is None:
        for k in DEFAULTS:
            if os.environ.get(k):
                cfg[k] = os.environ[k]
    if not cfg["IMAP_PASSWORD"] and cfg["IMAP_PASSWORD_KEYCHAIN"]:
        pw = _keychain_password(cfg["IMAP_PASSWORD_KEYCHAIN"], cfg["IMAP_USER"])
        if pw:
            cfg["IMAP_PASSWORD"] = pw
    return cfg


def excluded_folders(cfg: Dict[str, str]) -> list:
    return [s.strip() for s in cfg.get("ARCHIVE_EXCLUDE_FOLDERS", "").split(",") if s.strip()]
