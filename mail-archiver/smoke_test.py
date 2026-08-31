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

    def capability(self):
        # 本物と同じく、ログイン後に取り直せる形にしておく
        return ("OK", [" ".join(self.capabilities).encode()])

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
    real_connect = iu.connect                  # 11)で接続方式の判定だけ確かめるために取っておく
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

    print("11) 複数アカウント（設定の取り込み・接続方式の判定）")
    # ポートと「SSLを使う」から接続方式を決める。143 は STARTTLS でなければならない
    import imap_util as iu_mod
    import import_mail_accounts as ima
    check(ima.security_of("993", True) == "ssl", "993＋SSL は ssl")
    check(ima.security_of("143", True) == "starttls", "143＋SSL は starttls（SSL直結ではない）")
    check(ima.security_of("143", False) == "none", "143＋SSLなし は none")

    calls = []

    class _FakeIMAP:
        def __init__(self, host, port):
            calls.append(("plain", host, port))

        def starttls(self):
            calls.append(("starttls", None, None))

        def login(self, u, p):
            calls.append(("login", u, p))

    class _FakeSSL(_FakeIMAP):
        def __init__(self, host, port):
            calls.append(("ssl", host, port))

    orig_ssl, orig_plain = iu_mod.imaplib.IMAP4_SSL, iu_mod.imaplib.IMAP4
    try:
        iu_mod.imaplib.IMAP4_SSL, iu_mod.imaplib.IMAP4 = _FakeSSL, _FakeIMAP
        real_connect("h", 143, "u", "p", True)            # ← 会社・独自ドメインの形
        check(("plain", "h", 143) in calls and ("starttls", None, None) in calls,
              "143 は平文で繋いでから STARTTLS へ切り替える")
        calls.clear()
        real_connect("h", 993, "u", "p", True)            # ← iCloud・Gmail の形
        check(("ssl", "h", 993) in calls and ("starttls", None, None) not in calls,
              "993 は最初からSSLで繋ぐ")
    finally:
        iu_mod.imaplib.IMAP4_SSL, iu_mod.imaplib.IMAP4 = orig_ssl, orig_plain

    # 複数アカウントを回すとき、シェルに残った環境変数が全アカウントに被さらないこと
    env_dir = os.path.join(tmp, "envs")
    os.makedirs(env_dir, exist_ok=True)
    one = os.path.join(env_dir, ".env.mail-archiver.test")
    with open(one, "w", encoding="utf-8") as f:
        f.write("MAIL_ACCOUNT=t\nIMAP_HOST=h1\nIMAP_USER=u1\nIMAP_PORT=143\n")
    os.environ["IMAP_USER"] = "shell-side"
    try:
        c1 = config.load(one)
        check(c1["IMAP_USER"] == "u1", "ファイル指定なら環境変数で上書きされない")
        check(config.load()["IMAP_USER"] == "shell-side", "既定の読み込みでは環境変数が効く")
    finally:
        os.environ.pop("IMAP_USER", None)

    # ---------------------------------------------------------------- 添付の中身
    # ★ここが守りたいこと: 「本文に無く、添付にしか書かれていない事実」で検索できること。
    #   2026-08-31 に実際に困った例（PTA大会の会場がスキャンPDFの中にしか無い）を型にしてある。
    print("12) 添付の中身の索引（2026-08-31）")
    import attach_extract  # noqa: E402  … 重い依存を持たないので遅延importでよい

    adb = os.path.join(tmp, "attach.db")
    ac = db.connect(adb)
    db.init_schema(ac)
    aid = db.upsert_account(ac, "t2", "h", 993, "u")
    fid = db.upsert_folder(ac, aid, "INBOX", "INBOX")["id"]
    mid = db.insert_message(ac, {
        "account_id": aid, "folder_id": fid, "uid": 1, "uidvalidity": 1,
        "message_id": "<a@t>", "subject": "PTA大会の出欠返信のお願い",
        "from_name": "", "from_addr": "x@example.com", "to_addrs": "", "cc_addrs": "",
        "date_utc": "2026-07-14T00:00:00Z", "size_bytes": 1, "flags": "",
        "body_text": "出欠の返信をお願いします。",     # ★本文に会場は書かれていない
        "has_attachments": 1, "raw_path": "r.eml", "raw_sha256": "x",
        "synced_at": db.utcnow(), "server_state": "local",
    })
    att_path = os.path.join(tmp, "annai.txt")
    with open(att_path, "w", encoding="utf-8") as f:
        f.write("2．会場　スイスホテル南海大阪　8階「浪華の間」\n9月2日（水）10:00〜13:00\n")
    att_id = db.insert_attachment(ac, mid, "annai.txt", "text/plain", 100, "annai.txt", "sha")

    method, text, pages, err = attach_extract.extract_one(att_path, "annai.txt", use_ocr=False)
    check(method == "text" and "スイスホテル" in text, "添付から中身を取り出せる")
    db.save_attachment_text(ac, att_id, mid, method, text, pages, err)

    rows, total = db.search(ac, q="スイスホテル")
    check(total == 1 and rows and rows[0]["id"] == mid,
          "★本文に無い語（添付にだけある）で見つかる")
    rows2, total2 = db.search(ac, q="スイスホテル", include_attachments=False)
    check(total2 == 0, "添付を見ない設定なら見つからない（従来どおり）")

    hits = db.attachment_hits_terms(ac, [mid], ["スイスホテル"])
    check(mid in hits and hits[mid][0][0] == "annai.txt", "どの添付に当たったかを返す")

    # 同じ添付を2回処理しても、件数が二重にならないこと（FTSは制約を持たないので要注意）
    db.save_attachment_text(ac, att_id, mid, method, text, pages, err)
    rows3, total3 = db.search(ac, q="スイスホテル")
    check(total3 == 1, "二度取り込んでも件数が増えない")

    # 文字が取れなかったものも記録する（記録しないと毎晩同じものを試して前に進まない）
    empty = os.path.join(tmp, "empty.txt")
    open(empty, "w").close()
    m2, t2, p2, e2 = attach_extract.extract_one(empty, "empty.txt", use_ocr=False)
    check(m2 == "none", "文字が無いものは none として記録できる")
    check(attach_extract.extract_one(os.path.join(tmp, "no-such.pdf"), "no-such.pdf",
                                     use_ocr=False)[0] == "error",
          "実体が無いものは error（黙って成功にしない）")
    ac.close()

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
