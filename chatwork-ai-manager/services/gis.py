"""GIS / 地図の中核。**外部ライブラリを一切追加していない。**

なぜ geopandas / folium を入れなかったか（再検討しないための記録）:
  このMacは51本のアプリが共通の /usr/bin/python3 (3.9) を使い、本番の常駐worker も
  そこで動いている。geopandas は fiona/GDAL のバイナリを引き込むため、共有環境を
  壊す危険が、今回必要な機能（距離・半径・地図HTML）で得られる利益に見合わない。
  距離は Haversine（純Python）、地図は Leaflet を読むHTMLを自前生成、
  空間検索は座標計算、GeoJSON は標準 json で足りる。
  将来ポリゴン解析（町丁目・ハザード重ね）が要るなら、その時に隔離venvで shapely を足す。

Geocoding は **国土交通省 国土地理院の住所検索API**（キー不要・無料）。
  https://msearch.gsi.go.jp/address-search/AddressSearch?q=<住所>
  ※ OpenStreetMap の Nominatim は利用規約で一括ジオコーディングを禁じているため使わない。
  結果は geocode_cache に必ず保存し、同じ住所を二度外部へ問い合わせない。
"""
import datetime
import html
import json
import math
import os
import re
import time
import unicodedata
import urllib.parse
import urllib.request

from db.connection import get_conn, query, query_one
from services import config

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPS_DIR = os.path.join(APP_DIR, "maps")

GSI_URL = "https://msearch.gsi.go.jp/address-search/AddressSearch?q="
USER_AGENT = "daikyo-internal-property-tool/1.0"
# 相手は公共サービス。連続問い合わせは必ず間隔を空ける（規約以前の礼儀）
GEOCODE_INTERVAL_SEC = 1.0
_last_call = [0.0]

EARTH_RADIUS_M = 6371000.0


# ----------------------------------------------------------------- 距離
def haversine_m(lat1, lon1, lat2, lon2) -> float:
    """2点間の距離（メートル）。緯度経度の差分ではなく球面距離で計算する。"""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def fmt_distance(m: float) -> str:
    """人が読む形にする（1km未満はm、それ以上はkm）。"""
    return f"{int(round(m))}m" if m < 1000 else f"{m / 1000:.2f}km"


# ----------------------------------------------------------------- 住所の正規化
_POSTAL_RE = re.compile(r"〒?\s*\d{3}-?\d{4}")


def normalize_address(addr: str) -> str:
    """全角/半角の揺れ・郵便番号・建物名を落として問い合わせやすい形にする。"""
    if not addr:
        return ""
    s = unicodedata.normalize("NFKC", str(addr))
    s = _POSTAL_RE.sub("", s)
    s = s.replace("　", " ").strip()
    # 「大阪市都島区片町1-9-16 トーヨーコーポ」→ 建物名を落とす
    s = re.split(r"\s+", s)[0] if re.search(r"\d", re.split(r"\s+", s)[0] or "") else s
    return s.strip(" ,、")


_PREF_RE = re.compile(r"^(北海道|東京都|(?:京都|大阪)府|.{2,3}県)")


def strip_prefecture(addr: str) -> str:
    """先頭の都道府県を落とす。台帳は「大阪市…」と「大阪府大阪市…」が混在しており、
    そのまま集計すると同じ区が2グループに割れるため（2026-08-17 実データで発生）。"""
    return _PREF_RE.sub("", addr or "").strip()


def _fallbacks(addr: str):
    """完全一致で見つからないとき、末尾の番地から段階的に削って探す。"""
    yield addr
    cur = addr
    for _ in range(3):
        nxt = re.sub(r"[-‐−―ー]?\d+$", "", cur).rstrip("-‐−―ー ")
        if nxt == cur or not nxt:
            break
        cur = nxt
        yield cur


