"""Knowledge Tool（社内資料検索）。既存 kb_search.py を再利用。"""
import os

import kb_search as _kb


def kb_search(query: str, limit: int = 12):
    rows = _kb.search(query, limit=limit)
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
