#!/usr/bin/env python3
"""e-Stat（政府統計の総合窓口）API の共通クライアント（2026-08-23 作成）。

`japanpost_api.py` / `egov_law_api.py` と同じく **直下に1本だけ置く**。
アプリ側からは次のどちらかで読む:

    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import estat_api

appId は無料登録（2026-08-20 取得済み）。**値はコードに書かない**。次の順で探す:
`ESTAT_APP_ID`（環境変数）→ `st.secrets["estat_app_id"]` → **直下 `.env.estat`**。

**依存は標準ライブラリだけ**（urllib）。`chatwork-ai-manager` は
「HTTP は urllib、requests は入れない」方針で、launchd から `/usr/bin/python3` で
動いているため、requests を前提にすると本番で ImportError になる。

## 何が引けるか（社会・人口統計体系「市区町村データ 基礎データ」）

市区町村コード（5桁）を指定すると、その市区町村の指標を年次つきで取れる。
不動産で効くのは A（人口・世帯）と H（居住）の2表:

| 表ID | 分野 | 使いどころ |
|---|---|---|
| `0000020101` | Ａ 人口・世帯 | 人口・世帯数・年齢構成・転入転出・昼夜間人口・将来推計 |
| `0000020108` | Ｈ 居住 | 総住宅数・空き家数・借家数・民営借家・共同住宅・着工新設貸家 |

（B自然環境〜K安全も `TABLES` に入れてあるので同じ関数で引ける）

## 実測で確かめたこと（2026-08-20 / 2026-08-23）

- 地域コード（`cdArea`）は **5桁の全国地方公共団体コード**。国土地理院の逆ジオコーディング
  `LonLatToAddress` が返す `muniCd` がそのまま使える（例 大阪市都島区 = 27102）
- `cdArea` も `cdCat01` も **カンマ区切りで複数指定できる**（＝区どうしの比較が1回で済む）
- 値は年次が混ざって返るので、**項目ごとに最新年を選ぶ**。国勢調査系は5年おき、
  住宅・土地統計調査は5年おき（2023年が最新）、着工統計は毎年
- 欠測は `"-"`、秘匿は `"***"` で返る（数値に変換できないものは捨てる）
- `metaGetFlg=Y` を付けると **指定した地域・項目の正式名称と単位**だけがメタに入る
  （住所文字列から名前を作ると「大阪市」で区が落ちて実データと食い違う）
- 表のメタ情報（項目一覧）は変わらないので **`.estat-cache/` に30日キャッシュ**する
  （Ａ表で 134項目・Ｈ表で 232項目ある。毎回取りに行くと無駄）
"""

from __future__ import annotations

import json
import os
import pathlib
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterable, List, Optional, Tuple

BASE = "https://api.e-stat.go.jp/rest/3.0/app/json"
GSI_REVERSE_URL = "https://mreversegeocoder.gsi.go.jp/reverse-geocoder/LonLatToAddress"
ROOT = pathlib.Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env.estat"
CACHE_DIR = ROOT / ".estat-cache"
CACHE_DAYS = 30
TIMEOUT = 30

# 社会・人口統計体系「市区町村データ 基礎データ（オリジナル）」
TABLES = {
    "population": "0000020101",  # Ａ 人口・世帯
    "nature": "0000020102",      # Ｂ 自然環境
    "economy": "0000020103",     # Ｃ 経済基盤
    "admin": "0000020104",       # Ｄ 行政基盤
    "education": "0000020105",   # Ｅ 教育
    "labor": "0000020106",       # Ｆ 労働
    "culture": "0000020107",     # Ｇ 文化・スポーツ
    "housing": "0000020108",     # Ｈ 居住
    "health": "0000020109",      # Ｉ 健康・医療
    "welfare": "0000020110",     # Ｊ 福祉・社会保障
    "safety": "0000020111",      # Ｋ 安全
}
TABLE_LABELS = {
    "population": "Ａ 人口・世帯",
    "nature": "Ｂ 自然環境",
    "economy": "Ｃ 経済基盤",
    "admin": "Ｄ 行政基盤",
    "education": "Ｅ 教育",
    "labor": "Ｆ 労働",
    "culture": "Ｇ 文化・スポーツ",
    "housing": "Ｈ 居住",
    "health": "Ｉ 健康・医療",
    "welfare": "Ｊ 福祉・社会保障",
    "safety": "Ｋ 安全",
}


class EstatError(RuntimeError):
    """appId 未設定・通信失敗・API がエラーを返したとき。"""


# ---------------------------------------------------------------- 資格情報

def get_app_id() -> str:
    """appId を取得する（環境変数 → st.secrets → 直下 .env.estat）。無ければ空文字。"""
    app_id = os.environ.get("ESTAT_APP_ID", "").strip()
    if app_id:
        return app_id
    try:
        import streamlit as st  # Streamlit アプリから読まれたときだけ効く

        if "estat_app_id" in st.secrets:
            return str(st.secrets["estat_app_id"]).strip()
    except Exception:
        pass
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("ESTAT_APP_ID="):
                return line.split("=", 1)[1].strip()
    return ""


