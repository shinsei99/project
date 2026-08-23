"""国土交通省「不動産情報ライブラリ」API の共通クライアント。

用途地域（`zoning_service`）と災害リスク（`hazard_service`）が同じ叩き方をするため、
タイル計算・APIアクセス・ポリゴン内外判定をここ1本に集約する。

**実測で分かったこと（2026-08-23・このPCで確認）**

- エンドポイントは `https://www.reinfolib.mlit.go.jp/ex-api/external/<レイヤ>`。
  キーは **HTTPヘッダ `Ocp-Apim-Subscription-Key`**（クエリパラメータではない）
- **レイヤごとに使えるズームが違う**。範囲外を指定すると HTTP 400 で
  「不正なズーム値（z）が指定されたため、検索できませんでした。」が返る
  （例: 洪水 XKT026 と 津波 XKT028 は **z14〜15 だけ**）
- **同じ地点でもズームによって返る件数が変わる**（高ズームほど間引かれる）。
  XKT014（防火地域）は z14 で1件・z15 で0件になった。したがって
  **各レイヤで使えるいちばん粗いズームを使う**（間引きで拾い漏らさないため）
- 返るのはタイルに掛かる地物なので、**地点が属するタイルを引けば
  その地点を含むポリゴンは必ず入っている**。内外判定はこちらで行う
"""

import math
import os
from typing import Dict, List, Optional, Tuple

import requests

API_BASE = "https://www.reinfolib.mlit.go.jp/ex-api/external"
TIMEOUT = 30


def get_api_key() -> str:
    """APIキーを取得（st.secrets 優先、無ければ環境変数 REINFOLIB_API_KEY）。"""
    try:
        import streamlit as st

        if "reinfolib_api_key" in st.secrets:
            return str(st.secrets["reinfolib_api_key"]).strip()
    except Exception:
        pass
    return os.environ.get("REINFOLIB_API_KEY", "").strip()


def deg2tile(lat: float, lon: float, zoom: int) -> Tuple[int, int]:
    """緯度経度 → スリッピーマップのタイル座標 (x, y)。"""
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def fetch_features(
    layer: str, lat: float, lon: float, zoom: int, api_key: str = ""
) -> Optional[List[Dict]]:
    """レイヤの GeoJSON を取得して features を返す。

    **戻り値の 3 状態を混同しないこと**（重説では「未確認」と「該当なし」は別物）。

    - `None` … 取得できなかった（キー無し・通信失敗・APIエラー）＝**判定不可**
    - `[]`   … 取得できたが、そのタイルに地物が1つも無い＝**データ未整備の可能性**
    - `[...]`… 取得できた
    """
    key = api_key or get_api_key()
    if not key or lat is None or lon is None:
        return None
    x, y = deg2tile(lat, lon, zoom)
    try:
        resp = requests.get(
            "{}/{}".format(API_BASE, layer),
            params={"response_format": "geojson", "z": zoom, "x": x, "y": y},
            headers={"Ocp-Apim-Subscription-Key": key},
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            return None
        return resp.json().get("features") or []
    except Exception:
        return None


def point_in_ring(lon: float, lat: float, ring: List[List[float]]) -> bool:
    """レイキャスティングによる多角形内外判定。ring は [[lon,lat],...]。"""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-12) + xi
        ):
            inside = not inside
        j = i
    return inside


def rings(feature: Dict) -> List[List[List[float]]]:
    """地物の外周リング一覧（Polygon / MultiPolygon の外側だけ）。"""
    geom = feature.get("geometry", {})
    gtype = geom.get("type")
    coords = geom.get("coordinates", [])
    try:
        if gtype == "Polygon":
            return [coords[0]]
        if gtype == "MultiPolygon":
            return [poly[0] for poly in coords]
    except Exception:
        return []
    return []


def feature_contains(feature: Dict, lon: float, lat: float) -> bool:
    """地物が地点を含むか。"""
    for ring in rings(feature):
        if point_in_ring(lon, lat, ring):
            return True
    return False


def features_containing(features: List[Dict], lon: float, lat: float) -> List[Dict]:
    """地点を含む地物だけを返す（土砂災害は複数の区域が重なることがある）。"""
    return [f for f in features or [] if feature_contains(f, lon, lat)]


def boundary_distance_m(feature: Dict, lon: float, lat: float) -> Optional[float]:
    """地点からポリゴン外周の頂点までの最短距離（メートル・近似）。"""
    best = None
    cos_lat = math.cos(math.radians(lat))
    for ring in rings(feature):
        for point in ring:
            d = math.hypot(
                (point[0] - lon) * 111000.0 * cos_lat,
                (point[1] - lat) * 111000.0,
            )
            if best is None or d < best:
                best = d
    return best