# ----------------------------------------------------------------- Geocoding
def _cache_get(q: str):
    row = query_one("SELECT * FROM geocode_cache WHERE query=?", (q,))
    return dict(row) if row else None


def _cache_put(q, lat, lon, title, status, source="gsi"):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO geocode_cache (query, lat, lon, title, source, status) "
            "VALUES (?,?,?,?,?,?) ON CONFLICT(query) DO UPDATE SET "
            "lat=excluded.lat, lon=excluded.lon, title=excluded.title, status=excluded.status",
            (q, lat, lon, title, source, status),
        )


def _is_coarse(query_str: str, title: str) -> bool:
    """返ってきた正式名が、問い合わせより**粗い**場所か判定する。

    国土地理院は存在しない町名を投げても黙って区の中心座標を返す（例:
    「大阪市都島区存在しない町」→ 正式名「大阪府大阪市都島区」）。これを検出しないと、
    町名ごとの点が全部その区の1点に重なる（2026-08-17 の取引価格の重ね地図で実際に発生）。
    """
    if not title:
        return False
    q = strip_prefecture(normalize_address(query_str))
    t = strip_prefecture(normalize_address(title))
    return bool(t) and len(t) < len(q) and q.startswith(t)


def _gsi_lookup(q: str):
    """国土地理院へ1回だけ問い合わせる。呼び出し間隔はここで守る。"""
    wait = GEOCODE_INTERVAL_SEC - (time.time() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.time()
    req = urllib.request.Request(GSI_URL + urllib.parse.quote(q),
                                 headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.load(resp)
    if not data:
        return None
    top = data[0]
    lon, lat = top["geometry"]["coordinates"][:2]
    return {"lat": float(lat), "lon": float(lon),
            "title": (top.get("properties") or {}).get("title")}


def geocode(address: str, use_cache: bool = True) -> dict:
    """住所 → 緯度経度。**キャッシュ最優先**・失敗しても例外を投げない。

    戻り: {"ok":bool, "lat":float, "lon":float, "query":str, "title":str, "status":str,
           "coarse":bool}
    coarse=True は「町名までは特定できず、区や市の中心を返された」という意味。
    物件のピン立てには使えるが、**町名ごとに点を並べる用途では捨てること**（全部同じ点になる）。
    """
    q0 = normalize_address(address)
    if not q0:
        return {"ok": False, "status": "no_address", "error": "住所が空です"}
    for q in _fallbacks(q0):
        if use_cache:
            c = _cache_get(q)
            if c and c["status"] == "ok":
                return {"ok": True, "lat": c["lat"], "lon": c["lon"], "query": q,
                        "title": c["title"], "status": "ok", "cached": True,
                        "coarse": _is_coarse(q, c["title"])}
            if c and c["status"] == "not_found":
                continue          # 前に無いと分かっている → 外部を叩かず次の候補へ
        try:
            hit = _gsi_lookup(q)
        except Exception as e:      # ネットワーク断などで全体を止めない
            _cache_put(q, None, None, None, "error")
            return {"ok": False, "status": "error", "query": q, "error": f"{type(e).__name__}: {e}"}
        if hit:
            _cache_put(q, hit["lat"], hit["lon"], hit["title"], "ok")
            return {"ok": True, "lat": hit["lat"], "lon": hit["lon"], "query": q,
                    "title": hit["title"], "status": "ok", "cached": False,
                    "coarse": _is_coarse(q, hit["title"])}
        _cache_put(q, None, None, None, "not_found")
    return {"ok": False, "status": "not_found", "query": q0,
            "error": "住所から座標を特定できませんでした"}


# ----------------------------------------------------------------- 国土数値情報（不動産情報ライブラリAPI経由）
"""
用途地域・土砂災害警戒区域・地価公示は、既存の reinfolib_api_key（国交省 不動産情報
ライブラリ）をそのまま流用する。国土数値情報そのもの（nlftp.mlit.go.jp）は都道府県
一括のシェープファイル配布のみで住所検索に向かないが、不動産情報ライブラリはこれを
スリッピーマップのベクトルタイル（z/x/y + response_format=geojson）としてAPI化して
いるため、取引価格(XIT001)と同じ「1点ずつ問い合わせる」設計にそのまま乗せられる。

ポリゴン内外判定は pure-Python のレイキャスティングで行う（shapely等の追加依存なし。
gis.py 冒頭のコメント参照）。判定ロジックは jyuusetsu-research/services/zoning_service.py
の実装を踏襲しつつ、フィールド名の既知バグ（XKT001誤用）を避け XKT002 を使う。

XKT002 = 都市計画決定GISデータ（用途地域）/ XKT029 = 国土数値情報（土砂災害警戒区域）
XPT002 = 地価公示・地価調査のポイントAPI（ポリゴンではなく点データ）
"""
_REINFOLIB_BASE = "https://www.reinfolib.mlit.go.jp/ex-api/external"


def _deg2tile(lat: float, lon: float, zoom: int):
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def _point_in_ring(lon: float, lat: float, ring) -> bool:
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


def _feature_contains(feature: dict, lon: float, lat: float) -> bool:
    geom = feature.get("geometry") or {}
    gtype = geom.get("type")
    coords = geom.get("coordinates", [])
    try:
        if gtype == "Polygon":
            return _point_in_ring(lon, lat, coords[0])
        if gtype == "MultiPolygon":
            return any(_point_in_ring(lon, lat, poly[0]) for poly in coords)
    except Exception:
        return False
    return False


def reinfolib_vector_tile(code: str, lat: float, lon: float, zoom: int = 14, extra_params=None):
    """不動産情報ライブラリのベクトルタイルAPIを1タイルぶん取得する（GeoJSON）。

    キーが無い/通信失敗時は例外を投げず {"ok": False} を返す（GIS機能全体を止めないため）。
    extra_params: XPT002（地価公示）は year が必須など、コードごとに追加パラメータが要る。
    """
    api_key = config.get("reinfolib_api_key")
    if not api_key:
        return {"ok": False, "error": "reinfolib_api_key が未設定です"}
    x, y = _deg2tile(lat, lon, zoom)
    params = {"response_format": "geojson", "z": zoom, "x": x, "y": y, **(extra_params or {})}
    url = f"{_REINFOLIB_BASE}/{code}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Ocp-Apim-Subscription-Key": str(api_key)})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.load(resp)
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return {"ok": True, "features": data.get("features", [])}


