"""アイテム: フリー写真を探して取り込む（Openverse）

なぜ要るか:
  「フリー素材を使って」と言われても、`assets/` は人が手で置く前提で空のままだった。
  結果、どのテーマでも**文字だけのスライド**になっていた。
  テーマは毎回変わるので、**その場で言葉から探せる**素材源が要る。

なぜ Openverse か:
  - **APIキーが要らない**（登録・課金なし）
  - CC0・パブリックドメイン・CC BY など**再利用が許された画像だけ**を横断検索する
  - Flickr・Wikimedia など複数の出所をまとめて引ける

守ること（重要）:
  - `license_type=commercial` で引く。**NC（非営利限定）・ND（改変禁止）は取らない**
  - CC BY / BY-SA は**出典表示が要る**。取り込んだ画像の作者・ライセンス・出典URLを
    必ず記録し、紙面やスライドに出せるようにする（credits.json）
  - 人物が写った写真は、肖像の扱いが別問題として残る。**広告に使う前は人が確認する**
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

NAME = "free_photos"
LABEL = "フリー写真を探す（Openverse）"
DESCRIPTION = "テーマの言葉から、再利用が許された写真を探して取り込む（APIキー不要）"

ENDPOINT = "https://api.openverse.org/v1/images/"
UA = {"User-Agent": "agent-platform/1.0 (free material search)"}
MIN_BYTES = 40 * 1024
MIN_LONG_SIDE = 800

# 出典表示が要るライセンス
NEEDS_CREDIT = ("by", "by-sa", "by-nd", "sa")


def available() -> Tuple[bool, str]:
    try:
        import requests  # noqa: F401
    except Exception:
        return False, "requests 未導入"
    if _pexels_key():
        return True, "フリー写真を言葉から探します（Pexels＋Openverse）"
    return True, "フリー写真を言葉から探します（Openverse・鍵不要）"


def _pexels_key() -> str:
    """Pexelsの鍵。**無料（登録のみ・支払い不要）**。

    Openverse は鍵が要らない代わりに、写真の質にムラがある
    （「japanese shopping street」でバーミンガムの中華街が出た）。
    Pexels は人が選んだ写真だけで、商用利用も出典表示も自由。
    鍵があるときはこちらを優先し、無ければ Openverse に落ちる。
    """
    import os

    try:
        from core.config import get_settings

        value = getattr(get_settings(), "pexels_key", "")
        if value:
            return str(value)
    except Exception:
        pass
    return os.getenv("PEXELS_API_KEY", "").strip()


def _search_pexels(query: str, count: int, orientation: str) -> List[Dict[str, Any]]:
    import requests

    key = _pexels_key()
    if not key:
        return []
    params = {"query": str(query or "").strip(), "per_page": max(1, min(count, 20))}
    if orientation:
        params["orientation"] = {"wide": "landscape", "tall": "portrait",
                                 "square": "square"}.get(orientation, orientation)
    try:
        resp = requests.get("https://api.pexels.com/v1/search", params=params,
                            headers={"Authorization": key, **UA}, timeout=25)
        resp.raise_for_status()
        photos = resp.json().get("photos") or []
    except Exception:
        return []
    return [{"url": (p.get("src") or {}).get("large2x")
                    or (p.get("src") or {}).get("large"),
             "title": str(p.get("alt") or "")[:80],
             "creator": str(p.get("photographer") or "")[:60],
             "license": "Pexels", "license_code": "pexels",
             "source": p.get("url", ""), "provider": "Pexels"}
            for p in photos if (p.get("src") or {}).get("large")][:count]


def search(query: str, count: int = 6, orientation: str = "") -> List[Dict[str, Any]]:
    """言葉で探す。**商用利用が許されたものだけ**。

    orientation は "landscape" / "tall" / "square"（Openverseの `aspect_ratio`）。
    スライドの枠に合う向きを指定すると、切り取りが少なくて済む。
    """
    import requests

    # 質の良い方から順に試す
    picked = _search_pexels(query, count, orientation)
    if picked:
        return picked

    params = {"q": str(query or "").strip(), "license_type": "commercial",
              "page_size": max(1, min(int(count) * 2, 20)), "mature": "false"}
    if orientation:
        params["aspect_ratio"] = orientation
    try:
        resp = requests.get(ENDPOINT, params=params, headers=UA, timeout=25)
        resp.raise_for_status()
        results = resp.json().get("results") or []
    except Exception:
        return []

    found = []
    for item in results:
        url = item.get("url")
        if not url:
            continue
        found.append({
            "url": url,
            "title": str(item.get("title") or "")[:80],
            "creator": str(item.get("creator") or "")[:60],
            "license": ("%s %s" % (str(item.get("license") or "").upper(),
                                   str(item.get("license_version") or ""))).strip(),
            "license_code": str(item.get("license") or "").lower(),
            "source": item.get("foreign_landing_url") or item.get("source") or "",
            "provider": str(item.get("provider") or ""),
        })
        if len(found) >= count:
            break
    return found


def credit(item: Dict[str, Any]) -> str:
    """紙面に出す出典の1行。CC BY 系は表示が要る。"""
    if not item:
        return ""
    if str(item.get("license_code", "")) not in NEEDS_CREDIT:
        return ""
    who = item.get("creator") or "作者不明"
    return "%s（%s / %s）" % (item.get("title") or "写真", who,
                              item.get("license") or "CC")


def download(items: List[Dict[str, Any]], dest_dir, prefix: str = "free"
             ) -> List[Dict[str, Any]]:
    """取り込む。小さすぎる画像と、画像でないものは捨てる。

    出典は `credits.json` にまとめて残す。**後から誰でも確認できるようにする**のが目的。
    """
    import requests

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for index, item in enumerate(items or [], start=1):
        try:
            resp = requests.get(item["url"], headers=UA, timeout=30)
            resp.raise_for_status()
        except Exception:
            continue
        if len(resp.content) < MIN_BYTES:
            continue
        kind = str(resp.headers.get("Content-Type", "")).lower()
        if not kind.startswith("image/"):
            continue
        suffix = ".png" if "png" in kind else ".jpg"
        path = dest_dir / ("%s_%02d%s" % (prefix, index, suffix))
        path.write_bytes(resp.content)
        size = _size(path)
        if not size or max(size) < MIN_LONG_SIDE:
            path.unlink(missing_ok=True)
            continue
        record = dict(item)
        record.update({"path": str(path), "width": size[0], "height": size[1]})
        saved.append(record)

    if saved:
        _write_credits(dest_dir, saved)
    return saved


def _size(path):
    try:
        from PIL import Image

        with Image.open(path) as img:
            return img.size
    except Exception:
        return None


def _write_credits(dest_dir: Path, items: List[Dict[str, Any]]) -> None:
    path = Path(dest_dir) / "credits.json"
    existing = []
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            existing = []
    existing += [{"file": Path(x["path"]).name, "title": x.get("title"),
                  "creator": x.get("creator"), "license": x.get("license"),
                  "source": x.get("source"), "provider": x.get("provider")}
                 for x in items]
    path.write_text(json.dumps(existing, ensure_ascii=False, indent=2),
                    encoding="utf-8")


def fetch(query: str, dest_dir, count: int = 4, orientation: str = "",
          prefix: Optional[str] = None) -> List[Dict[str, Any]]:
    """探して取り込むまでを1回で。"""
    items = search(query, count=count, orientation=orientation)
    if not items:
        return []
    safe = "".join(ch for ch in str(query) if ch.isalnum() or ch in "ぁ-んァ-ヶ一-龠")
    return download(items, dest_dir, prefix=prefix or ("free_%s" % safe[:10]))
