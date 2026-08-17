"""国交省「不動産情報ライブラリ」API ツール（公的な不動産データ）。

- reinfolib_transactions: 不動産取引価格情報（XIT001）を都道府県/市区町村・期間で集計
- reinfolib_cities:        市区町村コード一覧（XIT002）を都道府県から取得
キーは secrets.toml の reinfolib_api_key（他アプリと共通・既存キー流用）。urllib のみ。
地価・取引相場など「客観的な数値根拠」を示すときに使う（社内資料では出せない公的データ）。
"""
import json
import statistics
import urllib.parse
import urllib.request

from services import config

_BASE = "https://www.reinfolib.mlit.go.jp/ex-api/external"
_TIMEOUT = 30

# 都道府県名 → コード（"大阪府"→"27" 等。県/府/都/道 の有無を吸収）
_PREF = {
    "北海道": "01", "青森": "02", "岩手": "03", "宮城": "04", "秋田": "05", "山形": "06",
    "福島": "07", "茨城": "08", "栃木": "09", "群馬": "10", "埼玉": "11", "千葉": "12",
    "東京": "13", "神奈川": "14", "新潟": "15", "富山": "16", "石川": "17", "福井": "18",
    "山梨": "19", "長野": "20", "岐阜": "21", "静岡": "22", "愛知": "23", "三重": "24",
    "滋賀": "25", "京都": "26", "大阪": "27", "兵庫": "28", "奈良": "29", "和歌山": "30",
    "鳥取": "31", "島根": "32", "岡山": "33", "広島": "34", "山口": "35", "徳島": "36",
    "香川": "37", "愛媛": "38", "高知": "39", "福岡": "40", "佐賀": "41", "長崎": "42",
    "熊本": "43", "大分": "44", "宮崎": "45", "鹿児島": "46", "沖縄": "47",
}


def _pref_code(prefecture: str) -> str:
    if not prefecture:
        return ""
    p = str(prefecture).strip()
    if p.isdigit():
        return p.zfill(2)
    for name, code in _PREF.items():
        if p.startswith(name):
            return code
    return ""


def _get(path: str, params: dict):
    import gzip
    import io
    api_key = config.get("reinfolib_api_key")
    if not api_key:
        raise RuntimeError("reinfolib_api_key が未設定です")
    url = f"{_BASE}/{path}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Ocp-Apim-Subscription-Key": str(api_key),
        "Accept-Encoding": "gzip",
    })
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        raw = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
            raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
        return json.loads(raw.decode("utf-8"))


def reinfolib_cities(prefecture):
    """都道府県の市区町村コード一覧。prefecture は名前('大阪府')かコード('27')。"""
    code = _pref_code(prefecture)
    if not code:
        return {"ok": False, "error": f"都道府県を特定できません: {prefecture}"}
    try:
        data = _get("XIT002", {"area": code})
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    cities = [{"city_code": r.get("id"), "name": r.get("name")} for r in data.get("data", [])]
    return {"ok": True, "prefecture_code": code, "count": len(cities), "cities": cities}


def reinfolib_transactions(prefecture, city_code=None, year=None, quarter=None, limit=200):
    """不動産取引価格情報を取得・集計。

    prefecture: 名前 or コード。city_code: 5桁市区町村コード（reinfolib_citiesで取得）。
    year: 西暦（省略時は直近年）。quarter: 1-4（省略時は通年ぶんを合算）。
    戻り: 件数・中央値/平均・種別内訳・サンプル数件。
    """
    code = _pref_code(prefecture)
    if not code:
        return {"ok": False, "error": f"都道府県を特定できません: {prefecture}"}
    import datetime
    if not year:
        year = datetime.date.today().year - 1
    quarters = [quarter] if quarter else [1, 2, 3, 4]

    rows = []
    for q in quarters:
        params = {"year": int(year), "quarter": int(q), "area": code}
        if city_code:
            params["city"] = str(city_code)
        try:
            data = _get("XIT001", params)
        except Exception:
            continue
        rows.extend(data.get("data", []))
        if len(rows) >= limit:
            break

    if not rows:
        return {"ok": True, "count": 0,
                "note": "該当する取引データが見つかりませんでした（年・地域を変えて再試行）",
                "params": {"prefecture_code": code, "city_code": city_code, "year": year}}

    prices, by_type = [], {}
    districts = {}          # 町名別（地図に重ねるため。2026-08-17 追加）
    samples = []
    for r in rows[:limit]:
        try:
            p = int(r.get("TradePrice") or 0)
        except (TypeError, ValueError):
            p = 0
        if p > 0:
            prices.append(p)
        t = r.get("Type") or "不明"
        by_type[t] = by_type.get(t, 0) + 1
        d = r.get("DistrictName")
        if d and p > 0:
            districts.setdefault(d, {"district": d, "municipality": r.get("Municipality"),
                                     "count": 0, "_prices": []})
            districts[d]["count"] += 1
            districts[d]["_prices"].append(p)
        if len(samples) < 8:
            samples.append({
                "type": t, "region": r.get("Region"), "municipality": r.get("Municipality"),
                "district": r.get("DistrictName"), "price_yen": r.get("TradePrice"),
                "area_m2": r.get("Area"), "layout": r.get("FloorPlan"),
                "year_built": r.get("BuildingYear"), "period": r.get("Period"),
            })
    by_district = []
    for d in districts.values():
        ps = d.pop("_prices")
        d["price_median_yen"] = int(statistics.median(ps))
        by_district.append(d)
    by_district.sort(key=lambda x: -x["count"])

    summary = {
        "ok": True, "count": len(rows),
        "prefecture_code": code, "city_code": city_code, "year": year,
        "price_median_yen": int(statistics.median(prices)) if prices else None,
        "price_mean_yen": int(statistics.mean(prices)) if prices else None,
        "by_type": by_type, "samples": samples,
        # 町名別（GISで地図に重ねる用。件数の多い順）
        "by_district": by_district[:40],
        "source": "国土交通省 不動産情報ライブラリ 取引価格情報(XIT001)",
    }
    return summary