def _require_app_id() -> str:
    app_id = get_app_id()
    if not app_id:
        raise EstatError("ESTAT_APP_ID が未設定です（直下 .env.estat / 環境変数 / secrets.toml）")
    return app_id


# ---------------------------------------------------------------- 通信

def _get_json(url: str) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "estat-api-client/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise EstatError("e-Stat への問い合わせに失敗しました: {}".format(e))


def _call(endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    params = dict(params)
    params["appId"] = _require_app_id()
    url = "{}/{}?{}".format(BASE, endpoint, urllib.parse.urlencode(params))
    return _get_json(url)


def _resolve_table(table: str) -> str:
    """`"housing"` のような別名でも、`"0000020108"` のような表IDでも受ける。"""
    table = str(table or "").strip()
    if table in TABLES:
        return TABLES[table]
    if table.isdigit():
        return table
    raise EstatError("知らない統計表です: {}（{} のいずれか、または統計表IDを指定）".format(
        table, "/".join(TABLES)))


# ---------------------------------------------------------------- 地域コード

def muni_code(lat: float, lon: float) -> str:
    """緯度経度 → 全国地方公共団体コード（5桁）。取れなければ空文字。

    国土地理院の逆ジオコーディング（キー不要）。先頭ゼロが落ちて返るのでゼロ埋めする。
    """
    if lat is None or lon is None:
        return ""
    url = "{}?{}".format(GSI_REVERSE_URL, urllib.parse.urlencode({"lat": lat, "lon": lon}))
    try:
        data = _get_json(url)
        code = str(data.get("results", {}).get("muniCd", "")).strip()
    except Exception:
        return ""
    return code.zfill(5) if code else ""


def normalize_area(code) -> str:
    """市区町村コードを5桁に揃える（6桁のチェックデジット付きが渡されたら落とす）。"""
    code = str(code or "").strip()
    if not code.isdigit():
        return ""
    if len(code) == 6:  # 住民基本台帳などで使う検査数字つき
        code = code[:5]
    return code.zfill(5)


# ---------------------------------------------------------------- メタ情報

def _cache_path(name: str) -> pathlib.Path:
    return CACHE_DIR / "{}.json".format(name)


def _cache_read(name: str) -> Optional[Dict[str, Any]]:
    path = _cache_path(name)
    if not path.exists():
        return None
    if time.time() - path.stat().st_mtime > CACHE_DAYS * 86400:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _cache_write(name: str, data: Dict[str, Any]) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass  # 書けなくても機能は落とさない


def indicators(table: str = "population") -> List[Dict[str, str]]:
    """統計表に入っている項目（cat01）の一覧。[{"code","name","unit"}]。

    表のメタは滅多に変わらないので30日キャッシュする。
    """
    stats_data_id = _resolve_table(table)
    cached = _cache_read("meta-{}".format(stats_data_id))
    if cached is not None:
        return cached["items"]

    body = _call("getMetaInfo", {"statsDataId": stats_data_id})["GET_META_INFO"]
    if str(body["RESULT"]["STATUS"]) != "0":
        raise EstatError(body["RESULT"].get("ERROR_MSG", "メタ情報の取得に失敗しました"))

    items: List[Dict[str, str]] = []
    for obj in body["METADATA_INF"]["CLASS_INF"]["CLASS_OBJ"]:
        if obj.get("@id") != "cat01":
            continue
        classes = obj.get("CLASS")
        if isinstance(classes, dict):
            classes = [classes]
        for cls in classes or []:
            name = str(cls.get("@name", ""))
            # 「A1101_総人口」のように コード_名前 で返るので名前だけにする
            if "_" in name:
                name = name.split("_", 1)[1]
            items.append({
                "code": str(cls.get("@code", "")),
                "name": name,
                "unit": str(cls.get("@unit", "") or ""),
            })
    _cache_write("meta-{}".format(stats_data_id), {"items": items})
    return items


def search_indicators(keyword: str, table=None, limit: int = 40) -> List[Dict[str, str]]:
    """項目名にキーワードを含む指標を探す（table 省略で人口・世帯＋居住の2表）。"""
    keyword = str(keyword or "").strip()
    tables = [table] if table else ["population", "housing"]
    out: List[Dict[str, str]] = []
    for t in tables:
        for item in indicators(t):
            if not keyword or keyword in item["name"]:
                row = dict(item)
                row["table"] = t
                out.append(row)
                if len(out) >= limit:
                    return out
    return out


def indicator_name_map(table: str) -> Dict[str, Dict[str, str]]:
    """{コード: {"name","unit"}}。値の整形に使う。"""
    return {i["code"]: {"name": i["name"], "unit": i["unit"]} for i in indicators(table)}


# ---------------------------------------------------------------- 統計値

def _to_number(raw: str):
    """e-Stat の値を数値にする。欠測 "-" ・秘匿 "***" は None。"""
    raw = str(raw).strip().replace(",", "")
    if not raw or raw in ("-", "***", "X", "…"):
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return int(value) if value.is_integer() else value


def _area_names(stats: Dict[str, Any]) -> Dict[str, str]:
    """メタから {地域コード: 正式名称}（例 27102 → 大阪府大阪市都島区）。"""
    names: Dict[str, str] = {}
    try:
        for obj in stats["CLASS_INF"]["CLASS_OBJ"]:
            if obj.get("@id") != "area":
                continue
            classes = obj.get("CLASS")
            if isinstance(classes, dict):
                classes = [classes]
            for cls in classes or []:
                names[str(cls.get("@code", ""))] = str(cls.get("@name", "")).replace(
                    " ", "").replace("　", "")
    except Exception:
        return names
    return names


def get_values(table: str, areas, cats, latest_only: bool = True) -> Dict[str, Any]:
    """市区町村の指標値を取る。

    table  : "population" / "housing" などの別名、または統計表ID
    areas  : 市区町村コード（1件でもリストでも可）
    cats   : 項目コード（1件でもリストでも可。例 "A1101" / ["H1100","H110202"]）
    戻り値 : {"table":…, "areas": {コード: {"name":…, "values": {項目: {...}}}}}
             各値は {"code","name","unit","value","year"}。
             `latest_only=False` なら {"history": {年: 値}} も付ける。
    """
    stats_data_id = _resolve_table(table)
    if isinstance(areas, (str, int)):
        areas = [areas]
    if isinstance(cats, str):
        cats = [cats]
    area_codes = [normalize_area(a) for a in areas if normalize_area(a)]
    cat_codes = [str(c).strip() for c in cats if str(c).strip()]
    if not area_codes:
        raise EstatError("市区町村コード（5桁）を1件以上渡してください")
    if not cat_codes:
        raise EstatError("項目コードを1件以上渡してください")

    body = _call("getStatsData", {
        "statsDataId": stats_data_id,
        "cdArea": ",".join(area_codes),
        "cdCat01": ",".join(cat_codes),
        "metaGetFlg": "Y",   # 地域・項目の正式名称と単位を取るため
        "cntGetFlg": "N",
        "limit": 10000,
    })["GET_STATS_DATA"]
    if str(body["RESULT"]["STATUS"]) != "0":
        raise EstatError(body["RESULT"].get("ERROR_MSG", "統計データの取得に失敗しました"))

    stats = body["STATISTICAL_DATA"]
    values = stats.get("DATA_INF", {}).get("VALUE", [])
    if isinstance(values, dict):
        values = [values]
    names = indicator_name_map(table)
    area_names = _area_names(stats)

    result: Dict[str, Any] = {
        "table": table,
        "table_id": stats_data_id,
        "table_label": TABLE_LABELS.get(table, table),
        "areas": {},
    }
    for area in area_codes:
        result["areas"][area] = {"name": area_names.get(area, ""), "values": {}}

    for v in values:
        area = str(v.get("@area", ""))
        cat = str(v.get("@cat01", ""))
        year = str(v.get("@time", ""))[:4]
        number = _to_number(v.get("$", ""))
        if number is None or area not in result["areas"]:
            continue
        slot = result["areas"][area]["values"].setdefault(cat, {
            "code": cat,
            "name": names.get(cat, {}).get("name", cat),
            "unit": names.get(cat, {}).get("unit", ""),
            "value": None,
            "year": "",
            "history": {},
        })
        slot["history"][year] = number
        if not slot["year"] or year > slot["year"]:
            slot["value"] = number
            slot["year"] = year

    for area in result["areas"].values():
        for slot in area["values"].values():
            if latest_only:
                slot.pop("history", None)
            else:
                slot["history"] = dict(sorted(slot["history"].items()))
    return result


def city_values(area_code, table: str, cats) -> Dict[str, Any]:
    """1市区町村ぶんだけ欲しいときの薄い入口。

    戻り値: {"code","name"（正式名称）,"values": {項目コード: {...}}}。
    地域が無い・値が無いときも同じ形（values が空）で返す。
    """
    area_code = normalize_area(area_code)
    data = get_values(table, [area_code], cats)
    area = data["areas"].get(area_code, {})
    return {"code": area_code, "name": area.get("name", ""), "values": area.get("values", {})}


# ---------------------------------------------------------------- 動作確認

if __name__ == "__main__":  # python3 estat_api.py [市区町村コード]
    import sys

    code = sys.argv[1] if len(sys.argv) > 1 else "27102"  # 既定は大阪市都島区
    print("appId:", "設定あり" if get_app_id() else "未設定")
    data = get_values("population", [code], ["A1101", "A7101"])
    for area, info in data["areas"].items():
        print(area, info["name"])
        for slot in info["values"].values():
            print("  {} {} {}（{}年）".format(slot["name"], slot["value"], slot["unit"], slot["year"]))