def zoning_info(lat: float, lon: float) -> dict:
    """指定地点の用途地域・建蔽率・容積率（国土数値情報 XKT002・不動産情報ライブラリ経由）。"""
    res = reinfolib_vector_tile("XKT002", lat, lon, zoom=13)
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error")}
    for feat in res["features"]:
        if _feature_contains(feat, lon, lat):
            p = feat.get("properties", {})
            return {
                "ok": True, "found": True,
                "use_area": p.get("use_area_ja") or "",
                "building_coverage_ratio": p.get("u_building_coverage_ratio_ja") or "",
                "floor_area_ratio": p.get("u_floor_area_ratio_ja") or "",
                "decision_date": p.get("decision_date") or p.get("first_decision_date") or "",
                "city_name": p.get("city_name") or "",
                "source": "国土数値情報（都市計画決定GISデータ・用途地域）／不動産情報ライブラリ",
            }
    return {"ok": True, "found": False,
            "note": "この地点は用途地域の指定が無いか、データの対象外です（都市計画区域外の可能性）"}


_SEDIMENT_PHENOMENON = {1: "急傾斜地の崩壊", 2: "土石流", 3: "地すべり"}
_SEDIMENT_ZONE = {1: "土砂災害警戒区域（イエローゾーン）", 2: "土砂災害特別警戒区域（レッドゾーン）"}


