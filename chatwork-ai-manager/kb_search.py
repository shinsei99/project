#!/usr/bin/env python3
"""社内ナレッジ全文検索ツール（エージェント型QAが Bash から反復的に呼ぶ）。

使い方:
  python3 kb_search.py "検索語1 検索語2 ..."
  python3 kb_search.py --docs "タイトル部分一致"   # 文書名で探す

スペース区切りの各語で LIKE 検索し、より多くの語に一致したチャンクを上位に返す。
NFKC 正規化・複合語の分割（メゾンドール都島501 → メゾンドール都島/501 など）に対応。
"""
import os
import re
import sys
import unicodedata
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db.connection import query  # noqa: E402


def tokenize(q: str):
    q = unicodedata.normalize("NFKC", q)
    toks, seen = [], set()

    def add(t):
        t = t.strip()
        if len(t) >= 2 and t not in seen:
            seen.add(t)
            toks.append(t)

    for w in q.split():
        add(w)
    for m in re.findall(r"[一-鿿゠-ヿA-Za-z0-9ー]{2,}", q):
        add(m)
        # 漢字/カタカナ/英字/数字の連なりごとに分割して個別にも検索語化
        for part in re.findall(r"[一-鿿]{2,}|[゠-ヿー]{2,}|[A-Za-z]{2,}|[0-9]{1,}", m):
            add(part)
    return toks


# どの棚を見るか（2026-08-29）。**既定は自社書類だけ。**
# 蔵書68冊・法令21点・判例173本を索引に入れたので、絞らないと業務の検索に
# 本の一般論が混ざる。必要なときだけ明示的に呼ぶ。
KINDS = {
    "自社": ("自社書類", "Dropboxの自社書類（既定）"),
    "法令": ("法令・ガイドライン", "国交省・国税庁・個情委の一次資料"),
    "判例": ("判例", "RETIO機関誌の裁判例・紛争事例"),
    "本": ("本", "蔵書68冊"),
    "全部": (None, "すべて"),
}


def _kind_sql(kind_keys):
    """--kind の指定を SQL 断片に。何も指定しなければ自社書類だけ"""
    # ★どの分岐でも会社の壁を通す（2026-08-30）。
    #   早期returnが2つあり、そこを素通りしていた。実測で新誠の場から
    #   大京商事の自社書類が10件出た。**分岐ごとに足すのではなく、必ず最後に足す。**
    cc, cargs = _company_sql()
    if not kind_keys:
        return " AND (d.source_kind IS NULL OR d.source_kind='自社書類') " + cc, list(cargs)
    vals = [KINDS[k][0] for k in kind_keys if k in KINDS and KINDS[k][0]]
    if "全部" in kind_keys:
        return " " + cc, list(cargs)
    if not vals:
        return " AND (d.source_kind IS NULL OR d.source_kind='自社書類') " + cc, list(cargs)
    marks = ",".join("?" for _ in vals)
    own = " d.source_kind IS NULL OR" if "自社" in kind_keys else ""
    return f" AND ({own} d.source_kind IN ({marks})) " + cc, vals + list(cargs)


def _company_sql():
    """会社の壁（2026-08-30 オーナー指示）。

    ★このモジュールは services/qa.py とは**別のSQL**を持っている。
      qa.py 側だけ直しても、道具（kb_search）はこちらを通るので効かない。
      実測で、新誠の場から大京商事の自社書類が10件出た。
      **同じ壁を両方に入れること。**
    自社書類はその会社のものだけ。法令・判例・本（company='共通'）は誰でも見てよい。
    """
    import os
    co = (os.environ.get("CWAI_COMPANY") or "").strip()
    if not co:
        try:
            import json
            from services.settings import get_setting
            co = json.loads(get_setting("room_company_map", "") or "{}").get("default") or ""
        except Exception:
            co = ""
    if not co:
        return "", []
    return " AND d.company IN (?, '共通') ", [co]


def search(q: str, limit: int = 12, snippet: int = 700, kinds=None):
    terms = tokenize(q)
    if not terms:
        return []
    ks, kargs = _kind_sql(kinds)
    score = defaultdict(int)
    matched = defaultdict(set)
    meta = {}
    for t in terms:
        rows = query(
            "SELECT c.id, c.text, c.source_ref, d.title, d.category, "
            "  d.source_kind, d.pub_date, d.use_scope "
            "FROM knowledge_chunks c JOIN knowledge_documents d ON d.id=c.doc_id "
            "WHERE d.active=1 AND c.text LIKE ? " + ks + "LIMIT 400",
            tuple(["%" + t + "%"] + kargs),
        )
        for r in rows:
            score[r["id"]] += 1
            matched[r["id"]].add(t)
            meta[r["id"]] = r
    ranked = sorted(score, key=lambda i: score[i], reverse=True)[:limit]
    out = []
    for i in ranked:
        r = meta[i]
        out.append((r["title"], r["category"], r["source_ref"], len(matched[i]),
                    r["text"][:snippet], r["pub_date"], r["use_scope"]))
    return out


def search_docs(title_like: str, limit: int = 30):
    return query(
        "SELECT DISTINCT title, category, filename FROM knowledge_documents "
        "WHERE active=1 AND (title LIKE ? OR filename LIKE ?) LIMIT ?",
        ("%" + title_like + "%", "%" + title_like + "%", limit),
    )


def main():
    args = sys.argv[1:]
    if args and args[0] == "--docs":
        for r in search_docs(" ".join(args[1:])):
            print(f"- {r['title']}（{r['category']}） file:{r['filename']}")
        return
    # --kind 法令,判例 のように指定する（省略すると自社書類だけ）
    kinds = None
    if "--kind" in args:
        i = args.index("--kind")
        kinds = [k.strip() for k in args[i + 1].split(",") if k.strip()]
        args = args[:i] + args[i + 2:]
    q = " ".join(args)
    if not q.strip():
        print("使い方: python3 kb_search.py \"検索語1 検索語2\" [--kind 法令,判例,本,自社,全部]")
        for k, (_, note) in KINDS.items():
            print(f"    {k:<4} … {note}")
        return
    res = search(q, kinds=kinds)
    if not res:
        print("（該当なし）検索語を変えるか、--kind で見る棚を変えてください。")
        return
    for k, (title, cat, ref, nm, text, pub, scope) in enumerate(res, 1):
        # **本は出版年と用途を必ず出す。** 古い本の法令記述をそのまま信じないため
        tag = ""
        if pub:
            tag += f" 発行:{pub[:4]}年"
        if scope == "concept":
            tag += " ★考え方のみ（法律・数値は一次資料で確認）"
        elif scope == "case":
            tag += " ［判例］"
        print(f"[{k}] 資料:{title}（{cat}） 出典:{ref} 一致語数:{nm}{tag}")
        print(text)
        print("----")


if __name__ == "__main__":
    main()
