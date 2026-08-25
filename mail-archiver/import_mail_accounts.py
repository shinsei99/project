#!/usr/bin/env python3
"""macOS標準メール（Mail.app）に登録されているアカウント設定を丸ごと取り込む。

    python3 import_mail_accounts.py --list      # 何があるか見るだけ（書かない）
    python3 import_mail_accounts.py             # 設定ファイルを作る
    python3 import_mail_accounts.py --force     # 既にあるファイルも作り直す

**取り込むのは接続設定だけで、パスワードは取らない。** Mail.app のパスワードは
ログインキーチェーンに入っているが、他のプロセスから読むには**その都度キーチェーンの
許可ダイアログ**が要る（人が押すもの）。ここでは `IMAP_PASSWORD_KEYCHAIN=mail-archiver`
と書いておき、実際の値は人が1回だけ登録する:

    security add-generic-password -s mail-archiver -a <メールアドレス> -w

※ このコマンドは**ターミナル.app から直接**叩く。Claude Code の `!` から叩くと
   入力待ちが効かず**空パスワードで登録される**（2026-08-24に実際に踏んだ）。

アカウント1つにつき `.env.mail-archiver.<slug>` を1本作る。1本の設定に7アカウントを
詰め込まないのは、消す操作（`sync.py --delete`）が**どのアカウントに対する操作か**を
コマンドに残したいため。
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

import config
import db

APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Mail.app に「アカウント種別」を聞くAppleScript。1行1アカウントでタブ区切りで返す
SCRIPT = '''
tell application "Mail"
  set out to ""
  repeat with a in every account
    set aType to (account type of a) as text
    set aEnabled to (enabled of a) as text
    set aUser to ""
    try
      set aUser to user name of a
    end try
    set aServer to ""
    try
      set aServer to server name of a
    end try
    set aPort to ""
    try
      set aPort to (port of a) as text
    end try
    set aSSL to ""
    try
      set aSSL to (uses ssl of a) as text
    end try
    set aAddr to ""
    try
      set aAddr to (item 1 of (email addresses of a)) as text
    end try
    set out to out & (name of a) & tab & aType & tab & aEnabled & tab & aUser & tab & ¬
      aServer & tab & aPort & tab & aSSL & tab & aAddr & linefeed
  end repeat
  return out
end tell'''


def slugify(name: str) -> str:
    """ファイル名に使える形へ。日本語アカウント名も考えられるので英数以外は落とす。"""
    s = re.sub(r"[^0-9A-Za-z._-]+", "-", name).strip("-.").lower()
    return s or "account"


def read_accounts() -> list:
    r = subprocess.run(["osascript", "-e", SCRIPT], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError("Mail.app に問い合わせできません: {}".format(r.stderr.strip()))
    rows = []
    for line in r.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        while len(parts) < 8:
            parts.append("")
        name, atype, enabled, user, server, port, ssl, addr = [p.strip() for p in parts[:8]]
        rows.append({
            "name": name, "type": atype, "enabled": enabled.lower() == "true",
            "user": user, "server": server, "port": port or "993",
            "ssl": ssl.lower() == "true", "address": addr or user,
        })
    return rows


def security_of(port: str, ssl: bool) -> str:
    """Apple Mail の「ポート＋SSLを使う」を、こちらの言葉に直す。

    143 で「SSLを使う」は **STARTTLS**（平文で繋いでから暗号化に切り替える）。
    143 に最初からSSLで繋ぐと必ず失敗するので、ここで分けておく。
    """
    if not ssl:
        return "none"
    return "starttls" if str(port) == "143" else "ssl"


TEMPLATE = """# {name}（Mail.app の設定から取り込み・{stamp}）
# アカウント種別: {atype}{disabled}
MAIL_ACCOUNT={slug}
IMAP_HOST={host}
IMAP_PORT={port}
IMAP_USER={user}
IMAP_SSL={ssl}
IMAP_SECURITY={security}

# パスワードは平文で置かない。下を**ターミナル.appから**1回だけ実行して入れる:
#   security add-generic-password -s mail-archiver -a {user} -w
IMAP_PASSWORD=
IMAP_PASSWORD_KEYCHAIN=mail-archiver

