#!/usr/bin/env python3
"""社内メールアーカイバの通し検証。**本物のメールサーバーには一切つながない**。

    /usr/bin/python3 smoke_test.py

守りたいことを型にしてある:

1. **安全弁**（社員のメールを消さない／会社の共有フォルダに置かない）
2. **選び方**（メルマガ・自動通知を知識索引に入れない。業務メールは入れる）
3. **会社の壁**（知識索引へ渡す会社名が大京商事であること）
4. 書き出しの中身に**添付から取り出した文字**が入ること
"""
from __future__ import annotations

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "mail-archiver"))

FAILED = []


def check(cond, label):
    print(("  ok   " if cond else "  NG   ") + label)
    if not cond:
        FAILED.append(label)


class Row(dict):
    """sqlite3.Row のかわり（テスト用に dict を [] で引けるようにするだけ）。"""
    def __getitem__(self, k):
        return self.get(k)


def main() -> int:
    import guards
    import export_to_knowledge as ex

    print("1) 安全弁")
    tmp = tempfile.mkdtemp(prefix="cma-test-")
    with open(os.path.join(tmp, ".env.company-mail-archiver.ok"), "w", encoding="utf-8") as f:
        f.write("MAIL_ACCOUNT=ok\nARCHIVE_DELETE_ENABLED=0\n")
    check(guards.check_delete_disabled(tmp) == [], "削除が無効なら通す")
    with open(os.path.join(tmp, ".env.company-mail-archiver.ng"), "w", encoding="utf-8") as f:
        f.write("MAIL_ACCOUNT=ng\nARCHIVE_DELETE_ENABLED=1\n")
    check(guards.check_delete_disabled(tmp) == [".env.company-mail-archiver.ng"],
          "★削除が有効な設定を見つけて止める")
    check(guards.check_not_shared("/Users/x/Dropbox-個人/company-mail-archive") == [],
          "個人Dropboxは通す")
    check(len(guards.check_not_shared(
        "/Users/x/大京商事　株式会社 Dropbox/共有フォルダ/mail")) == 2 or
        guards.check_not_shared("/Users/x/大京商事　株式会社 Dropbox/共有フォルダ/mail") != [],
        "★会社の共有フォルダ配下は止める")
    check(guards.check_company("大京商事株式会社") and not guards.check_company("新誠プロパティマネジメント株式会社"),
          "★会社の壁（大京商事以外は通さない）")

    print("2) 知識索引に入れるものの選び方")
    biz = Row(from_addr="tanaka@daikyocorp.co.jp", from_name="田中")
    check(ex.judge(biz, {}, 200)[0] is True, "業務メールは入れる")
    check(ex.judge(biz, {"list-unsubscribe": "<https://x/u>"}, 200)[0] is False,
          "★メルマガ（配信停止リンクあり）は入れない")
    check(ex.judge(biz, {"precedence": "bulk"}, 200)[0] is False, "★一斉配信は入れない")
    check(ex.judge(biz, {"auto-submitted": "auto-replied"}, 200)[0] is False,
          "★自動送信は入れない")
    check(ex.judge(Row(from_addr="noreply@example.com", from_name=""), {}, 200)[0] is False,
          "★返信不可アドレスからの通知は入れない")
    check(ex.judge(Row(from_addr="no-reply@example.com", from_name=""), {}, 200)[0] is False,
          "★no-reply も同じ")
    check(ex.judge(biz, {}, 0)[0] is False, "本文も添付も空なら入れない")
    # ★誤爆しないこと（業務で普通に来るアドレス）
    check(ex.judge(Row(from_addr="info@torihiki.co.jp", from_name="取引先"), {}, 200)[0] is True,
          "info@ を機械的に外さない（取引先の窓口アドレス）")

    print("3) 書き出しの中身")
    row = Row(subject="退去立会いの日程", date_utc="2026-08-20T01:00:00Z",
              from_name="山田", from_addr="yamada@example.co.jp",
              to_addrs="tanaka@daikyocorp.co.jp", cc_addrs="",
              body_text="来週火曜の10時でお願いできますか。", account_name="tanaka")
    md = ex.build_markdown(row, [Row(filename="見積書.pdf", text="原状回復工事 一式 120,000円")])
    check("退去立会いの日程" in md and "yamada@example.co.jp" in md, "件名と差出人が入る")
    check("120,000円" in md and "見積書.pdf" in md, "★添付から取り出した文字も入る")
    check("社内メール" in md, "どこから来た情報かが分かる")
    check(ex.COMPANY == "大京商事株式会社", "★索引に渡す会社名が大京商事")
    check(not ex.OUT_DIR.startswith(os.path.expanduser("~/Library/CloudStorage/Dropbox (大京")),
          "書き出し先が会社の共有フォルダではない")

    print("")
    if FAILED:
        print("失敗 {}件:".format(len(FAILED)))
        for f in FAILED:
            print("  - " + f)
        return 1
    print("すべて合格（社内メールアーカイバ）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
