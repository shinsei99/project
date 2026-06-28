"""国土地理院API（無料・キー不要）で住所→緯度経度を解決する。

realestate-valuation/services/geo_service.py と同じ作法。
"""

from __future__ import annotations

import requests

_GEOCODE_URL = "https://msearch.gsi.go.jp/address-search/AddressSearch"
_REVERSE_URL = "https://mreversegeocoder.gsi.go.jp/reverse-geocoder/LonLatToAddress"


def geocode(address: str) -> tuple[float, float] | None:
    """住所 → (lat, lng)。失敗時 None。"""
    if not address:
        return None
    try:
        resp = requests.get(_GEOCODE_URL, params={"q": address}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None
    if not data:
        return None
    # GeoJSON: coordinates = [lng, lat]
    coords = data[0].get("geometry", {}).get("coordinates")
    if not coords or len(coords) < 2:
        return None
    lng, lat = float(coords[0]), float(coords[1])
    return lat, lng


def reverse_muni_code(lat: float, lng: float) -> tuple[str, str]:
    """(lat, lng) → (市区町村コード5桁, 都道府県コード2桁)。失敗時 ("","" )。"""
    try:
        resp = requests.get(_REVERSE_URL, params={"lat": lat, "lon": lng}, timeout=15)
        resp.raise_for_status()
        muni = resp.json().get("results", {}).get("muniCd", "")
    except Exception:
        return "", ""
    muni = str(muni).zfill(5) if muni else ""
    pref = muni[:2] if muni else ""
    return muni, pref


def resolve(address: str) -> dict:
    """住所→{lat, lng, muni_code, pref_code}をまとめて返す。"""
    out = {"lat": None, "lng": None, "muni_code": "", "pref_code": ""}
    geo = geocode(address)
    if not geo:
        return out
    out["lat"], out["lng"] = geo
    muni, pref = reverse_muni_code(*geo)
    out["muni_code"], out["pref_code"] = muni, pref
    return out
