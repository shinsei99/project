#!/usr/bin/env python3
"""特約条項に「似た争いの実例」を付けるための判例表を作る。

**なぜ要るか**
  特約は書いたら終わりではなく、**有効性が裁判で争われる**。
  更新料・違約金・原状回復特約・定期借家・説明義務あたりは実際に争点になっている。
  索引には RETIO（不動産適正取引推進機構）の判例・紛争事例が173件入っているのに、
  特約条項ジェネレーター（8513）も AI重説（8536）もまったく使っていない。

**どこから取るか（ここが肝）**
  本文をキーワードで拾うと**目次のページ**を掴む（実測: 「更新料」で引くと手引の目次が出た）。
  RETIO には **「本号所収裁判例索引」が22本**あり、そこには
      裁判所 / 判決日 / 要旨（〜事例）/ 出典 / 掲載ページ
  が規則的に並んでいる。**索引から取れば、1件ずつが構造化された状態で手に入る。**

**使い方**
  python3 make_case_table.py            # 抽出して JSON を書く
  python3 make_case_table.py --check    # 抽出だけ（書かない）・件数と論点の分布を見る

**出力**
  /Users/apple/tokuyaku_cases.json
  ★リポジトリ直下に置く。特約カタログ（tokuyaku_clauses.py）や生成器（tokuyaku_core.py）と
    同じ場所＝**8513 と 8536 の両方から使える**（AI重説は tokuyaku_core を読んでいる）。
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sqlite3
import sys

KB = "/Users/apple/chatwork-ai-manager/data/app.db"
OUT = pathlib.Path("/Users/apple/tokuyaku_cases.json")

# 論点タグ。**特約カタログ側の title/hint とも同じ規則で突き合わせる**ので、
# ここを増やすと両側に同時に効く。値は正規表現（要旨に当てる）。
TOPICS: dict[str, str] = {
    "手付・違約金": r"手付|違約金|白紙解除",
    "ローン特約": r"融資|ローン|フラット35",
    "契約不適合・瑕疵": r"瑕疵|契約不適合|雨漏り|シロアリ|給湯|欠陥",
    "説明義務・告知": r"説明義務|告知|重要事項|知らせ|説明をしなかった|説明を怠",
    "心理的瑕疵・事故": r"心理的|自殺|自然死|孤独死|事故物件|嫌悪",
    "境界・越境・私道": r"境界|越境|私道|セットバック|接道|擁壁",
    "土壌汚染・地中埋設": r"土壌|汚染|埋設|地中",
    "原状回復・敷金": r"原状回復|敷金|保証金|通常損耗|償却|敷引",
    "更新料・礼金": r"更新料|礼金|更新手数料",
    "賃料・増減額": r"賃料(?:の)?(?:増|減)|増減額|賃料減額",
    "解除・明渡し・立退き": r"解除|明渡|立退|信頼関係",
    "定期借家・再契約": r"定期借家|定期建物賃貸借|再契約",
    "連帯保証・保証会社": r"連帯保証|保証委託|極度額|家賃債務保証",
    "サブリース・一括借上": r"サブリース|一括借上|マスターリース|転貸",
    "近隣・騒音・迷惑行為": r"騒音|迷惑|振動|臭気|階下|受忍限度",
    "設備・修繕": r"修繕|設備|大規模修繕|結露|漏水",
    "媒介・報酬": r"媒介|仲介|報酬|手数料",
    "区分所有・管理": r"管理組合|区分所有|管理規約|専有部分|共用部分",
    "借地・底地": r"借地|底地|地代|借地権",
    "駐車場": r"駐車場|車庫",
}

# 索引の書式ゆれ
_DATE = re.compile(r"((?:令和?|平成?|昭和?)?\s?(?:元|\d{1,2})\s?[.．]\s?\d{1,2}\s?[.．]\s?\d{1,2})")
_COURT = re.compile(r"([^ ]{0,10}?(?:地裁|高裁|最高裁)?\s?(?:支判|地判|高判|最判|決定))\s*$")
_SRC = re.compile(r"(.{2,26}?)\s*[·・…\.]{2,}\s*(\d{1,3})")


def _sp(s: str) -> str:
    """空白を1つに潰す。"""
    return re.sub(r"[\s　]+", " ", s).strip()


def _tidy(s: str) -> str:
    """見せる用。**日本語のあいだに入った空白を消す**（PDFの折り返しで「地 主に」になる）。

    先頭の記号も落とす。索引は「…事例ウエストロー・ジャパン··114」のように続いていて、
    切り出しの境目に「例」「·」が残ることがある（実測で確認）。
    """
    s = _sp(s)
    s = re.sub(r"(?<=[^\x00-\x7F]) (?=[^\x00-\x7F])", "", s)
    return re.sub(r"^[例·・…\.\s]+", "", s)


def topics_of(text: str) -> list[str]:
    """要旨（または特約の title/hint）から論点タグを付ける。両側で同じ関数を使う。"""
    return [name for name, pat in TOPICS.items() if re.search(pat, text)]


def extract(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT d.id, d.title, ch.ord, ch.text FROM knowledge_chunks ch "
        "JOIN knowledge_documents d ON d.id = ch.doc_id "
        "WHERE d.source_kind='判例' AND d.title LIKE '%本号所収%索引%' "
        "ORDER BY d.id, ch.ord"
    ).fetchall()
    seen: dict[tuple, dict] = {}
    for _did, title, _ord, text in rows:
        t = _sp(text)
        parts = _DATE.split(t)
        for i in range(1, len(parts), 2):
            date = _sp(parts[i])
            mc = _COURT.search(parts[i - 1])
            court = _sp(mc.group(1)) if mc else ""
            after = parts[i + 1] if i + 1 < len(parts) else ""
            m = re.search(r"^(.{15,240}?事例)", after.strip(), re.S)
            if not m:
                continue
            summary = _tidy(m.group(1))
            ms = _SRC.search(after[m.end():m.end() + 60])
            src, page = (_tidy(ms.group(1)), ms.group(2)) if ms else ("", "")
            key = (court, date, summary[:40])
            if key in seen:
                # 別チャンクで出典まで取れたら足す（チャンクは重なるので後勝ちにしない）
                if src and not seen[key]["source"]:
                    seen[key]["source"], seen[key]["page"] = src, page
                continue
            seen[key] = {
                "court": court,
                "date": date,
                "summary": summary,
                "source": src,
                "page": page,
                "retio": title.split("_")[0],
                "topics": topics_of(summary),
            }
    return list(seen.values())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if not pathlib.Path(KB).exists():
        print(f"★知識索引が無い: {KB}", file=sys.stderr)
        return 1
    conn = sqlite3.connect(f"file:{KB}?mode=ro", uri=True)
    cases = extract(conn)
    if len(cases) < 150:                    # 索引22本なら200件は超えるはず
        print(f"★抽出できたのが {len(cases)} 件しかない。書式が変わった可能性がある", file=sys.stderr)
        return 1

    tagged = [c for c in cases if c["topics"]]
    cnt = collections.Counter(t for c in cases for t in c["topics"])
    print(f"抽出: {len(cases)} 件 / 論点が付いたもの {len(tagged)} 件"
          f"（{len(tagged) * 100 // len(cases)}%）")
    print(f"出典まで取れたもの: {sum(1 for c in cases if c['source'])} 件\n")
    print("=== 論点の分布 ===")
    for k, v in cnt.most_common():
        print(f"  {v:4d}  {k}")
    missing = [k for k in TOPICS if cnt[k] == 0]
    if missing:
        print(f"\n※ 判例が1件も無い論点: {missing}（特約側で引いても出ない）")

    if args.check:
        print("\n--check なので書かない。")
        return 0
    OUT.write_text(json.dumps(
        {"_meta": {"source": "RETIO 本号所収裁判例索引（不動産適正取引推進機構）",
                   "count": len(cases),
                   "generator": "bookshelf/make_case_table.py",
                   "note": "手で編集しない（生成し直すこと）。要旨は索引の原文。"},
         "topics": {k: v for k, v in TOPICS.items()},
         "cases": cases}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n書き出した: {OUT}（{OUT.stat().st_size // 1024} KB）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
