#!/usr/bin/env python3
"""e-Gov 法令API（v2）の共通クライアント（2026-08-20 作成）。

**登録も申請も不要・無料・キー不要**。法令の「いま施行されている条文」を機械で引ける。
`japanpost_api.py` / `google_maps_api.py` と同じく直下に1本だけ置く。

    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import egov_law_api

使いどころ: `legal-crosscheck`（法令制限チェック）／`tokuyaku-generator`（特約条項）／
`gyomu-manual`（業務マニュアルの根拠条文）。**法改正に自動で追随できる**のが効き目。

実測で確かめたこと（2026-08-20）:

- `GET /api/2/laws?law_title=宅地建物取引業法` … 法令の検索。`law_id`（例 `327AC1000000176`）と
  **いま施行中の版**（`revision_info.law_revision_id`）が返る
- `GET /api/2/law_data/{law_id}` … 法令の全文。**`article=35` のような絞り込みは効かず**、
  常に全文が返る（宅建業法で 622KB）。条文の取り出しは手元で行う
- 全文は `law_full_text` に **{"tag", "attr", "children"} の入れ子**で入っている。
  条文は `tag="Article"` の `attr.Num`。見出しは `ArticleCaption`、本文は `Paragraph`
- 622KB を毎回取りに行くのは無駄なので、**`.egov-cache/` に7日キャッシュする**

**requests が無い環境でも動く**（2026-08-23 追加）。`chatwork-ai-manager` の worker は
launchd から `/usr/bin/python3` で動いており requests が入っていない可能性があるため、
無ければ標準ライブラリの urllib へ自動で切り替える。
"""

from __future__ import annotations

import json
import pathlib
import time
import urllib.parse
from typing import Any, Dict, List, Optional

try:  # requests があれば使う。無い環境（launchd の /usr/bin/python3 等）では urllib で代替する
    import requests
except ImportError:  # pragma: no cover - 環境依存
    requests = None
    import urllib.request

    class _Response:
        """requests.get の戻りのうち、このモジュールが使う分だけを真似る。"""

        def __init__(self, body: bytes):
            self._body = body

        def raise_for_status(self):
            return None  # urlopen は 4xx/5xx を例外にするので、ここに来た時点で成功

        def json(self):
            return json.loads(self._body.decode("utf-8"))

    class _UrllibShim:
        @staticmethod
        def get(url, timeout=30):
            req = urllib.request.Request(url, headers={"User-Agent": "egov-law-api-client/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return _Response(resp.read())

    requests = _UrllibShim()

BASE = "https://laws.e-gov.go.jp/api/2"
CACHE_DIR = pathlib.Path(__file__).resolve().parent / ".egov-cache"
CACHE_DAYS = 7
TIMEOUT = 30


class EgovError(RuntimeError):
    """検索・取得の失敗。"""


def search(title: str, limit: int = 5) -> List[Dict[str, str]]:
    """法令名で検索する。戻り値は新しい順ではなく API の並び順のまま。

    各要素: {"law_id", "law_title", "law_num", "promulgation_date", "revision_id",
             "amendment_enforcement_date"（施行日・無ければ空）}
    """
    url = "{}/laws?{}".format(BASE, urllib.parse.urlencode({"law_title": title, "limit": limit}))
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise EgovError("法令の検索に失敗しました: {}".format(e))

    out: List[Dict[str, str]] = []
    for item in data.get("laws", []):
        info = item.get("law_info", {})
        rev = item.get("revision_info", {})
        out.append({
            "law_id": info.get("law_id", ""),
            "law_title": rev.get("law_title", ""),
            "law_num": info.get("law_num", ""),
            "promulgation_date": info.get("promulgation_date", ""),
            "revision_id": rev.get("law_revision_id", ""),
            "amendment_enforcement_date": rev.get("amendment_enforcement_date", ""),
        })
    return out


def _cache_path(law_id: str) -> pathlib.Path:
    return CACHE_DIR / "{}.json".format(law_id)


def get_law(law_id: str, use_cache: bool = True) -> Dict[str, Any]:
    """法令の全文（JSON）を取る。7日以内のキャッシュがあればそれを使う。"""
    path = _cache_path(law_id)
    if use_cache and path.exists():
        age_days = (time.time() - path.stat().st_mtime) / 86400
        if age_days < CACHE_DAYS:
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass  # 壊れていたら取り直す
    try:
        resp = requests.get("{}/law_data/{}".format(BASE, law_id), timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise EgovError("法令の取得に失敗しました（{}）: {}".format(law_id, e))
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass  # キャッシュできなくても動く
    return data


def _text_of(node: Any) -> str:
    """入れ子のノードから、見える文字だけを取り出して連結する。"""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        return "".join(_text_of(c) for c in node.get("children", []))
    if isinstance(node, list):
        return "".join(_text_of(c) for c in node)
    return ""


def _walk(node: Any):
    """すべてのノードを順にたどる。"""
    if isinstance(node, dict):
        yield node
        for c in node.get("children", []):
            yield from _walk(c)
    elif isinstance(node, list):
        for c in node:
            yield from _walk(c)


def article(law_id: str, number: str) -> Optional[Dict[str, str]]:
    """条番号で1条を取り出す。戻り値 {"number", "caption", "text"} / 無ければ None。

    `number` は "35" のように算用数字の文字列（枝番は "35_2" ではなく API の Num に従う）。
    """
    body = get_law(law_id).get("law_full_text", {})
    for node in _walk(body):
        if node.get("tag") == "Article" and str(node.get("attr", {}).get("Num", "")) == str(number):
            caption, parts = "", []
            for child in node.get("children", []):
                if not isinstance(child, dict):
                    continue
                tag = child.get("tag")
                if tag == "ArticleCaption":
                    caption = _text_of(child)
                elif tag in ("Paragraph", "ArticleTitle"):
                    parts.append(_text_of(child))
            return {"number": str(number), "caption": caption, "text": "\n".join(p for p in parts if p)}
    return None


def find_articles(law_id: str, keyword: str, limit: int = 10) -> List[Dict[str, str]]:
    """本文にキーワードを含む条文を探す。戻り値は article() と同じ形の一覧。"""
    body = get_law(law_id).get("law_full_text", {})
    hits: List[Dict[str, str]] = []
    for node in _walk(body):
        if node.get("tag") != "Article":
            continue
        text = _text_of(node)
        if keyword in text:
            num = str(node.get("attr", {}).get("Num", ""))
            caption = ""
            for child in node.get("children", []):
                if isinstance(child, dict) and child.get("tag") == "ArticleCaption":
                    caption = _text_of(child)
                    break
            hits.append({"number": num, "caption": caption, "text": text})
            if len(hits) >= limit:
                break
    return hits


if __name__ == "__main__":  # 手元確認用: python3 egov_law_api.py 宅地建物取引業法 35
    import sys

    title = sys.argv[1] if len(sys.argv) > 1 else "宅地建物取引業法"
    num = sys.argv[2] if len(sys.argv) > 2 else "35"
    found = search(title, limit=3)
    for f in found:
        print("{}  {}  施行 {}".format(f["law_id"], f["law_title"], f["amendment_enforcement_date"]))
    if found:
        art = article(found[0]["law_id"], num)
        if art:
            print("\n第{}条 {}".format(art["number"], art["caption"]))
            print(art["text"][:400])
