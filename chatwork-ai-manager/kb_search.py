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


def search(q: str, limit: int = 12, snippet: int = 700):
    terms = tokenize(q)
    if not terms:
        return []
    score = defaultdict(int)
    matched = defaultdict(set)
    meta = {}
    for t in terms:
        rows = query(
            "SELECT c.id, c.text, c.source_ref, d.title, d.category "
            "FROM knowledge_chunks c JOIN knowledge_documents d ON d.id=c.doc_id "
            "WHERE d.active=1 AND c.text LIKE ? LIMIT 400",
            ("%" + t + "%",),
        )
        for r in rows:
            score[r["id"]] += 1
            matched[r["id"]].add(t)
            meta[r["id"]] = r
    ranked = sorted(score, key=lambda i: score[i], reverse=True)[:limit]
    out = []
    for i in ranked:
        r = meta[i]
        out.append((r["title"], r["category"], r["source_ref"], len(matched[i]), r["text"][:snippet]))
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
    q = " ".join(args)
    if not q.strip():
        print("使い方: python3 kb_search.py \"検索語1 検索語2\"")
        return
    res = search(q)
    if not res:
        print("（該当なし）検索語を変えて再検索してください。")
        return
    for k, (title, cat, ref, nm, text) in enumerate(res, 1):
        print(f"[{k}] 資料:{title}（{cat}） 出典:{ref} 一致語数:{nm}")
        print(text)
        print("----")


if __name__ == "__main__":
    main()
