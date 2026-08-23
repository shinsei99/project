"""用途地域・建ぺい率・容積率を取得する。

無料でキー不要のリアルタイム用途地域 API は存在しないため、
国土交通省「不動産情報ライブラリ」API（無料・要登録キー）を任意で利用する。

- 環境変数 REINFOLIB_API_KEY / st.secrets["reinfolib_api_key"] があれば自動取得を試みる
- なければ空欄で継続（重説ドラフトでは「要手動確認」として扱う）

**レイヤ番号の注意（2026-08-20 実測）**
- 用途地域は **XKT002**。XKT001 は「都市計画区域・区域区分」で、用途地域は入っていない
  （2026-08-19 まで XKT001 を叩いていたため、キーがあるのに常に空だった）
- 返るプロパティ名は `use_area_ja` / `u_building_coverage_ratio_ja` / `u_floor_area_ratio_ja`。
  **建ぺい率・容積率は `"80%"` `"400%"` のように単位付きの文字列**で返るので `%` を足さない
- **防火地域は XKT014 で取れる**（2026-08-23 実測で判明。プロパティ `fire_prevention_ja` に
  「防火地域」「準防火地域」が入る。対応ズームは 11〜15 で、**z13 を使う**。
  2026-08-20 に XKT001〜XKT007 だけを見て「レイヤが無い」と結論していたのは調べ足らずだった）
- **高度地区は依然として取れない**。XKT024 は名前が似ているが **「高度利用地区」**
  （容積率の最低限度等を定める別制度）なので流用しない。空欄のまま返す

ポリゴン内外判定は pure-Python のレイキャスティングで行う（追加依存なし）。
"""

import math
import os
from typing import Dict, List, Optional, Tuple

import requests

from . import reinfolib_client

API_BASE = "https://www.reinfolib.mlit.go.jp/ex-api/external"
LAYER_USE_AREA = "XKT002"  # 用途地域（XKT001 は都市計画区域なので誤り）
LAYER_FIRE = "XKT014"     # 防火地域・準防火地域
ZOOM_FIRE = 13            # 対応は 11〜15。高ズームだと地物が間引かれる
REINFOLIB_URL = "{}/{}".format(API_BASE, LAYER_USE_AREA)
TIMEOUT = 15
ZOOM = 13  # 用途地域 API が対応するズーム（11〜15）

# 地点を含むポリゴンが無いときに「最寄り」で救済してよい距離の上限（メートル）。
# 道路中心・ポリゴン境界のわずかなズレだけを拾う。これが無いと、用途地域の
# 定めが無い地点（市街化調整区域・山間部など）で **2.9km 先の地域** を返していた
# （2026-08-20 に加東市・六甲山中の座標で実測）。重説ドラフトに入ると事故になる。
NEAR_LIMIT_M = 100.0


def get_api_key() -> str:
    """APIキーを取得（st.secrets 優先、無ければ環境変数 REINFOLIB_API_KEY）。"""
    try:
        import streamlit as st

        if "reinfolib_api_key" in st.secrets:
            return str(st.secrets["reinfolib_api_key"]).strip()
    except Exception:
        pass
    return os.environ.get("REINFOLIB_API_KEY", "").strip()


def _deg2tile(lat: float, lon: float, zoom: int) -> Tuple[int, int]:
    """緯度経度 → スリッピーマップのタイル座標 (x, y)。"""
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def _point_in_ring(lon: float, lat: float, ring: List[List[float]]) -> bool:
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


def _feature_contains(feature: Dict, lon: float, lat: float) -> bool:
    geom = feature.get("geometry", {})
    gtype = geom.get("type")
    coords = geom.get("coordinates", [])
    try:
        if gtype == "Polygon":
            return _point_in_ring(lon, lat, coords[0])
        if gtype == "MultiPolygon":
            for poly in coords:
                if _point_in_ring(lon, lat, poly[0]):
                    return True
    except Exception:
        return False
    return False


def _centroid(feature: Dict) -> Optional[Tuple[float, float]]:
    """ポリゴンの外周の重心（最寄り判定用の粗い代表点）。"""
    geom = feature.get("geometry", {})
    gtype = geom.get("type")
    coords = geom.get("coordinates", [])
    try:
        if gtype == "Polygon":
            ring = coords[0]
        elif gtype == "MultiPolygon":
            ring = coords[0][0]
        else:
            return None
        if not ring:
            return None
        return (
            sum(p[0] for p in ring) / len(ring),
            sum(p[1] for p in ring) / len(ring),
        )
    except Exception:
        return None


