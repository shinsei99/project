#!/usr/bin/env python3
"""業務マニュアル（8521）に「法令の根拠」を足すための引用を作る。

**なぜ要るか**
  マニュアルには**インボイスも電子帳簿保存法も一言も書かれていない**（2026-08-30 実測）。
  全社員が毎日読む入口なのに、請求書の作り方も、メールで受け取った請求書の保存も、
  法令側の要件が載っていない。索引には一次資料が21件あるので、そこから補える。

**作り方（原状回復・判例と同じ）**
  検索結果をそのまま採らない。**人が「本文のどこか」を決めて、機械が中身を照合する。**
  ★キーワード検索は**目次のページを掴む**（実測: 「適格請求書の記載事項」で引くと
    250ページのQ&Aの目次が出た。本文はP30にある）。照合に落ちたら書き出さない。

**会社の手順と法令の根拠を混ぜない**
  出力は `law` という専用ブロックとして、マニュアル本文とは見た目を分けて出す。
  「これは国が決めていること」「これは当社のやり方」を読む人が区別できるようにする。

**使い方**
  python3 make_manual_law_notes.py            # 照合して JSON を書く
  python3 make_manual_law_notes.py --check    # 照合だけ

**出力**
  /Users/apple/gyomu-manual/law_notes.json （generate.py が読む）
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sqlite3
import sys

KB = "/Users/apple/chatwork-ai-manager/data/app.db"
OUT = pathlib.Path("/Users/apple/gyomu-manual/law_notes.json")

# マニュアルID → 足す根拠。
#   src    : 索引の資料名（前方一致）
#   needle : 本文に**必ず含まれているはず**の文字列。空白を全部消して照合する
#   title  : 画面に出す見出し
#   body   : 画面に出す説明（当社向けの言い換え。★引用そのものではない）
#   quote  : 画面に出す引用（原文。needle と同じか、その一部）
NOTES: dict[str, list[dict]] = {
    "keiri-seikyu": [{
        "title": "請求書に必ず入れる6項目（インボイス）",
        "src": "国税庁_インボイスQA",
        "needle": "課税資産の譲渡等の税抜価額又は税込価額を税率ごとに区分して合計した金額及び適用税率",
        "quote": "1 適格請求書発行事業者の氏名又は名称及び登録番号 / 2 課税資産の譲渡等を行った年月日 / "
                 "3 課税資産の譲渡等に係る資産又は役務の内容 / "
                 "4 課税資産の譲渡等の税抜価額又は税込価額を税率ごとに区分して合計した金額及び適用税率 / "
                 "5 税率ごとに区分した消費税額等 / 6 書類の交付を受ける事業者の氏名又は名称",
        "body": "この6つが1つでも欠けると、受け取った側が仕入税額控除を受けられません。"
                "特に**登録番号（T＋13桁）**と**税率ごとの区分**は入れ忘れが起きやすいところです。",
    }],
    "keiri-nyukin": [{
        "title": "メールで受け取った請求書は、そのデータのまま保存する（電子帳簿保存法）",
        "src": "国税庁_電子帳簿保存法一問一答_電子取引",
        "needle": "電子取引を行った場合には、取引情報を保存することとなりますが",
        "quote": "1 電子メールに請求書等が添付された場合 …(1) 請求書等が添付された電子メールそのものを"
                 "サーバ等に保存する。(2) 添付された請求書等をサーバ等に保存する。",
        "body": "**紙に印刷して保存するだけでは要件を満たしません。** メールに添付されて届いた請求書・領収書は、"
                "データのまま残す必要があります（相手のサイトからダウンロードしたものも同じ）。",
    }, {
        "title": "保存したデータは「日付・金額・取引先」で探せること（検索要件）",
        "src": "国税庁_電子帳簿保存法一問一答_電子取引",
        "needle": "取引年月日その他の日付、取引金額及び取引先を検索の条件として設定することができること",
        "quote": "(1) 取引年月日その他の日付、取引金額及び取引先を検索の条件として設定することができること。"
                 "(2) 日付又は金額に係る記録項目については、その範囲を指定して条件を設定することができること。"
                 "(3) 二以上の任意の記録項目を組み合わせて条件を設定することができること。",
        "body": "**全文検索ができるだけでは足りません。** 日付と金額は「範囲を指定して」探せること、"
                "2つ以上の項目を組み合わせて探せることまで求められています。"
                "ファイル名を「日付_取引先_金額」の形にそろえておくのが実務上いちばん確実です。",
    }],
    "kanri-kaiyaku": [{
        "title": "原状回復とは何か（国交省ガイドラインの定義）",
        "src": "国交省_原状回復をめぐるトラブルとガイドライン",
        "needle": "賃借人の居住、使用により発生した建物価値の減少のうち、賃借人の故意・過失、善管注意義務違反",
        "quote": "原状回復を「賃借人の居住、使用により発生した建物価値の減少のうち、賃借人の故意・過失、"
                 "善管注意義務違反、その他通常の使用を超えるような使用による損耗・毀損を復旧すること」と定義",
        "body": "**元の状態に戻すことではありません。** 普通に住んでいて生じた傷み（通常損耗・経年劣化）は"
                "貸主の負担です。借主に求められるのは、故意・過失や、通常の使い方を超えた使い方による分だけです。",
    }, {
        "title": "経過年数で借主の負担は軽くなる",
        "src": "国交省_原状回復をめぐるトラブルとガイドライン",
        "needle": "賃借人の負担について、建物・設備等の経過年数を考慮することとし、同じ損耗等であっても、経過年数に応じて負担を軽減する",
        "quote": "賃借人の負担について、建物・設備等の経過年数を考慮することとし、"
                 "同じ損耗等であっても、経過年数に応じて負担を軽減する考え方を採用した。",
        "body": "壁クロス・クッションフロア・カーペットは**6年で残存価値1円**まで下がります（別表2）。"
                "6年住んだ入居者に全額を請求することはできません。"
                "計算は社内ツール「原状回復費用自動精算」が行い、根拠のページも画面に出ます。",
    }],
    "keiri-seisan": [{
        "title": "精算で借主に請求できる範囲（別表2）",
        "src": "国交省_原状回復をめぐるトラブルとガイドライン",
        "needle": "(壁〔クロス〕)・6年で残存価値1円となるような直線(または曲線)を想定し、負担割合を算定する。",
        "quote": "(壁〔クロス〕) 6年で残存価値1円となるような直線(または曲線)を想定し、負担割合を算定する。"
                 " ／ (畳表) 消耗品に近いものであり、減価償却資産になじまないので、経過年数は考慮しない。",
        "body": "部材ごとに扱いが違います。**クロス・CF・カーペットは6年で償却、畳表とフローリング（部分補修）は"
                "経過年数を考慮しない**、といった区分です。社内ツール「原状回復費用自動精算」が"
                "ページ番号つきで根拠を出すので、揉めたときはその画面をそのまま示せます。",
    }],
}


def key(s: str) -> str:
    """照合用。空白を全部消す（PDFは折り返しで語の途中に空白が入る）。"""
    return re.sub(r"[\s　]+", "", s or "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{KB}?mode=ro", uri=True)
    out: dict[str, list[dict]] = {}
    ng = 0
    for mid, notes in NOTES.items():
        rows_out = []
        for nt in notes:
            hit = None
            for title, ref, text in conn.execute(
                    "SELECT d.title, ch.source_ref, ch.text FROM knowledge_chunks ch "
                    "JOIN knowledge_documents d ON d.id = ch.doc_id "
                    "WHERE d.title LIKE ? ORDER BY ch.ord", (nt["src"] + "%",)):
                if key(nt["needle"]) in key(text):
                    hit = (title, ref.split("/")[-1].strip())
                    break
            if not hit:
                print(f"  ★{mid}: 照合できない … {nt['title']}")
                ng += 1
                continue
            src_title, page = hit
            print(f"  ✅ {mid:16s} {page:5s} {nt['title'][:40]}")
            rows_out.append({"title": nt["title"], "body": nt["body"], "quote": nt["quote"],
                             "source": src_title, "page": page})
        if rows_out:
            out[mid] = rows_out

    if ng:
        print(f"\n★ {ng} 件が照合できなかった。書き出さない（間違った根拠を載せないため）", file=sys.stderr)
        return 1
    if args.check:
        print("\n--check なので書かない。照合はすべて通った。")
        return 0
    OUT.write_text(json.dumps(
        {"_meta": {"generator": "bookshelf/make_manual_law_notes.py",
                   "note": "手で編集しない（生成し直すこと）。引用は索引の本文と照合済み。"},
         "notes": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n書き出した: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
