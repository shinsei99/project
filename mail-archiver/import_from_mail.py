#!/usr/bin/env python3
"""Mail.app（macOS標準メール）から直接取り込む。**IMAPのパスワードが要らない**取り込み口。

    python3 import_from_mail.py --list                       # アカウントとメールボックスを見る
    python3 import_from_mail.py --mailbox INBOX --limit 20   # 新しい順に取り込む

なぜ在るのか: iCloud のように2ファクタ認証のアカウントは、外部アプリからのIMAPログインに
**App用パスワード**が要る。それを発行する前でも、手元の Mail.app が持っているメールなら
AppleScript で丸ごと（RFC822のソースごと）受け取れるので、中身を確かめられる。

**ここで取り込んだメールは、サーバー側削除の対象に絶対にならない。**
`server_state='local'`（IMAP管理外）で入れているため、`--delete` の候補抽出
（`server_state='present'` のみ）に一生引っかからない。UIDもIMAPのものではないので、
うっかり別のメールを消す余地を最初から断ってある。

限界（正直に）: Mail.app が返す `source` はテキストなので、8bitのまま送られてきた本文は
文字化けの可能性がある（base64/quoted-printable の普通のメールは問題ない）。
**原本の完全性を保証したいなら IMAP 経由（`sync.py --sync`）のほうが確実。**
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from typing import List, Optional, Tuple

import config
import db
import imap_util as iu
import sync


def osa(script: str, timeout: int = 120) -> str:
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "osascript が失敗しました")
    return r.stdout.rstrip("\n")


def list_mailboxes() -> None:
    print(osa('''
tell application "Mail"
  set out to ""
  repeat with a in every account
    set out to out & "[" & (name of a) & "]" & linefeed
    repeat with mb in every mailbox of a
      try
        set out to out & "  " & (name of mb) & " = " & ((count of messages of mb) as text) & linefeed
      end try
    end repeat
  end repeat
  return out
end tell'''))


def fetch_one(account: str, mailbox: str, index: int, out_path: str) -> Optional[Tuple[str, str]]:
    """1通のソースをファイルへ書き出す。戻り値 (Message-ID, 件名)。"""
    script = '''
tell application "Mail"
  set mb to mailbox "{mb}" of account "{acc}"
  set m to message {idx} of mb
  set src to source of m
  set fh to open for access (POSIX file "{path}") with write permission
  set eof fh to 0
  write src to fh as «class utf8»
  close access fh
  set mid to ""
  try
    set mid to message id of m
  end try
  set sbj to ""
  try
    set sbj to subject of m
  end try
  return mid & tab & sbj
end tell'''.format(mb=mailbox.replace('"', '\\"'), acc=account.replace('"', '\\"'),
                   idx=index, path=out_path)
    line = osa(script)
    parts = line.split("\t", 1)
    return (parts[0].strip(), parts[1].strip() if len(parts) > 1 else "")


def main() -> int:
    p = argparse.ArgumentParser(description="Mail.app から取り込む（IMAPパスワード不要）")
    p.add_argument("--list", action="store_true", help="アカウントとメールボックスの一覧")
    p.add_argument("--account", default="iCloud")
    p.add_argument("--mailbox", default="INBOX")
    p.add_argument("--limit", type=int, default=20, help="新しい順に何通取り込むか")
    p.add_argument("--db", default=config.DB_PATH)
    args = p.parse_args()

    if args.list:
        list_mailboxes()
        return 0

    conn = db.connect(args.db)
    db.init_schema(conn)
    account_id = db.upsert_account(conn, "Mail.app/{}".format(args.account), "(Mail.app)", 0,
                                   args.account)
    frow = db.upsert_folder(conn, account_id, "mailapp:{}".format(args.mailbox), args.mailbox)
    db.set_folder_uidvalidity(conn, frow["id"], 0)

    total = int(osa('tell application "Mail" to return (count of messages of '
                    'mailbox "{}" of account "{}") as text'
                    .format(args.mailbox, args.account)))
    n = min(args.limit, total)
    print("{} / {} … {}通中 {}通を取り込みます".format(args.account, args.mailbox, total, n))

    tmp = tempfile.mkdtemp(prefix="mailapp-")
    got = skipped = 0
    for i in range(1, n + 1):
        eml = os.path.join(tmp, "{}.eml".format(i))
        try:
            msgid, subject = fetch_one(args.account, args.mailbox, i, eml)
        except Exception as e:
            print("  {}通目 取得失敗: {}".format(i, e))
            continue
        if not os.path.exists(eml):
            print("  {}通目 ソースが空".format(i))
            continue
        with open(eml, "rb") as fp:
            raw = fp.read()
        if msgid and conn.execute(
                "SELECT 1 FROM messages WHERE account_id=? AND message_id LIKE ?",
                (account_id, "%{}%".format(msgid))).fetchone():
            skipped += 1
            continue
        # UIDはIMAPのものではない。あくまで並び順の通し番号（衝突しないよう負値は使わない）
        if db.message_exists(conn, account_id, frow["id"], 0, i):
            skipped += 1
            continue
        try:
            # ★state='local'（IMAP管理外）で入れる。削除候補（present）には一生入らない
            row_id = sync.save_one(conn, {"MAIL_ACCOUNT": "mailapp-{}".format(args.account)},
                                   account_id, frow, 0, i, raw, "\\Seen", state="local")
        except Exception as e:
            conn.rollback()
            print("  {}通目 保存失敗: {}".format(i, e))
            continue
        got += 1
        if got % 10 == 0:
            print("  … {}/{}".format(got, n))

    print("取り込み {}通 / 既にあった {}通".format(got, skipped))
    s = db.stats(conn)
    print("合計 {}通 / 添付 {}件".format(s["messages"], s["attachments"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
