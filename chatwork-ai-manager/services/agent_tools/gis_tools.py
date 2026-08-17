"""GIS / 地図のTool。**常駐AgentとターミナルのClaude Codeが同じこれを使う。**

地図処理を2系統に分けて重複実装しないための共通層。実体は services/gis.py。
市場データ（取引価格）は**既存の reinfolib_tools を再利用**し、ここでは重複実装しない。
地図に重ねたいときは gis_create_map の extra_points に渡す。
"""
import os

from services import gis
from services import settings

LAN_HOST = "192.168.1.105"        # 社内LANでの管理画面ホスト（.url 配布と同じ）


def _map_result(res, title):
    if not res.get("ok"):
        return res
    return {
        "ok": True, "count": res["count"], "path": res["path"],
        "filename": res["filename"], "title": title,
        "open_hint": (f"社内LANから見る場合は 管理画面 http://{LAN_HOST}:8540 の"
                      f"「🗺 物件マップ」で『{res['filename']}』を選ぶ。"
                      f"このMacで直接開くなら open '{res['path']}'"),
    }


def gis_geocode(address: str):
    """住所 → 緯度経度（国土地理院・結果はキャッシュ）。"""
    return gis.geocode(address)


def gis_property_search(keyword=None, classification=None, category=None, area=None, limit=100):
    """物件マスタを検索する（物件名/住所/オーナー、分類=自社/管理/仲介、種別、エリア）。"""
    rows = gis.list_properties(keyword=keyword, classification=classification,
                               category=category, area=area,
                               only_geocoded=False, limit=int(limit))
    return {"ok": True, "count": len(rows), "properties": [
        {k: r.get(k) for k in ("property_id", "name", "category", "classification",
                               "address", "units", "access", "lat", "lon", "geo_status")}
        for r in rows]}


def gis_distance(from_property=None, to_property=None, from_address=None, to_address=None):
    """2地点の距離（物件名でも住所でも指定できる）。"""
    def resolve(prop, addr, label):
        if prop:
            p = gis.find_property(prop)
            if not p:
                return None, f"物件が見つかりません（{label}）: {prop}"
            if p.get("lat") is None:
                return None, f"座標が未取得の物件です（{label}）: {p['name']}"
            return {"name": p["name"], "lat": p["lat"], "lon": p["lon"]}, None
        if addr:
            g = gis.geocode(addr)
            if not g.get("ok"):
                return None, f"住所から座標を特定できません（{label}）: {addr}"
            return {"name": addr, "lat": g["lat"], "lon": g["lon"]}, None
        return None, f"{label} が指定されていません"

    a, err = resolve(from_property, from_address, "起点")
    if err:
        return {"ok": False, "error": err}
    b, err = resolve(to_property, to_address, "終点")
    if err:
        return {"ok": False, "error": err}
    m = gis.haversine_m(a["lat"], a["lon"], b["lat"], b["lon"])
    return {"ok": True, "from": a["name"], "to": b["name"],
            "distance_m": round(m, 1), "distance": gis.fmt_distance(m),
            "note": "直線距離（道なりではない）"}


def gis_nearby_properties(property=None, address=None, lat=None, lon=None,
                          radius_m=1000, classification=None, category=None, limit=30):
    """指定地点/物件から半径内の管理物件を近い順に返す。radius_m は自由な数値でよい。"""
    origin_name = None
    exclude = None
    if property:
        p = gis.find_property(property)
        if not p:
            return {"ok": False, "error": f"物件が見つかりません: {property}"}
        if p.get("lat") is None:
            return {"ok": False, "error": f"座標が未取得です: {p['name']}（住所: {p.get('address') or '空'}）"}
        lat, lon, origin_name, exclude = p["lat"], p["lon"], p["name"], p["property_id"]
    elif address:
        g = gis.geocode(address)
        if not g.get("ok"):
            return {"ok": False, "error": f"住所から座標を特定できません: {address}"}
        lat, lon, origin_name = g["lat"], g["lon"], address
    if lat is None or lon is None:
        return {"ok": False, "error": "物件名・住所・緯度経度のいずれかを指定してください"}

    filters = {}
    if classification:
        filters["classification"] = classification
    if category:
        filters["category"] = category
    rows = gis.nearby(float(lat), float(lon), radius_m=float(radius_m),
                      exclude_property_id=exclude, limit=int(limit), **filters)
    return {"ok": True, "origin": origin_name, "origin_lat": lat, "origin_lon": lon,
            "radius_m": float(radius_m), "count": len(rows),
            "properties": [{k: r.get(k) for k in ("property_id", "name", "category",
                                                  "classification", "address",
                                                  "distance", "distance_m", "lat", "lon")}
                           for r in rows]}


def gis_area_stats(group="ward"):
    """エリア別の物件数（どこに集中しているか）。group: city / ward / town。"""
    rows = gis.area_stats(group=group)
    return {"ok": True, "group": group, "areas": rows[:40]}


