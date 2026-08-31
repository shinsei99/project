#!/usr/bin/env python3
"""原状回復費用自動精算（8508）に「ガイドラインのどこに書いてあるか」を渡す表を作る。

**なぜ要るか**
  アプリは耐用年数と負担方式をコードに直書きしている（services/depreciation_engine.py の
  MATERIAL_POLICY）。計算は合っているが、**その根拠が精算書に出ない**ので、
  退去者と揉めたときに担当者が「ガイドラインにこう書いてあります」と示せない。
  索引には国交省ガイドライン本文が**ページ番号つき**で入っている（310チャンク）。

**作り方（ここが肝）**
  検索結果をそのまま採らない。**部材ごとに「本文のどこか」を人が決めて（anchor）、
  その場所に本当にその文があるかを機械が検証する**（verify）。
  - 検索任せだと、似た語を含む別の箇所を拾って**間違った根拠を精算書に載せる**恐れがある
  - 逆に手書きだけだと、本文が差し替わったときに**黙って古い引用のまま**になる
  → 「人が場所を決め、機械が中身を照合する」。照合に落ちたら生成しない（＝気づける）。

**使い方**
  python3 make_basis_table.py            # 検証して JSON を書く
  python3 make_basis_table.py --check    # 検証だけ（書かない）

**出力**
  restoration-calculator/guideline_basis.json
  ★data/ には置かない。あそこは入居者名を含むCSVがあるので .gitignore で除外されており、
    置くと**gitに乗らず他PCで黙ってアプリ既定に落ちる**。
  アプリは実行時に索引DBを見ない（このJSONだけ読む）。サブPCでも動く。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sqlite3
import sys

KB = "/Users/apple/chatwork-ai-manager/data/app.db"
OUT = pathlib.Path("/Users/apple/restoration-calculator/guideline_basis.json")

# ガイドライン本体（再改訂版）。参考資料は 4583 だが、別表は本体にある。
DOC_ID = 4582
DOC_TITLE = "国土交通省「原状回復をめぐるトラブルとガイドライン」（再改訂版）"

# 部材種別 → 根拠。
#   anchor : そのチャンクの ord（本文のどこか）。ここに needle があることを機械が確かめる
#   needle : 照合に使う文字列（空白を潰して比較する）。**引用としてそのまま見せる**
#   unit   : 負担単位（別表2「賃借人の負担単位等」）。無ければ None
#   covered: ガイドラインに**その部材の個別の定めがあるか**。
#            False は「アプリの既定であって、ガイドラインが名指ししているわけではない」の意味。
#            ここを曖昧にすると、根拠が無いものにも根拠があるように見えてしまう。
BASIS: dict[str, dict] = {
    "壁クロス": {
        "covered": True,
        "useful_life": 6,
        "policy": "depreciable",
        "anchors": [53, (59, "(壁〔クロス〕) 6 年で残存価値1 円となるような負担割合を算定する。")],
        "needle": "(壁〔クロス〕) ・ 6 年で残存価値1 円となるような直線(または曲線)を想定し、負担割合を算定する。",
        "unit": "m2単位が望ましいが、賃借人が毀損させた箇所を含む一面分までは張替え費用を賃借人負担としてもやむをえないとする。",
        "note": "タバコ等のヤニ・臭いは、居室全体がヤニで変色・臭いが付着した場合のみ、居室全体のクリーニングまたは張替費用を賃借人負担とできる。",
    },
    "天井クロス": {
        "covered": True,
        "useful_life": 6,
        "policy": "depreciable",
        "anchors": [53],
        "needle": "(壁〔クロス〕) ・ 6 年で残存価値1 円となるような直線(または曲線)を想定し、負担割合を算定する。",
        "unit": "m2単位が望ましいが、賃借人が毀損させた箇所を含む一面分までは張替え費用を賃借人負担としてもやむをえないとする。",
        "note": "別表2は「壁・天井(クロス)」を同じ区分として扱う。天井クロス単独の定めは無い。",
    },
    "CF": {
        "covered": True,
        "useful_life": 6,
        "policy": "depreciable",
        "anchors": [51, (59, "(畳床・カーペット・クッションフロア) 6 年で残存価値1 円となるような負担割合を算定する。")],
        "needle": "(畳床、カーペット、クッションフロア) ・ 6 年で残存価値1 円となるような直線(または曲線)を想定し、負担割合を算定する。",
        "unit": "カーペット、クッションフロア:1部屋単位（毀損等が複数箇所の場合は居室全体）",
        "note": "CF＝クッションフロアの略。",
    },
    "クッションフロア": {
        "covered": True,
        "useful_life": 6,
        "policy": "depreciable",
        "anchors": [51, (59, "(畳床・カーペット・クッションフロア) 6 年で残存価値1 円となるような負担割合を算定する。")],
        "needle": "(畳床、カーペット、クッションフロア) ・ 6 年で残存価値1 円となるような直線(または曲線)を想定し、負担割合を算定する。",
        "unit": "カーペット、クッションフロア:1部屋単位（毀損等が複数箇所の場合は居室全体）",
        "note": "",
    },
    "カーペット": {
        "covered": True,
        "useful_life": 6,
        "policy": "depreciable",
        "anchors": [51, (59, "(畳床・カーペット・クッションフロア) 6 年で残存価値1 円となるような負担割合を算定する。")],
        "needle": "(畳床、カーペット、クッションフロア) ・ 6 年で残存価値1 円となるような直線(または曲線)を想定し、負担割合を算定する。",
        "unit": "カーペット、クッションフロア:1部屋単位（毀損等が複数箇所の場合は居室全体）",
        "note": "",
    },
    "畳": {
        "covered": True,
        "useful_life": None,
        "policy": "full_fault",
        "anchors": [51, (59, "(畳表) 経過年数は考慮しない。")],
        "needle": "(畳表) ・ 消耗品に近いものであり、減価償却資産になじまないので、経過年数は考慮しない。",
        "unit": "原則1枚単位（毀損部分が複数枚の場合はその枚数分。裏返しか表替えかは毀損の程度による）",
        "note": "★畳表は経過年数を考慮しない。ただし畳床は「6年で残存価値1円」の側にある（別表2）。"
                "このアプリは畳を1種別で扱っているので、畳床の張替えを含むときは注意する。",
    },
    "襖": {
        "covered": True,
        "useful_life": None,
        "policy": "full_fault",
        "anchors": [53],
        "needle": "(襖紙、障子紙) ・ 消耗品であり、減価償却資産とならないので、経過年数は考慮しない。",
        "unit": "襖:1枚単位（色・模様あわせを行う場合は当該面または居室全体）",
        "note": "襖・障子等の建具部分や柱も経過年数は考慮しない（考慮する場合は当該建物の耐用年数）。",
    },
    "障子": {
        "covered": True,
        "useful_life": None,
        "policy": "full_fault",
        "anchors": [53],
        "needle": "(襖紙、障子紙) ・ 消耗品であり、減価償却資産とならないので、経過年数は考慮しない。",
        "unit": "襖:1枚単位に準じる",
        "note": "",
    },
    "フローリング": {
        "covered": True,
        "useful_life": None,
        "policy": "full_fault",
        "anchors": [51, (59, "(フローリング) 補修は経過年数を考慮しない。")],
        "needle": "(フローリング) ・ 経過年数は考慮しない。ただし、フローリング全体にわたっての毀損によりフローリング床全体を張り替えた場合は、当該建物の耐用年数(参考資料の資料8参照)で残存価値1 円となるような直線を想定し、負担割合を算定する。",
        "unit": "原則m2単位（毀損等が複数箇所の場合は居室全体）",
        "note": "★部分補修は考慮しないが、**床全体を張り替えた場合は建物の耐用年数で按分**する。"
                "このアプリには全体張替えの経路が無いので、その場合は手で調整すること。",
    },
    "ハウスクリーニング": {
        "covered": True,
        "useful_life": None,
        "policy": "full_fault",
        "anchors": [54, (60, "経過年数は考慮しない。借主負担となるのは、通常の清掃を実施していない場合で、部位もしくは、住戸全体の清掃費用相当分を借主負担とする。")],
        "needle": "クリーニングについて、経過年数は考慮しない。賃借人負担となるのは、通常の清掃を実施していない場合で、部位もしくは住戸全体の清掃費用相当分を全額賃借人負担とする。",
        "unit": "部位ごと、または住戸全体",
        "note": "★賃借人が通常の清掃（ゴミ撤去・掃き掃除・拭き掃除・水回り・換気扇・レンジ回りの油汚れ除去）を"
                "実施している場合は、専門業者による全体クリーニングは**賃貸人負担**（別表1）。",
    },
    "換気扇": {
        "covered": False,          # ガイドラインは換気扇を名指ししていない
        # ★2026-08-31 オーナー判断: **明確な記載が無いものは税務上の耐用年数を使う。**
        #   根拠は2つあり、どちらもガイドライン本文で照合できる。
        #     ① 設備機器の一般則は「耐用年数で按分」（P28・下の needle）
        #     ② 経過年数の減価割合は税法によるとガイドライン自身が述べている（P16・下の anchor）
        #   換気扇は省令 別表第一の建物附属設備「冷房、暖房、通風又はボイラー設備」の
        #   **通風設備**にあたり、その他のもの＝15年。
        #   ガイドライン P28 が例示する「便器・洗面台等 15年」（給排水・衛生設備）と同じ枠なので、
        #   ガイドラインの例示とも矛盾しない。
        "useful_life": 15,
        "policy": "depreciable",
        "tax_life": 15,
        "tax_source": "減価償却資産の耐用年数等に関する省令 別表第一"
                      "「建物附属設備／冷房、暖房、通風又はボイラー設備／その他のもの」＝15年",
        "anchors": [
            54,
            (32, "「減価償却資産の耐用年数等に関する省令」(昭和40年3月31日大蔵省令第15号)"
                 "における経過年数による減価割合を参考にして"),
        ],
        "needle": "(設備機器) ・ 耐用年数経過時点で残存価値1円となるような直線(または曲線)を想定し、負担割合を算定する(新品交換の場合も同じ)。",
        "unit": "補修部分、交換相当費用",
        "note": "★ガイドラインは換気扇を名指ししていない。年数は**税法（省令 別表第一）の15年**を使う"
                "（2026-08-31 オーナー判断。定めが無いものは税務上の耐用年数による）。"
                "※P16の引用は残存価値10%だった旧基準の記述で、**採っているのは年数の出どころ**。"
                "残存価値は現行どおり1円で計算する。",
    },
    "ドアクローザー": {
        "covered": False,
        "useful_life": None,
        "policy": "equipment_needs_life",
        "anchors": [54],
        "needle": "(設備機器) ・ 耐用年数経過時点で残存価値1円となるような直線(または曲線)を想定し、負担割合を算定する(新品交換の場合も同じ)。",
        "unit": "補修部分、交換相当費用",
        "note": "★ガイドラインは名指ししていない。設備機器とみるなら耐用年数で按分、"
                "建具の一部とみるなら経過年数を考慮しない（襖・障子等の建具部分と同じ扱い）。判断が分かれる。",
    },
    "ソフト巾木": {
        "covered": False,
        "useful_life": None,
        "policy": None,
        "anchors": [],
        "needle": "",
        "unit": None,
        "note": "ガイドラインに個別の定めが無い。壁（クロス）に準じるとみる考え方もあるが、"
                "本文に根拠は無い。このアプリの既定は「耐用年数なし＝故意過失なら全額」。",
    },
    "ペンキ・塗装": {
        "covered": False,
        "useful_life": None,
        "policy": None,
        "anchors": [],
        "needle": "",
        "unit": None,
        "note": "ガイドラインに個別の定めが無い。このアプリの既定は「耐用年数なし＝故意過失なら全額」。",
    },
    "下地処理": {
        "covered": False,
        "useful_life": None,
        "policy": None,
        "anchors": [57],
        "needle": "壁等の画鋲、ピン等の穴(下地ボードの張替えは不要な程度のもの)",
        "unit": None,
        "note": "★下地処理そのものの定めは無い。ただし別表3に「**画鋲・ピン等の穴（下地ボードの張替えが"
                "不要な程度のもの）は賃貸人負担**」「くぎ穴・ネジ穴（重量物用で下地ボードの張替えが必要な"
                "程度のもの）は賃借人負担」とあり、**下地の張替えが要るかどうかが分かれ目**。"
                "このアプリは下地処理を壁クロスと同じ6年償却にしている。",
    },
    "その他": {
        "covered": False,
        "useful_life": None,
        "policy": None,
        "anchors": [],
        "needle": "",
        "unit": None,
        "note": "部材が特定できないもの。根拠は個別に確かめること。",
    },
    "諸経費": {
        "covered": False,
        "useful_life": None,
        "policy": None,
        "anchors": [],
        "needle": "",
        "unit": None,
        "note": "ガイドラインに定めが無い。このアプリは工事費の負担比率で按分している。",
    },
}


def norm(s: str) -> str:
    """見せる用。空白の揺れを1つに潰す。"""
    return re.sub(r"[\s　]+", " ", s).strip()


def key(s: str) -> str:
    """照合用。**空白を全部消す。**

    PDFから取った本文は、行を折り返した位置に空白が入る（実物は「(また は曲線)」）。
    空白を1つに潰すだけでは、こちらが素直に書いた「(または曲線)」と一致しない。
    日本語は語の区切りに空白を使わないので、全部消して比べてよい。
    ＝ 改行位置が変わっても照合は通り、**文字が変われば落ちる**。
    """
    return re.sub(r"[\s　]+", "", s)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="検証だけして書かない")
    args = ap.parse_args()

    if not pathlib.Path(KB).exists():
        print(f"★知識索引が無い: {KB}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(f"file:{KB}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT ord, source_ref, text FROM knowledge_chunks WHERE doc_id=?", (DOC_ID,)
    ).fetchall()
    if not rows:
        print(f"★ガイドライン本文が索引に無い（doc_id={DOC_ID}）", file=sys.stderr)
        return 1
    by_ord = {r[0]: (r[1], key(r[2])) for r in rows}
    print(f"索引: {DOC_TITLE} … {len(rows)}チャンク")

    out: dict[str, dict] = {}
    ng = 0
    for material, spec in BASIS.items():
        pages: list[str] = []
        found = False
        if spec["needle"]:
            # anchors は ord か (ord, その場所の引用) の混在を許す。
            # 別表2（P26-28）と別表3（P30）は**同じ趣旨だが文言が違う**ので、
            # 同じ引用で両方を照合できない。場所ごとに引用を持たせる。
            for a in spec["anchors"]:
                o, nd = a if isinstance(a, tuple) else (a, spec["needle"])
                needle = key(nd)
                if o not in by_ord:
                    print(f"  ★{material}: ord {o} が索引に無い")
                    ng += 1
                    continue
                ref, text = by_ord[o]
                page = ref.split("/")[-1].strip()
                if needle in text:
                    found = True
                    if page not in pages:
                        pages.append(page)
                else:
                    # 見つからない＝本文が変わったか、場所の指定が誤っている
                    print(f"  ★{material}: ord {o}（{page}）に引用が無い")
                    ng += 1
            if not found:
                ng += 1
                print(f"  ★{material}: どのanchorにも引用が見つからなかった")
        out[material] = {
            "covered": spec["covered"],
            # ★ここがアプリの計算の正になる（ガイドライン優先）。
            #   useful_life / policy は**ガイドライン本文から読み取った値**であって、
            #   アプリ側の既定を写したものではない。covered=False のものは None にしてある
            #   ＝「ガイドラインは何も言っていない」。アプリは自分の既定へ落ちる。
            "useful_life": spec["useful_life"],
            "policy": spec["policy"],
            # ★年数の出どころが税法のもの（ガイドラインに定めが無い部材）。
            #   「ガイドラインにこう書いてある」と「税法の年数を当てた」を混ぜないため、
            #   別の欄に分けて持つ。精算書と画面はこの欄を見て書き分ける。
            "tax_life": spec.get("tax_life"),
            "tax_source": spec.get("tax_source"),
            "pages": pages,
            "quote": norm(spec["needle"]) if spec["needle"] else "",
            "unit": spec["unit"],
            "note": spec["note"],
        }
        mark = "✅" if (spec["covered"] and found) else ("・" if not spec["needle"] else "△")
        print(f"  {mark} {material:12s} {'/'.join(pages) or '—':10s} covered={spec['covered']}")

    if ng:
        print(f"\n★照合に {ng} 件失敗した。JSONは書かない（間違った根拠を載せないため）", file=sys.stderr)
        return 1

    out["_meta"] = {
        "source": DOC_TITLE,
        "doc_id": DOC_ID,
        "chunks": len(rows),
        "generator": "bookshelf/make_basis_table.py",
        "note": "引用はすべて索引の本文と突き合わせ済み。手で編集しない（生成し直すこと）。",
    }
    if args.check:
        print("\n--check なので書かない。照合はすべて通った。")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n書き出した: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