def sediment_hazard_info(lat: float, lon: float) -> dict:
    """指定地点が土砂災害警戒区域/特別警戒区域に該当するか（国土数値情報 XKT029経由）。

    区域は小さいポリゴンが多いため zoom14 で取得する（zoom13だとタイルが粗く外れやすい）。
    """
    res = reinfolib_vector_tile("XKT029", lat, lon, zoom=14)
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error")}
    hits = []
    for feat in res["features"]:
        if _feature_contains(feat, lon, lat):
            p = feat.get("properties", {})
            hits.append({
                "phenomenon": _SEDIMENT_PHENOMENON.get(p.get("A33_001"), f"不明({p.get('A33_001')})"),
                "zone_type": _SEDIMENT_ZONE.get(p.get("A33_002"), f"不明({p.get('A33_002')})"),
                "area_name": p.get("A33_005") or "",
                "address": p.get("A33_006") or "",
                "decision_date": p.get("A33_007") or "",
            })
    return {"ok": True, "in_warning_zone": bool(hits), "zones": hits,
            "source": "国土数値情報（土砂災害警戒区域データ A33）／不動産情報ライブラリ",
            "note": "都道府県が指定した区域データ。最新指定状況は自治体のハザードマップで必ず確認すること"}


def land_price_nearby(lat: float, lon: float, radius_m: float = 1500, limit: int = 10,
                      year: int = None) -> dict:
    """指定地点の近傍にある地価公示地点（国土数値情報 XPT002・不動産情報ライブラリ経由）。

    ポイントデータなので周辺タイル1枚ぶんから半径で絞り込む（取引価格APIと同じ「参考値」用途）。
    year を省略すると前年（1/1時点公示の性質上、当年ぶんはまだ無いことが多いため）。
    """
    if not year:
        year = datetime.date.today().year - 1
    res = reinfolib_vector_tile("XPT002", lat, lon, zoom=13, extra_params={"year": int(year)})
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error")}
    out = []
    for feat in res["features"]:
        geom = feat.get("geometry") or {}
        if geom.get("type") != "Point":
            continue
        plon, plat = geom["coordinates"][0], geom["coordinates"][1]
        d = haversine_m(lat, lon, plat, plon)
        if d > radius_m:
            continue
        p = feat.get("properties", {})
        price = (p.get("u_current_years_price_ja") or "").strip()
        if not price and p.get("last_years_price"):
            price = f"{int(p['last_years_price']):,}円/㎡（前年）"
        out.append({
            "place_name": p.get("place_name_ja") or p.get("location") or "",
            "address": p.get("location") or "",
            "price": price or "非公表",
            "target_year": p.get("target_year_name_ja") or "",
            "distance_m": round(d, 1), "distance": fmt_distance(d),
            "lat": plat, "lon": plon,
        })
    out.sort(key=lambda x: x["distance_m"])
    return {"ok": True, "count": len(out), "points": out[:limit],
            "source": "地価公示・地価調査（国土交通省）／不動産情報ライブラリ XPT002"}


# ----------------------------------------------------------------- 物件の取得・検索
def _row(p) -> dict:
    d = dict(p)
    d.pop("created_at", None)
    return d


def list_properties(classification=None, category=None, area=None, keyword=None,
                    only_geocoded=True, limit=500):
    """物件マスタから条件で絞る。area は住所の部分一致（例「都島区」「大阪市」）。"""
    sql = "SELECT * FROM properties WHERE active=1"
    params = []
    if only_geocoded:
        sql += " AND lat IS NOT NULL AND lon IS NOT NULL"
    if classification:
        sql += " AND classification=?"
        params.append(classification)
    if category:
        sql += " AND category=?"
        params.append(category)
    if area:
        sql += " AND address LIKE ?"
        params.append(f"%{area}%")
    if keyword:
        sql += " AND (name LIKE ? OR address LIKE ? OR owner LIKE ?)"
        params += [f"%{keyword}%"] * 3
    sql += " ORDER BY classification, category, name LIMIT ?"
    params.append(limit)
    return [_row(r) for r in query(sql, tuple(params))]


