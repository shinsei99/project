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
ENV_FILE = os.path.join(APP_DIR, ".env.mail-archiver")


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


def load() -> Dict[str, str]:
    cfg = dict(DEFAULTS)
    cfg.update(_read_env_file(ENV_FILE))
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
