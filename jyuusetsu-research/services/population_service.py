"""人口・世帯数を e-Stat（政府統計）API で取得する。

**2026-08-20 に実装した**（それまでは地域名を抽出するだけで API を呼んでいなかった）。

取得の流れ:

    住所 → 緯度経度（address_service）→ **市区町村コード**（国土地理院 逆ジオコーディング）
         → e-Stat「社会・人口統計体系 市区町村データ 基礎データ Ａ人口・世帯」

実測で確かめたこと（2026-08-20）:

- **統計表ID `0000020101`** = 市区町村データ 基礎データ（オリジナル）Ａ　人口・世帯
- 項目コード（`cdCat01`）… **`A1101` 総人口** / **`A7101` 世帯数**
- 地域コード（`cdArea`）は **5桁の全国地方公共団体コード**。国土地理院の
  `LonLatToAddress` が返す `muniCd` がそのまま使える（例 大阪市中央区 = 27128）
- 例: 27128 → 総人口 103,726人 / 世帯数 67,139世帯（2020年度＝国勢調査年）
- 年次は5年おきの国勢調査値が中心なので、**最新の値がある年**を自動で選ぶ
- `metaGetFlg=Y` にすると、**指定した地域コードの正式名称だけ**がメタに入って返る
  （例 `27128` → 「大阪府 大阪市 中央区」）。応答は 6.9KB 程度で軽い。
  住所文字列から名前を作ると「大阪府大阪市」のように**区が落ちて実データと食い違う**ので、
  表示にはこの正式名称を使う

appId は無料登録。次の順に探す:
`ESTAT_APP_ID`（環境変数）→ `st.secrets["estat_app_id"]` → **直下 `.env.estat`**。
無ければ空欄で継続する（アプリは止めない）。
"""

import os
import pathlib
import re
from typing import Dict, Optional, Tuple

import requests

ESTAT_URL = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"
GSI_REVERSE_URL = "https://mreversegeocoder.gsi.go.jp/reverse-geocoder/LonLatToAddress"
ENV_PATH = pathlib.Path(__file__).resolve().parents[2] / ".env.estat"
TIMEOUT = 20

STATS_DATA_ID = "0000020101"  # 市区町村データ 基礎データ Ａ　人口・世帯
CAT_POPULATION = "A1101"      # 総人口
CAT_HOUSEHOLDS = "A7101"      # 世帯数


def get_app_id() -> str:
    """appId を取得する（環境変数 → st.secrets → 直下 .env.estat）。"""
    app_id = os.environ.get("ESTAT_APP_ID", "").strip()
    if app_id:
        return app_id
    try:
        import streamlit as st

        if "estat_app_id" in st.secrets:
            return str(st.secrets["estat_app_id"]).strip()
    except Exception:
        pass
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("ESTAT_APP_ID=") :
                return line.split("=", 1)[1].strip()
    return ""


def _extract_municipality(address: str) -> str:
    """住所文字列から「市区町村」までを簡易抽出する（表示・ログ用）。"""
    if not address:
        return ""
    m = re.search(r"(.+?[都道府県])?(.+?[市区町村])", address)
    if m:
        return (m.group(1) or "") + m.group(2)
    return ""


def muni_code(lat: float, lon: float) -> str:
    """緯度経度 → 全国地方公共団体コード（5桁）。取れなければ空文字。

    国土地理院の逆ジオコーディング。`realestate-valuation/services/geo_service.py` と同じ手。
    先頭ゼロが落ちて返ることがあるのでゼロ埋めする。
    """
    if lat is None or lon is None:
        return ""
    try:
        resp = requests.get(GSI_REVERSE_URL, params={"lat": lat, "lon": lon}, timeout=TIMEOUT)
        resp.raise_for_status()
        code = str(resp.json().get("results", {}).get("muniCd", "")).strip()
    except Exception:
        return ""
    return code.zfill(5) if code else ""


def _latest_values(values) -> Dict[str, Tuple[str, str]]:
    """e-Stat の VALUE 配列から、項目ごとに**最新年の値**を選ぶ。

    戻り値: {cat01コード: (値, 年)}。秘匿や欠測（数字でないもの）は捨てる。
    """
    if isinstance(values, dict):
        values = [values]
    latest: Dict[str, Tuple[str, str]] = {}
    latest_time: Dict[str, str] = {}
    for v in values or []:
        cat = v.get("@cat01", "")
        time_code = v.get("@time", "")
        raw = str(v.get("$", "")).strip().replace(",", "")
        if not raw.isdigit():
            continue  # "-"（該当なし）や "***"（秘匿）
        if cat not in latest_time or time_code > latest_time[cat]:
            latest_time[cat] = time_code
            latest[cat] = (raw, time_code[:4])
    return latest


def _area_name(stats: Dict) -> str:
    """メタ情報から地域の正式名称を取り出す（例「大阪府 大阪市 中央区」→ 空白を詰める）。"""
    try:
        for obj in stats["CLASS_INF"]["CLASS_OBJ"]:
            if obj.get("@id") != "area":
                continue
            cls = obj.get("CLASS")
            if isinstance(cls, dict):
                cls = [cls]
            if cls:
                return str(cls[0].get("@name", "")).replace(" ", "").replace("\u3000", "")
    except Exception:
        return ""
    return ""


def get_population(address: str, coords: Optional[Tuple[float, float]] = None) -> Dict[str, str]:
    """人口・世帯数を取得する。appId 未設定・取得失敗時は空文字で継続。

    `coords` を渡すと逆ジオコーディングだけで済む（app.py は調査済みの座標を渡す）。
    """
    result = {"人口": "", "世帯数": ""}
    app_id = get_app_id()
    if not app_id:
        return result

    if not coords:
        from services import address_service  # 循環参照を避けるため関数内で読む

        coords = address_service.geocode(address)
    if not coords:
        return result

    code = muni_code(coords[0], coords[1])
    if not code:
        return result

    try:
        resp = requests.get(
            ESTAT_URL,
            params={
                "appId": app_id,
                "statsDataId": STATS_DATA_ID,
                "cdArea": code,
                "cdCat01": "{},{}".format(CAT_POPULATION, CAT_HOUSEHOLDS),
                "metaGetFlg": "Y",  # 地域コードの正式名称を取るため
                "cntGetFlg": "N",
                "limit": 200,
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        body = resp.json()["GET_STATS_DATA"]
        if str(body["RESULT"]["STATUS"]) != "0":
            return result
        stats = body["STATISTICAL_DATA"]
        values = stats["DATA_INF"]["VALUE"]
        area_name = _area_name(stats)
    except Exception:
        return result

    latest = _latest_values(values)
    label = area_name or _extract_municipality(address) or "当該市区町村"
    if CAT_POPULATION in latest:
        value, year = latest[CAT_POPULATION]
        result["人口"] = "{:,}人（{}年・{}）".format(int(value), year, label)
    if CAT_HOUSEHOLDS in latest:
        value, year = latest[CAT_HOUSEHOLDS]
        result["世帯数"] = "{:,}世帯（{}年）".format(int(value), year)
    return result