def find_property(name_or_keyword: str):
    """物件名の部分一致で1件特定する（表記ゆれに強くするため NFKC で比較）。"""
    k = unicodedata.normalize("NFKC", (name_or_keyword or "").strip())
    if not k:
        return None
    rows = [_row(r) for r in query("SELECT * FROM properties WHERE active=1")]
    exact = [r for r in rows if unicodedata.normalize("NFKC", r["name"]) == k]
    if exact:
        return exact[0]
    part = [r for r in rows if k in unicodedata.normalize("NFKC", r["name"])]
    if part:
        return sorted(part, key=lambda r: len(r["name"]))[0]
    addr = [r for r in rows if k in unicodedata.normalize("NFKC", r["address"] or "")]
    return addr[0] if addr else None


def nearby(lat, lon, radius_m=1000, exclude_property_id=None, limit=50, **filters):
    """指定地点から半径内の物件を近い順で返す（距離つき）。"""
    out = []
    for p in list_properties(only_geocoded=True, limit=2000, **filters):
        if exclude_property_id and p["property_id"] == exclude_property_id:
            continue
        d = haversine_m(lat, lon, p["lat"], p["lon"])
        if d <= radius_m:
            out.append({**p, "distance_m": round(d, 1), "distance": fmt_distance(d)})
    out.sort(key=lambda x: x["distance_m"])
    return out[:limit]


def area_stats(group="city"):
    """住所からエリアを取り出して集計する（どこに物件が集中しているか）。

    group: "city"（○○市）/ "ward"（○○区・○○市まで）/ "town"（町名まで）
    """
    counter = {}
    for p in list_properties(only_geocoded=False, limit=2000):
        a = strip_prefecture(normalize_address(p["address"] or ""))
        if not a:
            key = "(住所なし)"
        elif group == "city":
            m = re.match(r"^(.+?[市区町村])", a)
            key = m.group(1) if m else a[:6]
        elif group == "ward":
            m = re.match(r"^(.+?市.+?区|.+?[市町村])", a)
            key = m.group(1) if m else a[:8]
        else:
            m = re.match(r"^(.+?市.+?区.+?[^\d\-]*)", a)
            key = (m.group(1) if m else a)[:14]
        e = counter.setdefault(key, {"area": key, "count": 0, "categories": {}})
        e["count"] += 1
        e["categories"][p["category"] or "?"] = e["categories"].get(p["category"] or "?", 0) + 1
    return sorted(counter.values(), key=lambda x: -x["count"])


# ----------------------------------------------------------------- 出力
def to_geojson(props) -> dict:
    """GeoJSON FeatureCollection（他のGISツールへ渡せる標準形式）。"""
    feats = []
    for p in props:
        if p.get("lat") is None or p.get("lon") is None:
            continue
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [p["lon"], p["lat"]]},
            "properties": {k: v for k, v in p.items()
                           if k not in ("lat", "lon", "id") and v not in (None, "")},
        })
    return {"type": "FeatureCollection", "features": feats}


# 種別ごとの色（地図の凡例と一致させる）
CATEGORY_COLORS = {
    "マンション": "#1b2340", "ビル": "#f07c1e", "駐車場": "#2e7d32",
    "看板": "#7b1fa2", "トランク": "#00838f", "戸建": "#c62828",
}
DEFAULT_COLOR = "#5f6368"
MARKET_COLOR = "#d81b60"

