"""災害リスク（洪水浸水想定・土砂災害・津波）を取得する。

**2026-08-23 実装**（それまでは常に空文字を返すスタブだった）。
国土交通省「不動産情報ライブラリ」API の災害レイヤを、地点のタイルで引いて
ポリゴンの内外を判定する。用途地域（`zoning_service`）と同じキー・同じ叩き方で、
共通部分は `reinfolib_client` にある。

| 項目 | レイヤ | 元データ | 使うズーム |
|---|---|---|---|
| 洪水浸水想定 | XKT026 | 国土数値情報 A31a（洪水浸水想定区域・**想定最大規模**） | 14（対応は14〜15） |
| 津波 | XKT028 | 国土数値情報 A40（津波浸水想定） | 14（対応は14〜15） |
| 土砂災害 | XKT029 | 国土数値情報 A33（土砂災害警戒区域） | 13（対応は11〜15） |

**コード値は公式コードリストで確認済み**（推測していない）。

- 浸水深ランク `A31a_205`: 1=0m以上0.5m未満 / 2=0.5〜3.0m / 3=3.0〜5.0m /
  4=5.0〜10.0m / 5=10.0〜20.0m / 6=20.0m以上
  （https://nlftp.mlit.go.jp/ksj/gml/codelist/water_depth_code.html）
- 現象種別 `A33_001`: 1=急傾斜地の崩壊 / 2=土石流 / 3=地滑り
  （codelist/CodeOfPhenomenon.html）
- 区域区分 `A33_002`: 1=警戒区域(指定済) / 2=特別警戒区域(指定済) /
  3=警戒区域(指定前) / 4=特別警戒区域(指定前)（codelist/CodeOfZone_h27.html）
- 津波の浸水深 `A40_003` は最初から文字列（例 "1.0～2.0m"）。コード変換は不要

**★ 出典側が課している制限（必ず画面に出す）**

国土数値情報 A33（土砂災害警戒区域）の配布ページに、都道府県ごとの但し書きがある。
そのうち **兵庫県は「本データを宅地建物取引業法に基づく重要事項の説明等の根拠と
しないで下さい」と明記している**。当社の営業エリア（加東など）が該当するため、
自動取得した値は**下調べであって重説の根拠にはできない**。県の指定図で確認する。

**「区域外」と「判定不可」を混同しない。**

- タイルに地物があって地点が外 → **区域外**（言い切ってよい）
- タイルに地物が1つも無い → **判定不可**（空文字）。データ未整備かもしれないため、
  「区域外」とは言わない。重説では「要確認」として人が調べる
"""

from typing import Dict, List, Optional, Tuple

from . import reinfolib_client as rc

# 国土地理院 ハザードマップポータル（重ねるハザードマップ）
HAZARD_PORTAL = "https://disaportal.gsi.go.jp/maps/index.html?ll={lat},{lon}&z=16"

LAYER_FLOOD = "XKT026"      # 洪水浸水想定区域（想定最大規模）
LAYER_TSUNAMI = "XKT028"    # 津波浸水想定
LAYER_SEDIMENT = "XKT029"   # 土砂災害警戒区域

ZOOM_FLOOD = 14
ZOOM_TSUNAMI = 14
ZOOM_SEDIMENT = 13

# 浸水深ランクコード（国土数値情報 water_depth_code）
DEPTH_RANK = {
    1: "0m以上0.5m未満",
    2: "0.5m以上3.0m未満",
    3: "3.0m以上5.0m未満",
    4: "5.0m以上10.0m未満",
    5: "10.0m以上20.0m未満",
    6: "20.0m以上",
}

# 現象種別コード（CodeOfPhenomenon）
PHENOMENON = {1: "急傾斜地の崩壊", 2: "土石流", 3: "地滑り"}

# H27区域コード（CodeOfZone）
ZONE_KIND = {
    1: "土砂災害警戒区域",
    2: "土砂災害特別警戒区域",
    3: "土砂災害警戒区域（指定前）",
    4: "土砂災害特別警戒区域（指定前）",
}

# 出典側が課している制限（国土数値情報 A33 の配布ページより）。都道府県コード → 注意文
PREF_NOTICE = {
    "28": "兵庫県は「本データを宅地建物取引業法に基づく重要事項の説明等の根拠と"
          "しないで下さい」としている。必ず県の指定図で確認すること。",
    "33": "岡山県は「警戒区域等の境界の確認の根拠としないこと」としている。",
    "26": "京都府はデータの商用利用を認めていない。",
}

SOURCE_FLOOD = "国土数値情報 A31a 洪水浸水想定区域（想定最大規模）／不動産情報ライブラリ XKT026"
SOURCE_TSUNAMI = "国土数値情報 A40 津波浸水想定／不動産情報ライブラリ XKT028"
SOURCE_SEDIMENT = "国土数値情報 A33 土砂災害警戒区域／不動産情報ライブラリ XKT029"


