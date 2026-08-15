"""アイテム: 住所 ⇄ 緯度経度（国土地理院・APIキー不要）

realestate-valuation / legal-crosscheck が使っているのと同じ公開エンドポイント。
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

NAME = "geo"
LABEL = "住所→緯度経度（国土地理院）"
DESCRIPTION = "住所から緯度経度を引く。地図・ハザード・周辺施設の起点に使う。キー不要"

_GEOCODE_URL = "https://msearch.gsi.go.jp/address-search/AddressSearch"
_REVERSE_URL = "https://mreversegeocoder.gsi.go.jp/reverse-geocoder/LonLatToAddress"


def available() -> Tuple[bool, str]:
    try:
        import requests  # noqa: F401
    except Exception:
        return False, "requests 未導入"
    return True, "キー不要で使えます"


def geocode(address: str, timeout: int = 20) -> Optional[Dict[str, Any]]:
    """住所 → {"lat","lon","title"}。見つからなければ None。"""
    import requests

    resp = requests.get(_GEOCODE_URL, params={"q": address}, timeout=timeout)
    resp.raise_for_status()
    items = resp.json()
    if not items:
        return None
    top = items[0]
    lon, lat = top["geometry"]["coordinates"]
    return {"lat": lat, "lon": lon, "title": top["properties"].get("title", address)}


def reverse(lat: float, lon: float, timeout: int = 20) -> Optional[Dict[str, Any]]:
    import requests

    resp = requests.get(_REVERSE_URL, params={"lat": lat, "lon": lon}, timeout=timeout)
    resp.raise_for_status()
    results = (resp.json() or {}).get("results")
    return results or None
