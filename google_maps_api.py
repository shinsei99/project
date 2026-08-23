#!/usr/bin/env python3
"""Google Maps の共通クライアント（2026-08-20 作成）。

複数アプリ（jyuusetsu-research / flyer-creator / kaitori-dm-maker など）から使うため、
`japanpost_api.py` と同じく **直下に1本だけ置く**。アプリ側からはこう読む:

    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import google_maps_api

キーは **`.env.google-maps`（直下・gitignore・600）**。値をコードに書かない。

    GOOGLE_MAPS_SERVER_KEY=...   # サーバー用（Geocoding / Directions / Static）
    GOOGLE_MAPS_WEB_KEY=...      # 公開ページ用（リファラ制限 https://daikyocorp.co.jp/*）
    GOOGLE_MAPS_EMBED_KEY=...    # 社内画面用（**Maps Embed だけに制限**。任意）

**社内画面（localhost / 192.168.x.x）から Embed を出すときは `GOOGLE_MAPS_EMBED_KEY` が要る。**
`GOOGLE_MAPS_WEB_KEY` はリファラが `https://daikyocorp.co.jp/*` に限定されているため、
社内画面から使うと **403** になる（2026-08-20 実測）。Embed は無制限・無料なので、
**Maps Embed API だけに制限したキー**を別に作れば、万一漏れても課金は発生しない。
未設定のあいだは `GOOGLE_MAPS_WEB_KEY` にフォールバックする（＝公開ページ側は今までどおり）。

## ジオコーディングの使い分け（2026-08-20 実測。ここが肝）

**Google に一律で置き換えてはいけない。** 国土地理院（無料・キー不要）と比べた結果:

| 住所 | ずれ | Google の location_type | 用途地域の判定 |
|---|---|---|---|
| 大阪市中央区本町4-2-12 | 21m | ROOFTOP | 同じ |
| 千代田区丸の内1-1-1 | 62m | ROOFTOP | 同じ |
| 世田谷区北沢2-23-12 | 18m | ROOFTOP | 同じ |
| **兵庫県加東市社1** | **892m** | **APPROXIMATE** | **★違う**（地理院が正しい） |

番地まで揃った住所は Google が建物単位（ROOFTOP）で強いが、**`APPROXIMATE` が返るときは
地理院より大きく外す**。用途地域・ハザードはポリゴンの内外判定なので、外すと結論が変わる。
→ **ROOFTOP / RANGE_INTERPOLATED のときだけ Google を採用**し、それ以外は地理院に任せる。

## 料金（2026-08-19 調べ。詳細は GOOGLE_MAPS_API.md）

Geocoding は **月10,000回まで無料**、超過分 $5/1,000。社内利用の規模ではほぼ $0。
**Street View / Maps の Embed は無制限で無料**（画像API=Static は有料枠）。
※ **予算アラートと日次クォータはまだ未設定**（`API_STATUS.md` の A-2 ⑧）。

## 規約で気をつけること

- **ストリートビューは印刷物に一切使えない**（紙チラシ・DM 不可。画面表示のみ）
- SV と 地理院地図・ハザードマップを**同一画面に並べない**（別タブなら可）
- Geocoding の緯度経度の保存は原則30日（自アプリの機能を直接支える用途は無期限・Service Terms 6.3.2）
- 取得した画像は保存せず、都度APIから表示する
"""

from __future__ import annotations

import os
import pathlib
import sys
from typing import Any, Dict, Optional

_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import http_compat  # requests が無い環境（launchd の /usr/bin/python3）でも動かすための互換層

requests = http_compat.get_requests()

ENV_PATH = pathlib.Path(__file__).resolve().parent / ".env.google-maps"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
STREETVIEW_META_URL = "https://maps.googleapis.com/maps/api/streetview/metadata"
TIMEOUT = 15

# この精度のときだけ Google を採用する（上の実測を参照）
PRECISE_TYPES = ("ROOFTOP", "RANGE_INTERPOLATED")


class GoogleMapsError(RuntimeError):
    """キー未設定・API エラーをまとめて表す。"""


def _load_env() -> Dict[str, str]:
    """`.env.google-maps` を読む（環境変数が先。無ければファイル）。"""
    values: Dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip().strip('"').strip("'")
    for k in ("GOOGLE_MAPS_SERVER_KEY", "GOOGLE_MAPS_WEB_KEY"):
        if os.environ.get(k):
            values[k] = os.environ[k].strip()
    return values