def _rings(feature: Dict) -> List[List[List[float]]]:
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


def _boundary_distance_m(feature: Dict, lon: float, lat: float) -> Optional[float]:
    """地点からポリゴン外周の頂点までの最短距離（メートル・近似）。"""
    best = None
    cos_lat = math.cos(math.radians(lat))
    for ring in _rings(feature):
        for point in ring:
            d = math.hypot(
                (point[0] - lon) * 111000.0 * cos_lat,
                (point[1] - lat) * 111000.0,
            )
            if best is None or d < best:
                best = d
    return best


def _pick_feature(features: List[Dict], lon: float, lat: float) -> Optional[Dict]:
    """地点を含むポリゴン。無ければ NEAR_LIMIT_M 以内の最寄りポリゴンだけを返す。

    遠いポリゴンで代用すると「用途地域の定めが無い土地」に他所の用途地域が
    入ってしまうため、離れている場合は None（＝空欄＝要手動確認）にする。
    """
    for feat in features:
        if _feature_contains(feat, lon, lat):
            return feat
    best, best_d = None, None
    for feat in features:
        d = _boundary_distance_m(feat, lon, lat)
        if d is None:
            continue
        if best_d is None or d < best_d:
            best, best_d = feat, d
    if best is not None and best_d is not None and best_d <= NEAR_LIMIT_M:
        return best
    return None


def _with_percent(value) -> str:
    """`"80%"` はそのまま、`80` のような数値だけの場合に `%` を補う。

    API は `"80%"` と `"60.0%"` の両方を返してくるので、`.0` は落として揃える。
    """
    text = str(value or "").strip()
    if not text:
        return ""
    number = text[:-1] if text.endswith("%") else text
    if number.endswith(".0"):
        number = number[:-2]
    return "{}%".format(number)


def get_zoning(lat: float, lon: float) -> Dict[str, str]:
    """用途地域等を取得する。取得できなければ空文字。

    防火地域は XKT014 から取る（2026-08-23 追加）。高度地区は該当レイヤが無いため
    常に空欄（空欄のときは comment_service が「都市計画図での確認が必要」と書く）。
    """
    result = {
        "用途地域": "",
        "建ぺい率": "",
        "容積率": "",
        "防火地域": "",
        "高度地区": "",
    }
    api_key = get_api_key()
    if not api_key or lat is None or lon is None:
        return result

    x, y = _deg2tile(lat, lon, ZOOM)
    try:
        resp = requests.get(
            REINFOLIB_URL,
            params={"response_format": "geojson", "z": ZOOM, "x": x, "y": y},
            headers={"Ocp-Apim-Subscription-Key": api_key},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        features = resp.json().get("features", [])
    except Exception:
        return result

    result["防火地域"] = _get_fire_zone(lat, lon, api_key)

    feat = _pick_feature(features, lon, lat)
    if not feat:
        return result

    props = feat.get("properties", {})
    result["用途地域"] = str(props.get("use_area_ja", "") or "").strip()
    result["建ぺい率"] = _with_percent(props.get("u_building_coverage_ratio_ja"))
    result["容積率"] = _with_percent(props.get("u_floor_area_ratio_ja"))
    return result


def _get_fire_zone(lat: float, lon: float, api_key: str) -> str:
    """防火地域・準防火地域（XKT014）。

    用途地域と違い **最寄りでの代用はしない**。防火地域は隣の街区で切り替わるので、
    100m 先の指定を借りてくると誤りになる。地点を含むポリゴンだけを見る。

    - 地点を含む → 「防火地域」「準防火地域」
    - タイルに地物はあるが地点は外 → **「指定なし」**（言い切ってよい）
    - タイルに地物が1つも無い → 空文字（＝判定不可。都市計画区域外の可能性もある）
    """
    features = reinfolib_client.fetch_features(LAYER_FIRE, lat, lon, ZOOM_FIRE, api_key)
    if features is None or not features:
        return ""
    hits = reinfolib_client.features_containing(features, lon, lat)
    if not hits:
        return "指定なし"
    return str(hits[0].get("properties", {}).get("fire_prevention_ja") or "").strip()
