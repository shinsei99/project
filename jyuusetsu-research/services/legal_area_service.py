# -*- coding: utf-8 -*-
"""区域指定（地区計画・都市計画道路・急傾斜地・地すべり・自然公園・立地適正化）を取得する。

重説の「都市計画法・建築基準法以外の法令に基づく制限」は **64の法律**が並んでいて、
宅建士が1つずつ「該当するか」を見ている（土地建物用で実測）。
そのうち**区域が全国データで公開されているもの**は機械で判定できる。

| 項目 | レイヤ | 重説のどこ |
|---|---|---|
| 地区計画 | XKT023 | 都市計画法の「地区計画の有無」 |
| 都市計画道路 | XKT030 | 都市計画施設（道路）の区域内か |
| 急傾斜地崩壊危険区域 | XKT022 | 64法令の「**急傾斜地法**」 |
| 地すべり防止区域 | XKT021 | 64法令の「**地すべり等防止法**」 |
| 自然公園地域 | XKT019 | 64法令の「**自然公園法**」 |
| 立地適正化計画区域 | XKT003 | 64法令の「都市再生特別措置法」（※自動チェックはしない・下記） |

**自動でチェックを入れるのは「区域内＝その法律の制限を受ける」と言い切れる3つだけ**
（急傾斜地法・地すべり等防止法・自然公園法）。

立地適正化計画は**区域内であることが制限を意味しない**（都市再生特別措置法の届出義務は
居住誘導区域**外**の行為で生じる）。解釈が要るので画面に出すだけにして、
チェックは宅建士に委ねる。地区計画・都市計画道路は 64法令ではなく
「都市計画法」の欄の話なので、これも表示にとどめる。

`hazard_service` と同じで、**「区域外」と「判定不可」を混同しない**。
タイルに地物が1件も無ければ空欄（要確認）にする。
"""

from typing import Dict, List, Optional, Tuple

from . import reinfolib_client as rc

# レイヤと、使うズーム（対応範囲のいちばん粗いところ。実測で確認済み）
LAYERS = {
    "地区計画": ("XKT023", 13),
    "都市計画道路": ("XKT030", 13),
    "急傾斜地崩壊危険区域": ("XKT022", 13),
    "地すべり防止区域": ("XKT021", 11),
    "自然公園": ("XKT019", 11),
    "立地適正化計画区域": ("XKT003", 13),
}

# 区域名として使えそうなプロパティ（レイヤごとに名前が違う）
_NAME_KEYS = (
    "plan_name", "planning_road_ja", "region_name", "address",
    "kubun_name_ja", "area_classification_ja", "OBJ_NAME_ja", "A33_005",
)

_OUTSIDE = "区域外"


def _label(props: Dict) -> str:
    for key in _NAME_KEYS:
        value = str(props.get(key) or "").strip()
        if value:
            return value
    return ""


def _one(layer: str, zoom: int, lat: float, lon: float, key: str) -> str:
    """1レイヤ分の判定。区域内なら名称つきで返す。空文字は判定不可。"""
    feats = rc.fetch_features(layer, lat, lon, zoom, key)
    if feats is None or not feats:
        return ""
    hits = rc.features_containing(feats, lon, lat)
    if not hits:
        return _OUTSIDE
    names: List[str] = []
    for f in hits:
        name = _label(f.get("properties", {}))
        if name and name not in names:
            names.append(name)
    return "区域内（{}）".format("・".join(names[:3])) if names else "区域内"


def get_areas(lat: float, lon: float) -> Dict[str, str]:
    """区域指定をまとめて取得する。取得できない項目は空文字。"""
    result = {name: "" for name in LAYERS}
    key = rc.get_api_key()
    if not key or lat is None or lon is None:
        return result
    for name, (layer, zoom) in LAYERS.items():
        result[name] = _one(layer, zoom, lat, lon, key)
    return result


def applies(value: str) -> bool:
    """「区域内」＝その法律の制限を受ける、と判断してよいか。"""
    text = str(value or "").strip()
    return bool(text) and _OUTSIDE not in text
