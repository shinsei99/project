#!/usr/bin/env python3
"""通し検証。**本物のIMAPサーバーには一切つながない**（偽サーバーで全部確かめる）。

    python3 smoke_test.py

確かめること:
  1. 取り込み（本文・添付・日本語件名・原本の SHA256）
  2. 日本語の全文検索（FTS5 trigram）
  3. 14日ルール … 取り込み直後は削除候補にならない
  4. dry-run では**サーバーから1通も消えない**
  5. 本番削除で消え、DBが 'deleted' になり、原本はローカルに残る
  6. 原本が壊れていたら消さない（SHA256不一致）
  7. UIDVALIDITY が変わったフォルダは丸ごと中止
  8. Message-ID が食い違うUIDは消さない（別のメールを消さない）
  9. UIDPLUS 非対応サーバーでは素のEXPUNGEを勝手にやらない
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

FAILED = []


def check(cond, label):
    print(("  ok   " if cond else "  NG   ") + label)
    if not cond:
        FAILED.append(label)


# ---------------------------------------------------------------- 偽IMAPサーバー

class FakeIMAP:
    def __init__(self, folders):
        self.folders = folders            # {raw_name: {"uidvalidity": int, "msgs": {uid: [raw, flags]}}}
        self.capabilities = ("IMAP4REV1", "UIDPLUS")
        self.cur = None
        self.expunged_full = 0

    # -- 接続系
    def login(self, u, p):
        return ("OK", [b"ok"])

    def logout(self):
        return ("BYE", [b"bye"])

    def list(self):
        return ("OK", ['(\\HasNoChildren) "." "{}"'.format(k).encode() for k in self.folders])

    def select(self, name, readonly=True):
        name = name.strip('"')
        if name not in self.folders:
            return ("NO", [b"no such folder"])
        self.cur = name
        return ("OK", [str(len(self.folders[name]["msgs"])).encode()])

    def response(self, key):
        if key == "UIDVALIDITY" and self.cur:
            return ("UIDVALIDITY", [str(self.folders[self.cur]["uidvalidity"]).encode()])
        return (key, [None])

    # -- UIDコマンド
    def uid(self, cmd, *args):
        cmd = cmd.upper()
        msgs = self.folders[self.cur]["msgs"]
        if cmd == "SEARCH":
            rest = [a for a in args if a]
            if rest and rest[0] == "UID":
                lo = int(rest[1].split(":")[0])
                uids = [u for u in sorted(msgs) if u >= lo]
            else:
                uids = sorted(msgs)
            return ("OK", [" ".join(str(u) for u in uids).encode()])
        if cmd == "FETCH":
            uid = int(args[0])
            what = args[1]
            if uid not in msgs:
                return ("OK", [None])
            raw, flags = msgs[uid]
            if "HEADER.FIELDS" in what:
                m = re.search(rb"(?im)^message-id:.*$", raw)
                head = (m.group(0) if m else b"") + b"\r\n\r\n"
                return ("OK", [(b"1 (BODY[HEADER.FIELDS (MESSAGE-ID)] {%d}" % len(head), head), b")"])
            if what == "(RFC822.SIZE)":
                return ("OK", [b"1 (UID %d RFC822.SIZE %d)" % (uid, len(raw))])
            meta = b"1 (UID %d FLAGS (%s) RFC822.SIZE %d BODY[] {%d}" % (
                uid, flags.encode(), len(raw), len(raw))
            return ("OK", [(meta, raw), b")"])
        if cmd == "STORE":
            for u in [int(x) for x in args[0].split(",")]:
                if u in msgs:
                    msgs[u][1] = (msgs[u][1] + " \\Deleted").strip()
            return ("OK", [b"ok"])
        if cmd == "EXPUNGE":
            for u in [int(x) for x in args[0].split(",")]:
                if u in msgs and "\\Deleted" in msgs[u][1]:
                    del msgs[u]
            return ("OK", [b"ok"])
        raise AssertionError("未対応のUIDコマンド: " + cmd)

    def expunge(self):
        self.expunged_full += 1
        msgs = self.folders[self.cur]["msgs"]
        for u in [u for u, v in msgs.items() if "\\Deleted" in v[1]]:
            del msgs[u]
        return ("OK", [b"ok"])


def make_mail(subject, body, frm, to, msgid, attach=None):
    m = EmailMessage()
    m["Subject"] = subject
    m["From"] = frm
    m["To"] = to
    m["Message-ID"] = msgid
    m["Date"] = "Mon, 04 Aug 2026 10:00:00 +0900"
    m.set_content(body)
    if attach:
        fname, data = attach
        m.add_attachment(data, maintype="application", subtype="pdf", filename=fname)
    return m.as_bytes()


def build_server():
    return {
        "INBOX": {"uidvalidity": 1001, "msgs": {
            10: [make_mail("【請求書】8月分の家賃について", "いつもお世話になっております。\n"
                           "8月分の請求書を送付いたします。よろしくお願いいたします。",
                           "経理 <keiri@example.co.jp>", "shin@daikyocorp.co.jp", "<a1@example>"),
                 "\\Seen"],
            11: [make_mail("退去立会いの日程", "来週火曜の10時でお願いできますでしょうか。",
                           "山田 <yamada@example.co.jp>", "shin@daikyocorp.co.jp", "<a2@example>",
                           attach=("見積書.pdf", b"%PDF-1.4 dummy attachment")), "\\Seen"],
            12: [make_mail("未読のお知らせ", "これは未読のままのメールです。",
                           "info@example.com", "shin@daikyocorp.co.jp", "<a3@example>"), ""],
        }},
        "INBOX.&U9ZfFVFI-": {"uidvalidity": 2002, "msgs": {   # 「取引先」
            5: [make_mail("契約更新の件", "更新後の条件についてご相談させてください。",
                          "取引先 <torihiki@example.co.jp>", "shin@daikyocorp.co.jp", "<b1@example>"),
                "\\Seen"],
        }},
        "Trash": {"uidvalidity": 3003, "msgs": {
            1: [make_mail("ゴミ箱のメール", "消す予定", "x@example.com", "shin@daikyocorp.co.jp",
                          "<c1@example>"), "\\Seen"],
        }},
    }


def backdate(conn, days=15):
    old = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute("UPDATE messages SET synced_at=?", (old,))
    conn.commit()


def main():
    tmp = tempfile.mkdtemp(prefix="mail-archiver-test-")
    import config
    config.DATA_DIR = tmp
    config.DB_PATH = os.path.join(tmp, "mail.db")
    import db, imap_util as iu, sync
    sync.config = config

    server = build_server()
    fake = FakeIMAP(server)
    iu.connect = lambda *a, **k: fake          # 本物には繋がない
    sync.iu = iu

    cfg = {"MAIL_ACCOUNT": "test", "IMAP_HOST": "fake", "IMAP_PORT": "993",
           "IMAP_USER": "u", "IMAP_PASSWORD": "p", "IMAP_SSL": "1",
           "ARCHIVE_DELETE_ENABLED": "1", "ARCHIVE_DELETE_DAYS": "14",
           "ARCHIVE_EXCLUDE_FOLDERS": "Trash,ゴミ箱"}

    conn = db.connect(config.DB_PATH)
    db.init_schema(conn)

    print("1) 取り込み")
    sync.do_sync(conn, cfg, None, 0, None)
    s = db.stats(conn)
    check(s["messages"] == 4, "4通取り込んだ（ゴミ箱は除外）… 実際 {}".format(s["messages"]))
    check(s["attachments"] == 1, "添付1件を保存した")
    row = conn.execute("SELECT * FROM messages WHERE uid=11").fetchone()
    check(row is not None and row["has_attachments"] == 1, "添付ありフラグが立っている")
    att = db.attachments_of(conn, row["id"])[0]
    check(att["filename"] == "見積書.pdf", "添付のファイル名が日本語のまま")
    check(os.path.exists(os.path.join(tmp, att["path"])), "添付ファイルが実在する")
    raw_abs = os.path.join(tmp, row["raw_path"])
    check(os.path.exists(raw_abs), "原本 .eml が実在する")
    check(db.sha256_bytes(open(raw_abs, "rb").read()) == row["raw_sha256"], "原本のSHA256が一致")
    fol = conn.execute("SELECT name FROM folders WHERE raw_name='INBOX.&U9ZfFVFI-'").fetchone()
    check(fol and fol["name"] == "INBOX.取引先", "フォルダ名がUTF-7からデコードされた")
    check(all("\\Deleted" not in v[1] for v in server["INBOX"]["msgs"].values()),
          "取り込みでサーバー側のフラグを変えていない")

    print("2) 検索")
    rows, total = db.search(conn, q="請求書")
    check(total == 1 and "請求書" in (rows[0]["subject"] or ""), "日本語キーワードで件名がヒット")
    rows, total = db.search(conn, q="立会い")
    check(total == 1, "本文以外にも件名の部分一致が効く")
    rows, total = db.search(conn, q="お世話になっております")
    check(total == 1, "本文の日本語で全文検索できる")
    rows, total = db.search(conn, sender="yamada@example.co.jp")
    check(total == 1, "送信元で絞り込める")
    rows, total = db.search(conn, has_attach=True)
    check(total == 1, "添付ありで絞り込める")

    print("3) 14日ルール")
    acc = conn.execute("SELECT * FROM accounts").fetchone()
    check(len(db.deletable_candidates(conn, acc["id"], 14)) == 0,
          "取り込み直後は削除候補が0（synced_atが新しい）")
    backdate(conn, 15)
    cands = db.deletable_candidates(conn, acc["id"], 14)
    check(len(cands) == 3, "15日前に取り込んだ扱いにすると既読3通が候補（未読は除く）… 実際 {}".format(len(cands)))
    check(len(db.deletable_candidates(conn, acc["id"], 14, keep_unseen=False)) == 4,
          "--include-unseen 相当で未読も候補に入る")

    print("4) dry-run")
    before = sum(len(f["msgs"]) for f in server.values())
    sync.do_delete(conn, cfg, 14, False, None, 500, False, False, False)
    after = sum(len(f["msgs"]) for f in server.values())
    check(before == after, "dry-run ではサーバーから1通も消えていない（{} → {}）".format(before, after))
    check(conn.execute("SELECT COUNT(*) c FROM messages WHERE server_state='deleted'"
                       ).fetchone()["c"] == 0, "dry-run ではDBの状態も変えない")
    check(conn.execute("SELECT COUNT(*) c FROM delete_log WHERE mode='dry-run'"
                       ).fetchone()["c"] == 3, "dry-run の記録が3件残る")

    print("5) 安全弁: 原本が壊れていたら消さない")
    victim = conn.execute("SELECT * FROM messages WHERE uid=10").fetchone()
    with open(os.path.join(tmp, victim["raw_path"]), "ab") as fp:
        fp.write(b"CORRUPT")
    ok, why = sync.local_copy_ok(conn, victim)
    check(not ok, "SHA256不一致を検知した（{}）".format(why))
    sync.do_delete(conn, cfg, 14, True, "INBOX", 500, False, False, False)
    check(10 in server["INBOX"]["msgs"], "壊れていた1通はサーバーに残した")
    check(11 not in server["INBOX"]["msgs"], "健全な1通はサーバーから消えた")
    check(conn.execute("SELECT server_state FROM messages WHERE uid=11").fetchone()["server_state"]
          == "deleted", "消したメールのDB状態が deleted")
    check(os.path.exists(os.path.join(tmp, conn.execute(
        "SELECT raw_path FROM messages WHERE uid=11").fetchone()["raw_path"])),
        "サーバーから消してもローカルの原本は残っている")
    check(12 in server["INBOX"]["msgs"], "未読メールは消していない")

    print("6) 安全弁: UIDVALIDITY が変わったフォルダは中止")
    server["INBOX.&U9ZfFVFI-"]["uidvalidity"] = 9999
    sync.do_delete(conn, cfg, 14, True, "INBOX.取引先", 500, False, False, False)
    check(5 in server["INBOX.&U9ZfFVFI-"]["msgs"], "UIDVALIDITY 不一致のフォルダは1通も消していない")
    check(conn.execute("SELECT COUNT(*) c FROM delete_log WHERE reason LIKE '%UIDVALIDITY%'"
                       ).fetchone()["c"] >= 1, "中止した理由がログに残る")
    server["INBOX.&U9ZfFVFI-"]["uidvalidity"] = 2002

    print("7) 安全弁: Message-ID が食い違うUIDは消さない")
    server["INBOX.&U9ZfFVFI-"]["msgs"][5][0] = make_mail(
        "まったく別のメール", "UIDが指す先が入れ替わった状況", "other@example.com",
        "shin@daikyocorp.co.jp", "<zzz@example>")
    sync.do_delete(conn, cfg, 14, True, "INBOX.取引先", 500, False, False, False)
    check(5 in server["INBOX.&U9ZfFVFI-"]["msgs"], "別のメールにすり替わったUIDは消さない")
    check(conn.execute("SELECT COUNT(*) c FROM delete_log WHERE reason LIKE '%Message-ID%'"
                       ).fetchone()["c"] >= 1, "すり替わりを理由つきで記録した")

    print("8) 安全弁: ゴミ箱は触らない・UIDPLUS非対応なら素のEXPUNGEをしない")
    check(1 in server["Trash"]["msgs"], "除外フォルダ（Trash）のメールは残っている")
    check(conn.execute("SELECT COUNT(*) c FROM folders WHERE name='Trash'").fetchone()["c"] == 0,
          "除外フォルダは取り込みもしていない")
    fake.capabilities = ("IMAP4REV1",)
    fake.expunged_full = 0
    conn.execute("UPDATE messages SET server_state='present' WHERE uid=10")
    conn.commit()
    sync.do_delete(conn, cfg, 14, True, "INBOX", 500, False, False, False)
    check(fake.expunged_full == 0, "UIDPLUS非対応サーバーでは素のEXPUNGEを実行しない")
    check(10 in server["INBOX"]["msgs"], "UIDPLUSが無いときは何も消さずに中止する")
    fake.capabilities = ("IMAP4REV1", "UIDPLUS")

    print("9) 設定で無効なら何もしない")
    cfg2 = dict(cfg, ARCHIVE_DELETE_ENABLED="0")
    before = sum(len(f["msgs"]) for f in server.values())
    sync.do_delete(conn, cfg2, 14, True, None, 500, False, False, False)
    check(before == sum(len(f["msgs"]) for f in server.values()),
          "ARCHIVE_DELETE_ENABLED=0 なら --yes でも消さない")

    print("10) 再同期しても二重取り込みしない")
    n_before = db.stats(conn)["messages"]
    sync.do_sync(conn, cfg, None, 0, None)
    check(db.stats(conn)["messages"] == n_before, "同じメールを二度保存しない")

    shutil.rmtree(tmp, ignore_errors=True)
    print("")
    if FAILED:
        print("失敗 {}件:".format(len(FAILED)))
        for f in FAILED:
            print("  - " + f)
        return 1
    print("すべて合格")
    return 0


if __name__ == "__main__":
    sys.exit(main())
