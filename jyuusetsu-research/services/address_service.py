"""住所 → 緯度経度・最寄駅 を取得する。

- ジオコーディング: **国土地理院（無料・キー不要）を基本**とし、
  Google Geocoding が **建物単位（ROOFTOP / RANGE_INTERPOLATED）** を返したときだけそちらを採る
- 最寄駅: HeartRails Express API（無料・キー不要）

API 失敗時はアプリを止めず、空の結果を返す（呼び出し側で空欄継続）。

**なぜ「Google に一本化」しないのか（2026-08-20 実測）**
番地まで揃った住所では Google が 15〜60m の精度で地理院より良いが、
`APPROXIMATE` が返る住所（例「兵庫県加東市社1」）では **892m 外し、用途地域の判定まで変わった**
（地理院が正しかった）。用途地域・ハザードはポリゴンの内外判定なので、外すと結論が変わる。
判定材料は `location_type` なので、精度が出たときだけ採用する。
Google のキーが無いPCでは、そのまま従来どおり地理院だけで動く。
"""

import pathlib
import sys
from typing import Dict, Optional, Tuple

import requests

# 直下の共通クライアント（google_maps_api.py）を読む。キーが無ければ使わないだけ。
_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
try:
    import google_maps_api
except Exception:  # 共通クライアントが無い環境でも動かす
    google_maps_api = None

GSI_GEOCODE_URL = "https://msearch.gsi.go.jp/address-search/AddressSearch"
HEARTRAILS_URL = "http://express.heartrails.com/api/json"
TIMEOUT = 10


def _gsi_geocode(address: str) -> Optional[Tuple[float, float]]:
    """国土地理院の住所検索（無料・キー不要）。失敗時は None。"""
    try:
        resp = requests.get(GSI_GEOCODE_URL, params={"q": address}, timeout=TIMEOUT)
        resp.raise_for_status()
        results = resp.json()
        if not results:
            return None
        # GeoJSON: coordinates = [lon, lat]
        lon, lat = results[0]["geometry"]["coordinates"]
        return float(lat), float(lon)
    except Exception:
        return None


def geocode_detail(address: str) -> Dict:
    """住所を緯度経度に変換し、**どちらのAPIで・どの精度で**取れたかも返す。

    戻り値: {"coords": (lat, lon) or None, "source": "Google(ROOFTOP)"/"国土地理院"/"",
             "precise": bool}
    """
    address = (address or "").strip()
    empty = {"coords": None, "source": "", "precise": False}
    if not address:
        return empty

    hit = google_maps_api.geocode(address) if google_maps_api else None
    if hit and hit.get("precise"):
        return {
            "coords": (hit["lat"], hit["lon"]),
            "source": "Google({})".format(hit.get("precision", "")),
            "precise": True,
        }

    gsi = _gsi_geocode(address)
    if gsi:
        return {"coords": gsi, "source": "国土地理院", "precise": False}

    # 地理院が引けないときだけ、精度の低い Google の結果を使う（無いよりはよい）
    if hit:
        return {
            "coords": (hit["lat"], hit["lon"]),
            "source": "Google({}・要確認)".format(hit.get("precision", "")),
            "precise": False,
        }
    return empty


def geocode(address: str) -> Optional[Tuple[float, float]]:
    """住所を緯度経度 (lat, lon) に変換する。失敗時は None。"""
    return geocode_detail(address)["coords"]


def nearest_station(lat: float, lon: float) -> Dict[str, str]:
    """緯度経度から最寄駅と距離を取得する（HeartRails Express）。

    戻り値: {"最寄駅": "...駅（...線）", "駅距離": "約 ... m"}
    失敗時は空文字。
    """
    result = {"最寄駅": "", "駅距離": ""}
    if lat is None or lon is None:
        return result
    try:
        resp = requests.get(
            HEARTRAILS_URL,
            params={"method": "getStations", "x": lon, "y": lat},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        stations = resp.json().get("response", {}).get("station", [])
        if not stations:
            return result
        st = stations[0]  # 距離順で先頭が最寄り
        name = st.get("name", "")
        line = st.get("line", "")
        distance = st.get("distance", "")  # 例 "350m"
        if name:
            result["最寄駅"] = "{}駅（{}）".format(name, line) if line else "{}駅".format(name)
        if distance:
            result["駅距離"] = "約 {}".format(distance)
    except Exception:
        return result
    return result


def investigate(address: str) -> Dict:
    """住所からの自動調査の入口。

    戻り値:
      {
        "coords": (lat, lon) or None,
        "data": { PropertyData にマージするキー群 },
      }
    """
    detail = geocode_detail(address)
    coords = detail["coords"]
    data = {"所在地": address.strip()} if address else {}
    if coords:
        lat, lon = coords
        data.update(nearest_station(lat, lon))
    return {"coords": coords, "data": data, "coords_source": detail["source"]}
