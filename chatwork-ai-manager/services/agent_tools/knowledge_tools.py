"""Knowledge Tool（社内資料検索）。既存 kb_search.py を再利用。"""
import kb_search as _kb


def kb_search(query: str, limit: int = 12):
    rows = _kb.search(query, limit=limit)
    results = [
        {"title": t, "category": cat, "source": ref, "matched_terms": nm, "text": text}
        for (t, cat, ref, nm, text) in rows
    ]
    return {"ok": True, "count": len(results), "results": results}
