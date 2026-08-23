# -*- coding: utf-8 -*-
"""公示地価・都道府県地価調査の標準地から、価格と周辺の状況を拾う。

不動産情報ライブラリの **XPT002**（地価公示・地価調査のポイント／国土数値情報 L01・L02）。
`PropertyData` の `公示地価` は項目だけあって**一度も埋まったことがない**空欄だった。

取れるもの（実測）:

    u_current_years_price_ja        "406,000(円/㎡)"   … 当年の価格
    last_years_price                386000              … 前年
    year_on_year_change_rate        5.2                 … 変動率(%)
    front_road_condition            "北東　4.0m　市道"  … 前面道路の方位・幅員・種別
    water_supply_availability       True                … 上水道
    gas_supply_availability         True                … 都市ガス
    sewer_supply_availability       True                … 下水道
    regulations_use_category_name_ja "第二種住居地域"
    area_division_name_ja           "市街化区域"

**ライフラインと前面道路は「その標準地」の状況であって当該物件のものではない。**
重説のライフライン欄・道路欄に**そのまま書いてはいけない**ので、
画面では「近傍の標準地の状況（参考）」と明示し、書式には入れない。

**いちばん近い標準地を採る。** 標準地は点なので内外判定ができない。
距離が離れるほど参考にならないので、`NEAR_LIMIT_M` より遠いものは使わない。
"""

import math
from typing import Dict, List, Optional

from . import reinfolib_client as rc

LAYER = "XPT002"
ZOOM = 13
YEAR = 2025

# これより遠い標準地は「近傍」と呼べないので採らない
NEAR_LIMIT_M = 1500.0


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return math.hypot(
        (lon2 - lon1) * 111000.0 * math.cos(math.radians(lat1)),
        (lat2 - lat1) * 111000.0,
    )


def _nearest(features: List[Dict], lat: float, lon: float):
    best, best_d = None, None
    for f in features or []:
        try:
            lon2, lat2 = f["geometry"]["coordinates"][:2]
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        d = _distance_m(lat, lon, lat2, lon2)
        if best_d is None or d < best_d:
            best, best_d = f, d
    return best, best_d


def get_landprice(lat: float, lon: float, year: int = YEAR) -> Dict[str, str]:
    """近傍の標準地から公示地価などを返す。取得できなければ空文字。

    戻り値のうち `公示地価` だけが `PropertyData` の項目。
    残りは画面に出す参考情報（書式には入れない）。
    """
    blank = {"公示地価": "", "_距離": "", "_前面道路": "", "_ライフライン": "",
             "_用途地域": "", "_区域区分": ""}
    key = rc.get_api_key()
    if not key or lat is None or lon is None:
        return blank

    feats = rc.fetch_features(LAYER, lat, lon, ZOOM, key, extra={"year": year})
    if not feats:
        return blank
    best, dist = _nearest(feats, lat, lon)
    if best is None or dist is None or dist > NEAR_LIMIT_M:
        return blank

    p = best.get("properties", {})
    price = str(p.get("u_current_years_price_ja") or "").strip()
    change = p.get("year_on_year_change_rate")
    text = price
    if text and change not in (None, ""):
        text += "（前年比 {}%）".format(change)

    life = []
    for label, field in (("上水道", "water_supply_availability"),
                         ("都市ガス", "gas_supply_availability"),
                         ("下水道", "sewer_supply_availability")):
        value = p.get(field)
        if value is True:
            life.append(label + "有")
        elif value is False:
            life.append(label + "無")

    return {
        "公示地価": text,
        "_距離": "約{:,.0f}m".format(dist),
        "_前面道路": str(p.get("front_road_condition") or "").strip(),
        "_ライフライン": "・".join(life),
        "_用途地域": str(p.get("regulations_use_category_name_ja") or "").strip(),
        "_区域区分": str(p.get("area_division_name_ja") or "").strip(),
    }