# ハザードマップポータルサイト（国交省）配信のラスタタイル。地理院タイル仕様のXYZなので
# 既存のLeaflet地図にレイヤ追加するだけで重ね表示できる（バックエンドでの画像処理は不要）。
# 出典表示はポータルサイトの規約に従い凡例に必ず入れる。
HAZARD_TILE_LAYERS = {
    "flood": {
        "label": "洪水浸水想定区域（想定最大規模）",
        "url": "https://disaportaldata.gsi.go.jp/raster/01_flood_l2_shinsuishin_data/{z}/{x}/{y}.png",
        "max_zoom": 17,
    },
    "landslide": {
        "label": "土砂災害警戒区域（土石流）",
        "url": "https://disaportaldata.gsi.go.jp/raster/05_dosekiryukeikaikuiki/{z}/{x}/{y}.png",
        "max_zoom": 17,
    },
    "hightide": {
        "label": "高潮浸水想定区域",
        "url": "https://disaportaldata.gsi.go.jp/raster/03_hightide_l2_shinsuishin_data/{z}/{x}/{y}.png",
        "max_zoom": 17,
    },
}


def _esc(v):
    return html.escape(str(v)) if v not in (None, "") else ""


def build_map(props, title="管理物件マップ", center=None, circle=None,
              extra_points=None, filename=None, cluster=True, hazard_layers=None) -> dict:
    """Leaflet の地図HTMLを生成して保存する（外部ライブラリ不要。CDNのLeafletを読む）。

    props         : list_properties/nearby が返した物件
    circle        : {"lat":..,"lon":..,"radius_m":..,"label":..} 半径検索の範囲を描く
    extra_points  : [{"lat","lon","name","note","color"}] 取引価格など別レイヤの点
    hazard_layers : ["flood","landslide","hightide"] ハザードマップポータルのタイルを重ねる
    """
    pts = [p for p in props if p.get("lat") is not None and p.get("lon") is not None]
    extra = [e for e in (extra_points or []) if e.get("lat") is not None]
    if not pts and not extra and not circle:
        return {"ok": False, "error": "地図に出せる座標が1件もありません"}

    hazards = [HAZARD_TILE_LAYERS[h] for h in (hazard_layers or []) if h in HAZARD_TILE_LAYERS]

    if center:
        clat, clon = center
    elif circle:
        clat, clon = circle["lat"], circle["lon"]
    else:
        clat = sum(p["lat"] for p in pts) / len(pts)
        clon = sum(p["lon"] for p in pts) / len(pts)

    markers = []
    for p in pts:
        color = CATEGORY_COLORS.get(p.get("category"), DEFAULT_COLOR)
        rows = "".join(
            f"<tr><th>{_esc(lbl)}</th><td>{_esc(p.get(k))}</td></tr>"
            for lbl, k in (("種別", "category"), ("分類", "classification"),
                           ("住所", "address"), ("構造", "structure"),
                           ("戸数", "units"), ("交通", "access"),
                           ("オーナー", "owner"), ("距離", "distance"))
            if p.get(k)
        )
        markers.append({
            "lat": p["lat"], "lon": p["lon"], "color": color,
            "name": p.get("name") or "",
            "label": (p.get("distance") or ""),
            "popup": f"<div class='pp'><b>{_esc(p.get('name'))}</b><table>{rows}</table></div>",
        })
    for e in extra:
        markers.append({
            "lat": e["lat"], "lon": e["lon"], "color": e.get("color") or MARKET_COLOR,
            "name": e.get("name") or "", "label": e.get("label") or "", "square": True,
            "popup": f"<div class='pp'><b>{_esc(e.get('name'))}</b><br>{_esc(e.get('note'))}</div>",
        })

    legend = "".join(
        f"<div><i style='background:{c}'></i>{_esc(k)}</div>"
        for k, c in CATEGORY_COLORS.items()
        if any(p.get("category") == k for p in pts)
    )
    if extra:
        legend += f"<div><i style='background:{MARKET_COLOR}'></i>参考データ</div>"
    for h in hazards:
        legend += (f"<div><i style='background:#9c27b0;border-radius:2px'></i>{_esc(h['label'])}"
                   f"（<a href='https://disaportal.gsi.go.jp/' target='_blank'>ハザードマップポータル</a>）</div>")

    os.makedirs(MAPS_DIR, exist_ok=True)
    if not filename:
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"map-{stamp}.html"
    if not filename.endswith(".html"):
        filename += ".html"
    path = os.path.join(MAPS_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(_MAP_TEMPLATE.format(
            title=_esc(title),
            center_lat=clat, center_lon=clon,
            markers=json.dumps(markers, ensure_ascii=False),
            circle=json.dumps(circle, ensure_ascii=False) if circle else "null",
            hazard_layers=json.dumps(hazards, ensure_ascii=False),
            legend=legend,
            cluster="true" if cluster else "false",
            count=len(pts),
            generated=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        ))
    return {"ok": True, "path": path, "filename": filename, "count": len(pts),
            "center": [clat, clon]}


_MAP_TEMPLATE = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html,body{{margin:0;height:100%;font-family:-apple-system,"Hiragino Sans",sans-serif}}
  #map{{height:100%}}
  .hd{{position:absolute;z-index:500;top:10px;left:50px;background:#fff;padding:8px 14px;
      border-radius:8px;box-shadow:0 1px 6px rgba(0,0,0,.3);font-size:14px}}
  .hd b{{font-size:15px}} .hd span{{color:#666;font-size:12px;margin-left:8px}}
  .lg{{position:absolute;z-index:500;bottom:20px;right:10px;background:#fff;padding:8px 12px;
      border-radius:8px;box-shadow:0 1px 6px rgba(0,0,0,.3);font-size:12px;line-height:1.8}}
  .lg i{{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:6px}}
  .pp table{{border-collapse:collapse;margin-top:6px;font-size:12px}}
  .pp th{{text-align:left;color:#666;padding:1px 8px 1px 0;white-space:nowrap;font-weight:normal}}
  .pp td{{padding:1px 0}}
  .lbl{{background:rgba(255,255,255,.85);border-radius:3px;padding:0 3px;font-size:11px;white-space:nowrap}}
</style></head><body>
<div class="hd"><b>{title}</b><span>{count}件 / {generated}</span></div>
<div class="lg">{legend}</div>
<div id="map"></div>
<script>
const markers = {markers};
const circle = {circle};
const hazardLayers = {hazard_layers};
const map = L.map('map').setView([{center_lat}, {center_lon}], 13);
L.tileLayer('https://cyberjapandata.gsi.go.jp/xyz/pale/{{z}}/{{x}}/{{y}}.png', {{
  attribution: '<a href="https://maps.gsi.go.jp/development/ichiran.html">地理院タイル</a>', maxZoom: 18
}}).addTo(map);
hazardLayers.forEach(h => {{
  L.tileLayer(h.url, {{opacity: 0.6, maxZoom: h.max_zoom,
    attribution: '<a href="https://disaportal.gsi.go.jp/">ハザードマップポータルサイト</a>'}}).addTo(map);
}});
const bounds = [];
if (circle) {{
  L.circle([circle.lat, circle.lon], {{radius: circle.radius_m, color:'#f07c1e',
    fillColor:'#f07c1e', fillOpacity:.08, weight:2}}).addTo(map);
  bounds.push([circle.lat, circle.lon]);
}}
markers.forEach(m => {{
  const mk = L.circleMarker([m.lat, m.lon], {{radius: m.square ? 6 : 8, color:'#fff', weight:2,
    fillColor: m.color, fillOpacity: .95}}).addTo(map);
  mk.bindPopup(m.popup);
  mk.bindTooltip(m.label ? (m.name + ' <span class="lbl">' + m.label + '</span>') : m.name,
                 {{direction:'top'}});
  bounds.push([m.lat, m.lon]);
}});
if (bounds.length > 1) map.fitBounds(bounds, {{padding:[40,40]}});
else if (bounds.length === 1) map.setView(bounds[0], 16);
</script></body></html>
"""
