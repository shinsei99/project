"""Knowledge Tool（社内資料検索）。既存 kb_search.py を再利用。"""
import os

import kb_search as _kb
from services import company_scope as CS


def kb_search(query: str, limit: int = 12, kinds=None):
    """社内資料を検索する。

    kinds: 見に行く棚。省略すると**自社書類だけ**（従来と同じ）。
        "法令" … 国交省・国税庁・個情委の一次資料（最新版・そのまま根拠にできる）
        "判例" … RETIO機関誌の裁判例・紛争事例
        "本"   … 蔵書68冊（★発行年に注意。古い本は考え方だけ使う）
        "全部" … すべて
        例) kinds=["法令","判例"] / kinds="法令"

    **質問が制度・法律・トラブルの話なら、必ず kinds を指定して呼び直すこと。**
    自社書類だけでは「うちのやり方」しか出てこず、根拠を示せない。
    """
    if isinstance(kinds, str):
        kinds = [k.strip() for k in kinds.split(",") if k.strip()]
    rows = _kb.search(query, limit=limit, kinds=kinds)
    results = [
        {
            "title": t, "category": cat, "source": ref, "matched_terms": nm, "text": text,
            "pub_date": pub_date, "use_scope": use_scope,
        }
        for (t, cat, ref, nm, text, pub_date, use_scope) in rows
    ]
    return {"ok": True, "count": len(results), "results": results}


def kb_read_document(path: str, max_pages: int = 30):
    """指定ファイルの中身をその場で読む（未索引のスキャン画像PDFは claude vision でOCR）。

    kb_search はヒットしないが、全ファイル一覧・過去の会話・フォルダ構成などから
    フルパスが分かっている資料（スキャン画像PDF等）を読んで直接答えを出すためのツール。
    読んだ内容は自動的に社内資料索引にも登録されるので、次回以降は kb_search でも見つかる。
    """
    from db.connection import query, query_one
    from services import config, knowledge

    # ★共有フォルダは既定の会社（大京商事）のもの。他社の場からは読ませない。
    #   kb_search には会社の壁を入れてあるが、この道具はパス直指定なので**壁を迂回できる**。
    #   ここを塞がないと、文書のパスさえ分かれば中身が読めてしまう（2026-08-30）。
    if not CS.is_default_company():
        return CS.deny(what="共有フォルダの資料")
    root = config.get("knowledge_source_dir")
    if not root:
        return {"ok": False, "error": "knowledge_source_dir が未設定です"}
    root_abs = os.path.abspath(root)

    p = path if os.path.isabs(path) else os.path.join(root_abs, path)
    p = os.path.normpath(p)
    if not (p == root_abs or p.startswith(root_abs + os.sep)):
        return {"ok": False, "error": "許可されたフォルダ外のパスです"}
    if not os.path.isfile(p):
        return {"ok": False, "error": f"ファイルが見つかりません: {p}"}

    result = knowledge.ingest_file(
        p, category=knowledge.category_of(root_abs, p), ocr_fallback=True,
        force=True, ocr_max_pages=max_pages,
    )
    if result.get("skipped"):
        return {"ok": False, "error": result.get("reason", "抽出失敗")}

    doc = query_one(
        "SELECT id FROM knowledge_documents WHERE filepath=? AND active=1 ORDER BY version DESC LIMIT 1",
        (p,),
    )
    if not doc:
        return {"ok": False, "error": "索引化に失敗しました"}
    chunks = query(
        "SELECT ord, text, source_ref FROM knowledge_chunks WHERE doc_id=? ORDER BY ord",
        (doc["id"],),
    )
    text = "\n\n".join(f"【{c['source_ref']}】\n{c['text']}" for c in chunks)
    return {
        "ok": True,
        "path": p,
        "used_ocr": bool(result.get("used_ocr")),
        "chunk_count": len(chunks),
        "text": text[:20000],
    }
