#!/usr/bin/env python3
"""AI重説（8536）に「重要事項説明書の記載漏れ点検」を渡す表を作る。

**なぜ要るか**
  重説は**書き漏らしがそのまま説明義務違反**になる。中身の正しさより先に
  「そもそも項目が抜けていないか」のほうが機械で確実に点検でき、実害も大きい。

**どこから取るか（3つの出どころを役割で分ける）**
  1. **条文（宅建業法35条1項の各号）… e-Gov法令API**
     ★索引には35条の条文が入っていない（実測0件）。しかも条文は改正で変わるので、
       索引に入れて固めるより**APIで取って施行日ごと記録する**のが正しい。
       JSONの構造（Article/Paragraph/Item）から号を取るので、
       「一当該宅地又は…」と地続きになった本文を正規表現で切る必要がない。
  2. **解釈運用のどこに書いてあるか … 知識索引**
     国交省「宅地建物取引業法の解釈・運用の考え方（令和8年4月1日施行版）」。
     本文が号を名指ししている（例「法第35条第1項第6号に基づき」）ので、
     **号ごとにページを貼れる**（実測: 15号中11号に紐づく）。
  3. **本当に検出できるか … 索引にある実物の重説7本で検証**
     検出用キーワードは人が決めるしかないが、**決めっぱなしにしない**。
     実物の重説に当たるかを機械で確かめ、当たらない号は警告する。

**使い方**
  python3 make_jyuusetsu_checklist.py           # 取得・検証して JSON を書く
  python3 make_jyuusetsu_checklist.py --check   # 検証だけ（書かない）

**出力**
  /Users/apple/jyuusetsu_checklist.json
  ★直下に置く。共有モジュール jyuusetsu_checklist.py が読む。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sqlite3
import sys

sys.path.insert(0, "/Users/apple")
import egov_law_api as egov  # noqa: E402

KB = "/Users/apple/chatwork-ai-manager/data/app.db"
OUT = pathlib.Path("/Users/apple/jyuusetsu_checklist.json")
LAW_TITLE = "宅地建物取引業法"
ARTICLE = "第三十五条"

# 号 → 重説の中でその項目を書いていれば必ず出てくるはずの語（**当社が決めた検出の手がかり**。
# 条文そのものではない）。1つでも当たれば「記載あり」とみなす。
# ★実物の重説7本で当たるかを下で検証する。当たらない号は警告して人に直させる。
DETECT: dict[str, list[str]] = {
    "一": ["登記された権利", "登記名義人", "所有権", "抵当権", "登記記録", "登記簿"],
    "二": ["都市計画法", "建築基準法", "用途地域", "法令に基づく制限"],
    "三": ["私道"],
    "四": ["飲用水", "上水道", "電気", "ガス", "排水"],
    "五": ["工事の完了", "完了時における形状", "未完成", "完成予定"],
    "六": ["区分所有", "共用部分", "管理規約", "敷地に関する権利"],
    "六の二": ["建物状況調査", "インスペクション", "既存住宅", "設計図書"],
    "七": ["授受される金銭", "手付金", "金銭の額"],
    "八": ["契約の解除"],
    "九": ["損害賠償額の予定", "違約金"],
    "十": ["手付金等の保全", "保全措置"],
    "十一": ["支払金", "預り金"],
    "十二": ["あっせん", "あつせん", "金銭の貸借", "融資", "ローン"],
    "十三": ["契約不適合", "瑕疵担保", "保証保険"],
    "十四": ["石綿", "耐震", "ハザードマップ", "造成宅地", "土砂災害", "津波", "水害"],
}

# 十四号は「国土交通省令で定める事項」＝施行規則16条の4の3。中身が多く、
# **ここの書き漏らしが実務で一番起きる**ので、個別に見る。
SUB_14: dict[str, list[str]] = {
    "水害ハザードマップ": ["ハザードマップ", "水害", "浸水想定"],
    "石綿（アスベスト）調査": ["石綿", "アスベスト"],
    "耐震診断": ["耐震診断", "耐震"],
    "造成宅地防災区域": ["造成宅地防災区域", "造成宅地"],
    "土砂災害警戒区域": ["土砂災害"],
    "津波災害警戒区域": ["津波"],
}

_GUIDE_TITLE = "%宅地建物取引業法_解釈運用%"
# 解釈運用は半角で書く（例「法第35条第1項第6号」）。漢数字では1件も当たらない（実測）
_GUIDE_PAT = re.compile(r"第35条(?:第1項)?第(\d+)号(?:の(\d))?")
# 漢数字の号 → 解釈運用側の表記
_ARABIC = {"一": "1", "二": "2", "三": "3", "四": "4", "五": "5", "六": "6", "六の二": "6の2",
           "七": "7", "八": "8", "九": "9", "十": "10", "十一": "11", "十二": "12",
           "十三": "13", "十四": "14"}


def _sp(s: str) -> str:
    return re.sub(r"[\s　]+", "", s or "")


def _kids(n):
    return n.get("children", []) if isinstance(n, dict) else []


def _walk(n):
    if isinstance(n, dict):
        yield n
        for c in _kids(n):
            yield from _walk(c)
    elif isinstance(n, list):
        for c in n:
            yield from _walk(c)


def _text(n) -> str:
    if isinstance(n, str):
        return n
    if isinstance(n, dict):
        return "".join(_text(c) for c in _kids(n))     # ★children だけ。tag の値を拾わない
    if isinstance(n, list):
        return "".join(_text(c) for c in n)
    return ""


def _first(n, tag):
    return next((c for c in _walk(n) if isinstance(c, dict) and c.get("tag") == tag), None)


def fetch_article() -> dict:
    """e-Gov から35条を構造ごと取る。"""
    hits = egov.search(LAW_TITLE, limit=5)
    exact = [h for h in hits if h.get("law_title") == LAW_TITLE]
    if not exact:
        raise RuntimeError(f"{LAW_TITLE} が見つからない: {hits}")
    info = exact[0]
    law = egov.get_law(info["law_id"])
    art = None
    for n in _walk(law["law_full_text"]):
        if isinstance(n, dict) and n.get("tag") == "Article":
            t = _first(n, "ArticleTitle")
            if t and _text(t).strip() == ARTICLE:
                art = n
                break
    if art is None:
        raise RuntimeError(f"{ARTICLE} が取れない")
    paras = [c for c in _kids(art) if c.get("tag") == "Paragraph"]
    items = [c for c in _kids(paras[0]) if c.get("tag") == "Item"]
    return {
        "law_id": info["law_id"],
        "revision_id": info.get("revision_id", ""),
        "enforced": info.get("amendment_enforcement_date", ""),
        "caption": _text(_first(art, "ArticleCaption")).strip(),
        "paragraphs": len(paras),
        "items": [{"no": _text(_first(it, "ItemTitle")).strip(),
                   "text": _text(_first(it, "ItemSentence")).strip()} for it in items],
    }


def guidance(conn) -> dict:
    """解釈運用のどこにその号の話があるか（号 → ページと引用）。"""
    rows = conn.execute(
        "SELECT ch.source_ref, ch.text FROM knowledge_chunks ch "
        "JOIN knowledge_documents d ON d.id = ch.doc_id "
        f"WHERE d.title LIKE '{_GUIDE_TITLE}' ORDER BY ch.ord").fetchall()
    out: dict[str, dict] = {}
    for ref, text in rows:
        t = _sp(text)
        for m in _GUIDE_PAT.finditer(t):
            key = m.group(1) + ("の" + m.group(2) if m.group(2) else "")
            if key in out:
                continue
            out[key] = {"page": ref.split("/")[-1].strip(),
                        "quote": t[max(0, m.start() - 20):m.start() + 170]}
    return out


def samples(conn) -> list[tuple[str, str]]:
    """索引にある実物の重説（検証用）。"""
    ids = [r[0] for r in conn.execute(
        "SELECT id FROM knowledge_documents WHERE title LIKE '%重要事項説明書%'")]
    out = []
    for did in ids:
        title = conn.execute("SELECT title FROM knowledge_documents WHERE id=?", (did,)).fetchone()[0]
        blob = "".join(r[0] for r in conn.execute(
            "SELECT text FROM knowledge_chunks WHERE doc_id=? ORDER BY ord", (did,)))
        out.append((title, _sp(blob)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    art = fetch_article()
    print(f"e-Gov: {ARTICLE}{art['caption']} … {art['paragraphs']}項 / 第1項に {len(art['items'])}号")
    print(f"  施行日 {art['enforced']}  revision {art['revision_id']}")

    conn = sqlite3.connect(f"file:{KB}?mode=ro", uri=True)
    g = guidance(conn)
    print(f"解釈運用が号を名指ししている: {len(g)} 号ぶん")

    docs = samples(conn)
    print(f"検証に使う実物の重説: {len(docs)} 本\n")

    items, warn = [], 0
    print("=== 号ごと（解釈運用の根拠 / 実物の重説で当たった本数）===")
    for it in art["items"]:
        no = it["no"]
        kws = DETECT.get(no, [])
        hit = sum(1 for _t, b in docs if any(k in b for k in kws))
        gd = g.get(_ARABIC.get(no, ""), {})
        mark = "✅" if hit else "★"
        if not hit:
            warn += 1
        print(f"  {mark} 第{no}号  解釈運用 {gd.get('page', '—'):>4s}   実物 {hit}/{len(docs)}本"
              f"   語: {'・'.join(kws[:3])}")
        items.append({"no": no, "text": it["text"], "detect": kws,
                      "guidance": gd, "sample_hits": hit})

    print("\n=== 十四号の内訳（施行規則16条の4の3。書き漏らしが一番起きる）===")
    subs = []
    for name, kws in SUB_14.items():
        hit = sum(1 for _t, b in docs if any(k in b for k in kws))
        print(f"  {'✅' if hit else '★'} {name:18s} 実物 {hit}/{len(docs)}本")
        subs.append({"name": name, "detect": kws, "sample_hits": hit})

    if warn:
        print(f"\n★ 実物の重説に1本も当たらなかった号が {warn} 件ある。"
              "検出の語が実務の書き方と合っていない可能性がある（人が見直すこと）")

    if args.check:
        print("\n--check なので書かない。")
        return 0
    OUT.write_text(json.dumps({
        "_meta": {"article": ARTICLE, "caption": art["caption"],
                  "law_id": art["law_id"], "revision_id": art["revision_id"],
                  "enforced": art["enforced"],
                  "law_source": "e-Gov法令API（条文は現行。施行日を必ず一緒に見せること）",
                  "guidance_source": "国交省「宅地建物取引業法の解釈・運用の考え方」（知識索引）",
                  "validated_with": f"索引にある実物の重要事項説明書 {len(docs)}本",
                  "generator": "bookshelf/make_jyuusetsu_checklist.py",
                  "note": "手で編集しない（生成し直すこと）。detect は当社が決めた検出の手がかりで条文ではない。"},
        "items": items, "sub_14": subs,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n書き出した: {OUT}（{OUT.stat().st_size // 1024} KB）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