# ★削除は既定で無効。有効にしても実行時に --delete --yes が要る（三重の鍵）
ARCHIVE_DELETE_ENABLED=0
ARCHIVE_DELETE_DAYS=14
ARCHIVE_EXCLUDE_FOLDERS=Trash,Deleted Messages,Junk,ゴミ箱,迷惑メール,Sent Messages,Drafts

# 置き場は全アカウント共通（原本は個人Dropbox・索引はローカル）
ARCHIVE_STORE_DIR={store}
ARCHIVE_DB_PATH={dbpath}
"""


def main() -> int:
    p = argparse.ArgumentParser(description="Mail.app のアカウント設定を取り込む")
    p.add_argument("--list", action="store_true", help="一覧を見るだけ（ファイルを書かない）")
    p.add_argument("--force", action="store_true", help="既にある設定ファイルも作り直す")
    p.add_argument("--include-disabled", action="store_true", help="無効なアカウントも取り込む")
    p.add_argument("--db", default=config.DB_PATH)
    args = p.parse_args()

    accounts = read_accounts()
    if not accounts:
        print("Mail.app にアカウントがありません。")
        return 1

    base = config.load()                      # 既定の .env.mail-archiver（既に設定済みの1本）
    base_user = (base.get("IMAP_USER") or "").lower()
    stamp = subprocess.run(["date", "+%Y-%m-%d"], capture_output=True, text=True).stdout.strip()

    print("Mail.app のアカウント {} 件".format(len(accounts)))
    made, skipped, need_pw = [], [], []
    for a in accounts:
        sec = security_of(a["port"], a["ssl"])
        mark = "" if a["enabled"] else "（無効）"
        print("  {:<20} {:<28} {}:{} {}{}".format(
            a["name"], a["user"] or "-", a["server"] or "-", a["port"], sec, mark))
        if args.list:
            continue
        if not a["enabled"] and not args.include_disabled:
            skipped.append((a["name"], "Mail.app 側で無効"))
            continue
        if not a["server"] or not a["user"]:
            skipped.append((a["name"], "サーバーかユーザー名が空"))
            continue
        if a["user"].lower() == base_user:
            skipped.append((a["name"], ".env.mail-archiver に設定済み"))
            continue

        slug = slugify(a["name"])
        path = os.path.join(APP_DIR, config.ENV_PREFIX + slug)
        if os.path.exists(path) and not args.force:
            skipped.append((a["name"], "既にある（--force で作り直す）"))
            continue
        text = TEMPLATE.format(
            name=a["name"], stamp=stamp, atype=a["type"],
            disabled="" if a["enabled"] else " ※Mail.app では無効",
            slug=slug, host=a["server"], port=a["port"], user=a["user"],
            ssl="1" if a["ssl"] else "0", security=sec,
            store=base.get("ARCHIVE_STORE_DIR") or config.DATA_DIR,
            dbpath=base.get("ARCHIVE_DB_PATH") or config.DB_PATH)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(path, 0o600)                 # 接続先を他人に見せない
        made.append((slug, a["user"]))

    if args.list:
        return 0

    # DBのアカウント表にも入れておく（画面の「アカウント」絞り込みに出す）
    conn = db.connect(args.db)
    db.init_schema(conn)
    for path in config.account_env_files():
        c = config.load(path)
        if not c.get("IMAP_HOST") or not c.get("IMAP_USER"):
            continue
        db.upsert_account(conn, c["MAIL_ACCOUNT"], c["IMAP_HOST"], int(c["IMAP_PORT"]),
                          c["IMAP_USER"])
        if not c.get("IMAP_PASSWORD"):
            need_pw.append((c["MAIL_ACCOUNT"], c["IMAP_USER"]))

    print("\n作った設定ファイル: {} 件".format(len(made)))
    for slug, user in made:
        print("  .env.mail-archiver.{:<18} {}".format(slug, user))
    if skipped:
        print("飛ばしたもの: {} 件".format(len(skipped)))
        for name, why in skipped:
            print("  {:<20} {}".format(name, why))
    if need_pw:
        print("\n★次にやること（人の作業）。ターミナル.app で1行ずつ:")
        for _, user in need_pw:
            print("  security add-generic-password -s mail-archiver -a {} -w".format(user))
        print("\n入れ終わったら:  python3 sync.py --list-accounts   で「パスワードあり」を確認")
    print("\n取り込み:  python3 sync.py --sync --all-accounts --since-days 30 --limit 50")
    return 0


if __name__ == "__main__":
    sys.exit(main())
