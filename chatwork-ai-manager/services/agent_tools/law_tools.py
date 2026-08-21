"""e-Gov 法令API（v2）ツール — 法令の条文を**原文で**引く。

- law_search:        法令名から法令IDを探す
- law_article:       条番号で1条を取り出す（例: 宅地建物取引業法 第35条）
- law_find_articles: 本文にキーワードを含む条を探す（条番号が分からないとき）

実体は**直下の共有クライアント `egov_law_api.py`**（キー不要・公的データ・コピーを作らない）。

なぜ要るか: 社員からの「原状回復はどこまで請求できるか」「更新拒絶の要件は」といった質問に、
AIの記憶で答えると条文が古かったり、条番号を取り違えたりする。**e-Gov の現行条文をそのまま
引いて示せば、根拠が確認できる形で返せる**（施行日も一緒に返る）。

使い分け:
  - 社内の運用・書式の話 → kb_search（社内資料）
  - 法律そのものの条文   → このTool

注意: 条文は**AIの解釈ではなく原文**として引用する。法的な判断そのものは人が行う。
"""
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# 不動産業務でよく引く法令の別名 → 正式名称
_ALIAS = {
    "宅建業法": "宅地建物取引業法",
    "宅建": "宅地建物取引業法",
    "借地借家": "借地借家法",
    "民法": "民法",
    "区分所有法": "建物の区分所有等に関する法律",
    "マンション管理適正化法": "マンションの管理の適正化の推進に関する法律",
    "品確法": "住宅の品質確保の促進等に関する法律",
    "消費者契約法": "消費者契約法",
    "都計法": "都市計画法",
    "建基法": "建築基準法",
    "賃貸住宅管理業法": "賃貸住宅の管理業務等の適正化に関する法律",
}
_MAX_TEXT = 4000  # 1条が長すぎるとChatworkに貼れないので頭を切る


def _import():
    import egov_law_api
    return egov_law_api


def _trim(a):
    if a and isinstance(a.get("text"), str) and len(a["text"]) > _MAX_TEXT:
        a = dict(a)
        a["text"] = a["text"][:_MAX_TEXT] + "\n…（以下略。全文は e-Gov で確認）"
    return a


def _resolve(eg, law):
    """法令名でも法令IDでも受ける。戻り: (law_id, 見出し情報 or None, エラー文 or None)"""
    s = str(law or "").strip()
    if not s:
        return None, None, "法令名（または法令ID）を渡してください"
    # 法令IDは "403AC0000000090" のような英数字15桁前後
    if s.isalnum() and any(c.isdigit() for c in s) and len(s) >= 12:
        return s, None, None
    title = _ALIAS.get(s, s)
    try:
        hits = eg.search(title, 5)
    except Exception as e:
        return None, None, f"{type(e).__name__}: {e}"
    if not hits:
        return None, None, f"法令が見つかりません: {law}"
    return hits[0].get("law_id"), hits[0], None


def law_search(title, limit=5):
    """法令名で検索して法令IDを得る。「宅建業法」のような通称も引ける。"""
    eg = _import()
    q = _ALIAS.get(str(title or "").strip(), str(title or "").strip())
    if not q:
        return {"ok": False, "error": "法令名を渡してください"}
    try:
        hits = eg.search(q, int(limit))
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return {"ok": True, "query": q, "count": len(hits), "laws": hits,
            "source": "e-Gov 法令API v2"}


def law_article(law, number):
    """条番号で1条を取り出す。law は法令名でも法令IDでもよい。number は "35" のような算用数字。"""
    eg = _import()
    law_id, hit, err = _resolve(eg, law)
    if err:
        return {"ok": False, "error": err}
    try:
        got = eg.article(law_id, str(number).strip())
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    if not got:
        return {"ok": False, "error": f"第{number}条が見つかりません（枝番は本則の条番号で指定する）",
                "law_id": law_id, "law_title": (hit or {}).get("law_title")}
    return {"ok": True, "law_id": law_id,
            "law_title": (hit or {}).get("law_title"),
            "law_num": (hit or {}).get("law_num"),
            "enforced": (hit or {}).get("amendment_enforcement_date"),
            "article": _trim(got),
            "source": "e-Gov 法令API v2（現行条文）"}


def law_find_articles(law, keyword, limit=5):
    """条番号が分からないとき、本文にキーワードを含む条を探す。"""
    eg = _import()
    law_id, hit, err = _resolve(eg, law)
    if err:
        return {"ok": False, "error": err}
    if not str(keyword or "").strip():
        return {"ok": False, "error": "keyword を渡してください"}
    try:
        hits = eg.find_articles(law_id, str(keyword).strip(), int(limit))
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return {"ok": True, "law_id": law_id,
            "law_title": (hit or {}).get("law_title"),
            "keyword": keyword, "count": len(hits),
            "articles": [_trim(a) for a in hits],
            "source": "e-Gov 法令API v2（現行条文）"}