def server_key() -> str:
    """サーバー用キー。無ければ空文字（呼び出し側は無料APIへ退避する）。"""
    return _load_env().get("GOOGLE_MAPS_SERVER_KEY", "")


def web_key() -> str:
    """公開ページ用キー（リファラ制限つき）。無ければ空文字。"""
    return _load_env().get("GOOGLE_MAPS_WEB_KEY", "")


def embed_key() -> str:
    """埋め込み（Embed）に使うキー。

    社内画面用の `GOOGLE_MAPS_EMBED_KEY` を優先し、無ければ公開ページ用にフォールバックする。
    フォールバック時は社内画面（localhost 等）で 403 になる（リファラ制限のため）。
    """
    env = _load_env()
    return env.get("GOOGLE_MAPS_EMBED_KEY", "") or env.get("GOOGLE_MAPS_WEB_KEY", "")


def geocode(address: str) -> Optional[Dict[str, Any]]:
    """住所 → 緯度経度。取れなければ None。

    戻り値: {"lat", "lon", "precision", "precise"(bool), "formatted_address", "place_id"}
    `precise` が False のときは **国土地理院のほうが正確なことがある**ので、
    呼び出し側は無料APIの結果を優先すること。
    """
    address = (address or "").strip()
    key = server_key()
    if not address or not key:
        return None
    try:
        resp = requests.get(
            GEOCODE_URL,
            params={"address": address, "language": "ja", "region": "jp", "key": key},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None
    if data.get("status") != "OK" or not data.get("results"):
        return None
    result = data["results"][0]
    geometry = result.get("geometry", {})
    location = geometry.get("location", {})
    precision = geometry.get("location_type", "")
    return {
        "lat": float(location.get("lat")),
        "lon": float(location.get("lng")),
        "precision": precision,
        "precise": precision in PRECISE_TYPES,
        "formatted_address": result.get("formatted_address", ""),
        "place_id": result.get("place_id", ""),
    }


def streetview_metadata(lat: float, lon: float, radius: int = 50) -> Optional[Dict[str, Any]]:
    """その地点にストリートビューがあるか。**メタデータの取得は無料**。

    戻り値: {"pano_id", "date", "lat", "lon"} / 無ければ None。
    `date` は撮影年月（例 "2021-08"）。`pano_id` は無期限に保存してよい。
    """
    key = server_key()
    if not key or lat is None or lon is None:
        return None
    try:
        resp = requests.get(
            STREETVIEW_META_URL,
            params={"location": "{},{}".format(lat, lon), "radius": radius, "key": key},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None
    if data.get("status") != "OK":
        return None
    loc = data.get("location", {})
    return {
        "pano_id": data.get("pano_id", ""),
        "date": data.get("date", ""),
        "lat": loc.get("lat"),
        "lon": loc.get("lng"),
    }


def streetview_embed_url(lat: float, lon: float, heading: int = 0, pitch: int = 0) -> str:
    """埋め込み用のストリートビューURL（**Embed は無制限・無料**）。

    印刷は不可。ハザードマップ等と同一画面に並べない（別タブにする）。
    """
    key = embed_key()
    if not key or lat is None or lon is None:
        return ""
    return (
        "https://www.google.com/maps/embed/v1/streetview"
        "?key={}&location={},{}&heading={}&pitch={}&fov=90".format(key, lat, lon, heading, pitch)
    )


def map_embed_url(lat: float, lon: float, zoom: int = 17) -> str:
    """埋め込み用の地図URL（**Embed は無制限・無料**）。"""
    key = embed_key()
    if not key or lat is None or lon is None:
        return ""
    return "https://www.google.com/maps/embed/v1/place?key={}&q={},{}&zoom={}".format(
        key, lat, lon, zoom
    )


if __name__ == "__main__":  # 手元確認用: python3 google_maps_api.py "住所"
    import sys

    query = sys.argv[1] if len(sys.argv) > 1 else "大阪府大阪市中央区本町4-2-12"
    hit = geocode(query)
    print("geocode:", hit)
    if hit:
        print("streetview:", streetview_metadata(hit["lat"], hit["lon"]))