def gis_create_map(title=None, keyword=None, classification=None, category=None, area=None,
                   center_property=None, radius_m=None, extra_points=None, filename=None):
    """条件に合う物件の地図HTMLを作る。center_property＋radius_m で半径円も描ける。

    extra_points: [{"lat","lon","name","note"}]（取引価格など別レイヤ。既存の
    reinfolib ツールで取った数値をここへ渡す。市場データの取得はこのToolでは行わない）
    """
    circle = None
    center = None
    if center_property:
        p = gis.find_property(center_property)
        if not p:
            return {"ok": False, "error": f"物件が見つかりません: {center_property}"}
        if p.get("lat") is None:
            return {"ok": False, "error": f"座標が未取得です: {p['name']}"}
        center = (p["lat"], p["lon"])
        if radius_m:
            circle = {"lat": p["lat"], "lon": p["lon"], "radius_m": float(radius_m),
                      "label": f"{p['name']} から {gis.fmt_distance(float(radius_m))}"}

    if center and radius_m:
        rows = gis.nearby(center[0], center[1], radius_m=float(radius_m), limit=500,
                          **{k: v for k, v in (("classification", classification),
                                               ("category", category)) if v})
        p0 = gis.find_property(center_property)
        if p0 and not any(r["property_id"] == p0["property_id"] for r in rows):
            rows = [p0] + rows
    else:
        rows = gis.list_properties(keyword=keyword, classification=classification,
                                   category=category, area=area, limit=500)
    if not title:
        bits = [b for b in (classification, category, area, keyword) if b]
        title = "管理物件マップ" + ("（" + " / ".join(bits) + "）" if bits else "")
        if center_property and radius_m:
            title = f"{center_property} から {gis.fmt_distance(float(radius_m))} 圏内"
    res = gis.build_map(rows, title=title, center=center, circle=circle,
                        extra_points=extra_points, filename=filename)
    return _map_result(res, title)


def gis_export_geojson(keyword=None, classification=None, category=None, area=None,
                       filename=None):
    """条件に合う物件を GeoJSON で書き出す（他のGISツールへ渡す標準形式）。"""
    import json
    rows = gis.list_properties(keyword=keyword, classification=classification,
                               category=category, area=area, limit=2000)
    if not rows:
        return {"ok": False, "error": "該当する物件がありません（座標未取得の可能性）"}
    os.makedirs(gis.MAPS_DIR, exist_ok=True)
    name = filename or "properties.geojson"
    if not name.endswith(".geojson"):
        name += ".geojson"
    path = os.path.join(gis.MAPS_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(gis.to_geojson(rows), f, ensure_ascii=False, indent=1)
    return {"ok": True, "count": len(rows), "path": path, "filename": name}


def gis_market_map(prefecture="大阪府", city_code=None, city_name=None, year=None,
                   area=None, filename=None):
    """管理物件に**国交省の取引価格**を重ねた地図を作る。

    市場データの取得は**既存の reinfolib_transactions をそのまま呼ぶ**（API連携を二重に作らない）。
    町名ごとの中央値を点として重ね、管理物件と同じ地図で見比べられるようにする。
    city_name は町名をジオコードするための市区名（例「大阪市都島区」）。省略時は area を使う。
    """
    from services.agent_tools import reinfolib_tools

    mk = reinfolib_tools.reinfolib_transactions(prefecture=prefecture, city_code=city_code,
                                                year=year)
    if not mk.get("ok"):
        return mk
    base = (city_name or area or "").strip()
    if not base:
        return {"ok": False, "error": "町名をジオコードするための市区名（city_name）が必要です"}
    pts = []
    seen = set()
    dropped = 0
    for d in mk.get("by_district", [])[:25]:
        g = gis.geocode(f"{base}{d['district']}")
        if not g.get("ok"):
            dropped += 1
            continue          # 1件失敗しても全体は止めない
        # 国土地理院は町名が特定できないと**黙って区の中心**を返す。そのまま置くと
        # 全部の点が1箇所に重なるので捨てる（2026-08-17 に実地で発生した不具合）
        if g.get("coarse"):
            dropped += 1
            continue
        key = (round(g["lat"], 5), round(g["lon"], 5))
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        man = d["price_median_yen"] // 10000
        pts.append({"lat": g["lat"], "lon": g["lon"],
                    "name": f"{d['district']}（取引{d['count']}件）",
                    "note": f"取引価格の中央値 {d['price_median_yen']:,}円",
                    "label": f"{man:,}万"})
    title = f"{base} 管理物件 × {mk.get('year')}年 取引価格（国交省）"
    res = gis.build_map(gis.list_properties(area=area or base, limit=500), title=title,
                        extra_points=pts, filename=filename or "market-overlay")
    out = _map_result(res, title)
    out.update({"market_count": mk.get("count"), "market_median_yen": mk.get("price_median_yen"),
                "districts_plotted": len(pts), "districts_dropped": dropped,
                "source": mk.get("source")})
    return out


def gis_status():
    """物件マスタと座標の整備状況（何件登録され、何件に座標があるか）。"""
    from db.connection import query
    total = query("SELECT COUNT(*) c FROM properties WHERE active=1")[0]["c"]
    geo = query("SELECT COUNT(*) c FROM properties WHERE active=1 AND lat IS NOT NULL")[0]["c"]
    miss = [dict(r) for r in query(
        "SELECT name, address, geo_status FROM properties WHERE active=1 AND lat IS NULL LIMIT 20")]
    by_cls = [dict(r) for r in query(
        "SELECT classification, COUNT(*) c FROM properties WHERE active=1 GROUP BY classification")]
    return {"ok": True, "total": total, "geocoded": geo, "by_classification": by_cls,
            "missing_coordinates": miss,
            "note": "台帳の取込・座標取得は ターミナルで python3 ingest_properties.py"}
