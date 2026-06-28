"""行政の「正解」（用途地域・建ぺい率・容積率）を取得するサービス。

優先:
  1. 国交省「不動産情報ライブラリAPI」XKT002（都市計画決定情報・用途地域）
     ※無料APIキーが必要。緯度経度→タイル座標(z/x/y)に変換して問い合わせる。
  2. キー未設定・通信失敗・該当なしの場合は内蔵モックにフォールバックし、
     必ず AdminMaster を返す（仕様: モックで画面が動くことを最優先）。

国交省 不動産情報ライブラリ: https://www.reinfolib.mlit.go.jp/
"""

from __future__ import annotations

import math
import os

import requests

try:
    import streamlit as st
except Exception:  # streamlit外（テスト等）でも import できるように
    st = None

from models.legal_check_data import AdminMaster

_API_BASE = "https://www.reinfolib.mlit.go.jp/ex-api/external"
_ZOOM = 13  # 用途地域GISの推奨ズーム

# 用途地域コード → 名称（国交省コード体系）
_USE_DISTRICT_NAMES = {
    "1": "第一種低層住居専用地域",
    "2": "第二種低層住居専用地域",
    "3": "第一種中高層住居専用地域",
    "4": "第二種中高層住居専用地域",
    "5": "第一種住居地域",
    "6": "第二種住居地域",
    "7": "準住居地域",
    "8": "近隣商業地域",
    "9": "商業地域",
    "10": "準工業地域",
    "11": "工業地域",
    "12": "工業専用地域",
    "21": "田園住居地域",
}

# ---- モックマスター（住所キーワード → 行政正解） ----
# 国交省APIが使えない場合のデモ用。代表的な値で照合ロジックを動かすため。
_MOCK_MASTERS: list[tuple[tuple[str, ...], AdminMaster]] = [
    (("新宿", "渋谷", "中央区", "千代田"),
     AdminMaster("商業地域", 80.0, 600.0, "防火地域", "", source="モック(都心商業)")),
    (("世田谷", "杉並", "練馬", "武蔵野"),
     AdminMaster("第一種低層住居専用地域", 50.0, 100.0, "準防火地域", "第2種高度地区", source="モック(住宅地)")),
    (("港区", "目黒", "文京"),
     AdminMaster("第一種住居地域", 60.0, 300.0, "準防火地域", "", source="モック(住居)")),
]
_MOCK_DEFAULT = AdminMaster(
    "第一種住居地域", 60.0, 200.0, "準防火地域", "", source="モック(既定値)"
)


def get_api_key() -> str:
    """st.secrets['reinfolib_api_key'] → 環境変数 REINFOLIB_API_KEY の順で取得。"""
    if st is not None:
        try:
            key = st.secrets.get("reinfolib_api_key", "")
            if key:
                return str(key)
        except Exception:
            pass
    return os.environ.get("REINFOLIB_API_KEY", "")


def _latlng_to_tile(lat: float, lng: float, z: int) -> tuple[int, int]:
    """緯度経度 → XYZタイル座標。"""
    lat_rad = math.radians(lat)
    n = 2 ** z
    x = int((lng + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def _from_api(lat: float, lng: float, api_key: str) -> AdminMaster | None:
    """XKT002 用途地域GISへ問い合わせ。取得できれば AdminMaster、なければ None。"""
    x, y = _latlng_to_tile(lat, lng, _ZOOM)
    try:
        resp = requests.get(
            f"{_API_BASE}/XKT002",
            params={"response_format": "geojson", "z": _ZOOM, "x": x, "y": y},
            headers={"Ocp-Apim-Subscription-Key": api_key},
            timeout=20,
        )
        resp.raise_for_status()
        features = resp.json().get("features", [])
    except Exception:
        return None
    if not features:
        return None

    # 複数ポリゴンが返るため、最初の有効なものを採用
    for feat in features:
        p = feat.get("properties", {})
        code = str(p.get("youto_chiki", p.get("use_area_ja", "")) or "")
        name = _USE_DISTRICT_NAMES.get(code, p.get("use_area_ja", "") or "")
        kenpei = _to_float(p.get("kenpei", p.get("building_coverage_ratio")))
        yoseki = _to_float(p.get("yoseki", p.get("floor_area_ratio")))
        if name or kenpei:
            return AdminMaster(
                use_district=name,
                building_coverage=kenpei,
                floor_area_ratio=yoseki,
                fire_zone="",
                source="国交省API(XKT002)",
            )
    return None


def _to_float(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _from_mock(address: str) -> AdminMaster:
    for keywords, master in _MOCK_MASTERS:
        if any(kw in address for kw in keywords):
            # コピーして返す（dataclassは可変なので参照共有を避ける）
            return AdminMaster(**{**master.__dict__})
    return AdminMaster(**{**_MOCK_DEFAULT.__dict__})


def research(address: str, lat: float | None, lng: float | None,
             api_key: str | None = None) -> AdminMaster:
    """行政正解マスターを返す。API失敗時はモックで必ず値を返す。"""
    key = api_key if api_key is not None else get_api_key()
    if key and lat is not None and lng is not None:
        got = _from_api(lat, lng, key)
        if got is not None:
            return got
    return _from_mock(address or "")
