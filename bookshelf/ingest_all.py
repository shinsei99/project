# -*- coding: utf-8 -*-
"""本・法令・判例を知識索引へ入れ、本棚に配置する。

**既存の自社書類（source_kind が NULL）には触らない。** 新しく入れるものだけ
source_kind / pub_date / use_scope を立てるので、既定の検索からは外れる
（services/qa.py の _kind_clause 参照）。
"""
import json, os, sys, time
sys.path.insert(0, "/Users/apple/chatwork-ai-manager")
from db.connection import get_conn
from services import knowledge

S = "/private/tmp/claude-501/-Users-apple/b1bdf458-cb66-42ac-8dd3-e0a46d301b4a/scratchpad/ocr"
BOOKS = os.environ.get(
    "BOOKSHELF_BOOKS_DIR",
    os.path.expanduser("~/Library/CloudStorage/Dropbox-個人/CLAUDE/書籍"))
# ★Claude が作るデータの置き場は個人Dropboxの `CLAUDE/` の下に集める（CLAUDE.md 3-c）。
#   2026-09-01 にオーナー指示で `Dropbox-個人/一次資料` から移した。
#   直書きせず環境変数で差し替えられるようにしてある（置き場が変わっても直すのは.envだけ）。
PRIM = os.environ.get(
    "BOOKSHELF_PRIM_DIR",
    os.path.expanduser("~/Library/CloudStorage/Dropbox-個人/CLAUDE/一次資料"))


def shelf_id(conn, name, note="", prefer_new=0):
    conn.execute("INSERT OR IGNORE INTO knowledge_shelf(name, note, prefer_new) VALUES (?,?,?)",
                 (name, note, prefer_new))
    return conn.execute("SELECT id FROM knowledge_shelf WHERE name=?", (name,)).fetchone()[0]


def put(path, category, kind, scope, pub, shelf):
    """1件を索引へ入れて棚に置く。既に同じ内容が入っていれば何もしない"""
    r = knowledge.ingest_file(path, category=category)
    if r.get("skipped"):
        return None, "テキストなし"
    doc_id = r.get("doc_id")
    if not doc_id:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT id FROM knowledge_documents WHERE filepath=? AND active=1 "
                "ORDER BY version DESC LIMIT 1", (path,)).fetchone()
            doc_id = row[0] if row else None
    if not doc_id:
        return None, "doc_id不明"
    with get_conn() as conn:
        conn.execute("UPDATE knowledge_documents SET source_kind=?, pub_date=?, use_scope=? WHERE id=?",
                     (kind, pub, scope, doc_id))
        sid = shelf_id(conn, shelf)
        conn.execute("INSERT OR IGNORE INTO knowledge_shelf_member(shelf_id, doc_id) VALUES (?,?)",
                     (sid, doc_id))
    return doc_id, r.get("chunks")


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    n_ok = n_ng = 0
    t0 = time.time()

    if what in ("law", "all"):
        with get_conn() as c:
            shelf_id(c, "法令・ガイドライン", "国交省・国税庁・個情委の一次資料。**本と食い違ったらこちらが正**", 1)
        for f in sorted(os.listdir(PRIM)):
            if not f.endswith(".pdf"):
                continue
            p = os.path.join(PRIM, f)
            d, ch = put(p, "法令・一次資料", "法令・ガイドライン", "full", None, "法令・ガイドライン")
            print(("  ○ " if d else "  × ") + f"{f[:56]:<56} {ch}")
            n_ok += bool(d); n_ng += (not d)

    if what in ("case", "all"):
        with get_conn() as c:
            shelf_id(c, "判例・紛争事例", "RETIO機関誌（不動産適正取引推進機構）10年分", 1)
        R = os.path.join(PRIM, "RETIO判例・実務")
        for f in sorted(os.listdir(R)):
            if not f.endswith(".pdf"):
                continue
            d, ch = put(os.path.join(R, f), "判例・紛争事例", "判例", "case", None, "判例・紛争事例")
            n_ok += bool(d); n_ng += (not d)
        print(f"  RETIO: {n_ok}件まで完了")

    if what in ("book", "all"):
        assign = json.load(open(f"{S}/assign.json", encoding="utf-8"))
        meta = json.load(open(f"{S}/bookmeta.json", encoding="utf-8"))
        for title, a in sorted(assign.items()):
            if a["scope"] == "none":
                continue
            p = os.path.join(BOOKS, title + ".pdf")
            if not os.path.exists(p):
                print(f"  × 見つからない: {title}"); n_ng += 1; continue
            pub = str(meta.get(title, {}).get("pubdate") or a.get("year") or "")
            d, ch = put(p, a["shelf"], "本", a["scope"], pub, a["shelf"])
            mark = "○" if d else "×"
            print(f"  {mark} {a['shelf']:<12} {pub[:4]} {a['scope']:<7} {title[:36]}")
            n_ok += bool(d); n_ng += (not d)

    print(f"\n完了 {n_ok}件 / 失敗 {n_ng}件 / {time.time()-t0:.0f}秒")