def _flood(lat: float, lon: float, key: str) -> Tuple[str, str]:
    """洪水浸水想定。戻り値は (値, 注意文)。値が空文字なら判定不可。"""
    feats = rc.fetch_features(LAYER_FLOOD, lat, lon, ZOOM_FLOOD, key)
    if feats is None or not feats:
        return "", ""
    hits = rc.features_containing(feats, lon, lat)
    if not hits:
        return "浸水想定区域外（想定最大規模）", ""

    # 同じ地点に複数の河川が重なることがある。いちばん深いランクを採る
    ranks: List[int] = []
    rivers: List[str] = []
    for f in hits:
        p = f.get("properties", {})
        try:
            ranks.append(int(p.get("A31a_205")))
        except (TypeError, ValueError):
            pass
        river = str(p.get("A31a_202") or "").strip()
        if river and river not in rivers:
            rivers.append(river)
    depth = DEPTH_RANK.get(max(ranks)) if ranks else ""
    text = "浸水想定区域内（想定最大規模）"
    if depth:
        text += "／想定浸水深 {}".format(depth)
    if rivers:
        text += "／対象河川 {}".format("・".join(rivers))
    return text, ""


def _tsunami(lat: float, lon: float, key: str) -> Tuple[str, str]:
    """津波浸水想定。戻り値は (値, 注意文)。"""
    feats = rc.fetch_features(LAYER_TSUNAMI, lat, lon, ZOOM_TSUNAMI, key)
    if feats is None or not feats:
        return "", ""
    hits = rc.features_containing(feats, lon, lat)
    if not hits:
        return "津波浸水想定区域外", ""

    depths = [str(f.get("properties", {}).get("A40_003") or "").strip() for f in hits]
    depths = [d for d in depths if d]
    text = "津波浸水想定区域内"
    if depths:
        text += "／想定浸水深 {}".format("・".join(sorted(set(depths))))
    return text, ""


def _sediment(lat: float, lon: float, key: str) -> Tuple[str, str]:
    """土砂災害警戒区域。戻り値は (値, 注意文)。"""
    feats = rc.fetch_features(LAYER_SEDIMENT, lat, lon, ZOOM_SEDIMENT, key)
    if feats is None or not feats:
        return "", ""

    # 都道府県ごとの利用制限（兵庫県は重説の根拠に使えない）
    pref = ""
    for f in feats:
        pref = str(f.get("properties", {}).get("A33_003") or "").strip()
        if pref:
            break
    notice = PREF_NOTICE.get(pref, "")

    hits = rc.features_containing(feats, lon, lat)
    if not hits:
        return "土砂災害警戒区域外", notice

    # 1 つの地点に「土石流の警戒区域」と「急傾斜地の特別警戒区域」が重なることがある
    labels: List[str] = []
    for f in hits:
        p = f.get("properties", {})
        try:
            kind = ZONE_KIND.get(int(p.get("A33_002")), "")
        except (TypeError, ValueError):
            kind = ""
        try:
            phen = PHENOMENON.get(int(p.get("A33_001")), "")
        except (TypeError, ValueError):
            phen = ""
        name = str(p.get("A33_005") or "").strip()
        label = kind or "土砂災害警戒区域"
        detail = "・".join([x for x in (phen, name) if x])
        if detail:
            label += "（{}）".format(detail)
        if label not in labels:
            labels.append(label)
    return "／".join(labels), notice


def get_hazard_detail(lat: float, lon: float) -> Dict[str, Dict[str, str]]:
    """災害リスクを項目ごとに {値, 出典, 注意} で返す（画面表示用）。"""
    key = rc.get_api_key()
    blank = {"値": "", "出典": "", "注意": ""}
    if not key or lat is None or lon is None:
        return {
            "洪水浸水想定": dict(blank),
            "土砂災害": dict(blank),
            "津波": dict(blank),
        }

    flood, flood_note = _flood(lat, lon, key)
    sediment, sediment_note = _sediment(lat, lon, key)
    tsunami, tsunami_note = _tsunami(lat, lon, key)
    return {
        "洪水浸水想定": {"値": flood, "出典": SOURCE_FLOOD, "注意": flood_note},
        "土砂災害": {"値": sediment, "出典": SOURCE_SEDIMENT, "注意": sediment_note},
        "津波": {"値": tsunami, "出典": SOURCE_TSUNAMI, "注意": tsunami_note},
    }


def get_hazard(lat: float, lon: float) -> Dict[str, str]:
    """災害リスクを取得する。取得できなければ空文字（重説では「要確認」）。"""
    detail = get_hazard_detail(lat, lon)
    return {k: v["値"] for k, v in detail.items()}


def hazard_link(lat: Optional[float], lon: Optional[float]) -> str:
    """重ねるハザードマップの該当地点 URL を返す（UI の確認導線用）。"""
    if lat is None or lon is None:
        return "https://disaportal.gsi.go.jp/"
    return HAZARD_PORTAL.format(lat=lat, lon=lon)
