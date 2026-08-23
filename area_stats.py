#!/usr/bin/env python3
"""商圏データ（人口・世帯・住宅）を政府統計 e-Stat から取る — 直下の共有モジュール（2026-08-23 作成）。

査定は取引事例（国交省 不動産情報ライブラリ）だけでは「その値段で買う人がいるのか」に
答えられない。**世帯数・単身世帯の多寡・転入超過・空き家率**は、賃貸需要と出口の
見通しを裏づける公的な数字になる。オーナー・投資家に渡す査定書の根拠として使う。

使うのは `estat_api.py`（同じく直下）。**査定（8509）と事業計画（8533）が同じこれを読む。**
アプリ側で計算を作り直さないこと（片方だけ直すと、同じ物件で違う空き家率が出る）。
appId は直下 `.env.estat`（gitignore）。**未設定なら空で返し、査定は止めない**
（相場取得と同じ考え方）。

数字の粒度は**市区町村**。町丁目・駅徒歩圏の統計は無いので、査定書に載せるときは
「市区町村単位の公的統計」と分かる書き方にすること。調査年も必ず併記する。
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any, Dict

_ROOT = pathlib.Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# 査定書に効くものだけ。多く出しても読まれない
_POP = {
    "A1101": "総人口",
    "A7101": "世帯数",
    "A710101": "一般世帯数",
    "A710201": "一般世帯人員",
    "A1303": "65歳以上人口",
    "A5103": "転入者数",
    "A5104": "転出者数",
    "A191005": "2040年推計人口",
}
_HOUSE = {
    "H1100": "総住宅数",
    "H1101": "居住世帯あり住宅数",
    "H110202": "空き家数",
    "H1320": "借家数",
    "H1322": "民営借家数",
    "H1403": "共同住宅数",
    "H1802": "着工新設貸家数",
}


def is_configured() -> bool:
    try:
        import estat_api
        return bool(estat_api.get_app_id())
    except Exception:
        return False


def _pct(numerator, denominator):
    if not numerator or not denominator:
        return None
    return round(numerator / denominator * 100, 1)


def fetch(muni_code: str) -> Dict[str, Any]:
    """市区町村コード（5桁）→ 査定書に載せられる形の商圏データ。

    戻り値: {"ok", "city", "rows"[{項目,値,年}], "highlights"{…}, "summary"(貼り付け用), "error"}
    """
    try:
        import estat_api
    except Exception as e:
        return {"ok": False, "error": "estat_api を読み込めません: {}".format(e)}

    code = estat_api.normalize_area(muni_code)
    if not code:
        return {"ok": False, "error": "市区町村コードが取れませんでした（住所の精度をご確認ください）"}
    if not estat_api.get_app_id():
        return {"ok": False, "error": "ESTAT_APP_ID が未設定です（直下 .env.estat）"}

    try:
        pop = estat_api.city_values(code, "population", list(_POP))
        house = estat_api.city_values(code, "housing", list(_HOUSE))
    except Exception as e:
        return {"ok": False, "error": "{}: {}".format(type(e).__name__, e)}

    city = pop.get("name") or house.get("name") or code
    values = {}
    rows = []
    for label_map, area in ((_POP, pop), (_HOUSE, house)):
        for code_, label in label_map.items():
            slot = area["values"].get(code_)
            if not slot:
                continue
            values[label] = slot["value"]
            rows.append({"項目": label, "値": slot["value"],
                         "単位": slot["unit"], "調査年": slot["year"]})

    highlights = {
        "高齢化率": _pct(values.get("65歳以上人口"), values.get("総人口")),
        "空き家率": _pct(values.get("空き家数"), values.get("総住宅数")),
        "借家率": _pct(values.get("借家数"), values.get("居住世帯あり住宅数")),
        "共同住宅率": _pct(values.get("共同住宅数"), values.get("総住宅数")),
        "社会増減": (values.get("転入者数", 0) - values.get("転出者数", 0)
                     if values.get("転入者数") and values.get("転出者数") else None),
        "1世帯あたり人員": (round(values["一般世帯人員"] / values["一般世帯数"], 2)
                            if values.get("一般世帯人員") and values.get("一般世帯数") else None),
        "2040年増減率": (round((values["2040年推計人口"] - values["総人口"])
                              / values["総人口"] * 100, 1)
                         if values.get("2040年推計人口") and values.get("総人口") else None),
    }

    years = {r["項目"]: r["調査年"] for r in rows}
    lines = ["【商圏データ】{}（出典: 政府統計 e-Stat 社会・人口統計体系）".format(city)]
    if values.get("総人口"):
        lines.append("人口 {:,}人・世帯数 {:,}世帯（{}年 国勢調査）".format(
            values["総人口"], values.get("世帯数", 0), years.get("総人口", "")))
    if highlights["1世帯あたり人員"]:
        lines.append("1世帯あたり {}人／高齢化率 {}%".format(
            highlights["1世帯あたり人員"], highlights["高齢化率"]))
    if highlights["社会増減"] is not None:
        lines.append("転入 {:,}人 − 転出 {:,}人 ＝ {:+,}人（{}年 住民基本台帳）".format(
            values["転入者数"], values["転出者数"], highlights["社会増減"],
            years.get("転入者数", "")))
    if highlights["空き家率"]:
        lines.append("総住宅 {:,}戸・空き家率 {}%・借家率 {}%・共同住宅 {}%（{}年 住宅土地統計調査）".format(
            values.get("総住宅数", 0), highlights["空き家率"], highlights["借家率"],
            highlights["共同住宅率"], years.get("総住宅数", "")))
    if values.get("着工新設貸家数"):
        lines.append("着工新設貸家 {:,}戸（{}年 建築着工統計＝新規供給の勢い）".format(
            values["着工新設貸家数"], years.get("着工新設貸家数", "")))
    if highlights["2040年増減率"] is not None:
        lines.append("2040年の推計人口は {}年比 {:+}%".format(
            years.get("総人口", ""), highlights["2040年増減率"]))
    lines.append("※市区町村単位の公的統計。統計上の空き家には賃貸募集中の空室も含む。")

    return {"ok": True, "city": city, "muni_code": code, "rows": rows,
            "values": values, "highlights": highlights,
            "summary": "\n".join(lines), "error": ""}


# ── 住所から直接引く（市区町村コードを持っていないアプリ用）───────────────
_GSI_SEARCH = "https://msearch.gsi.go.jp/address-search/AddressSearch?q="


def geocode(address: str):
    """住所 → (緯度, 経度)。国土地理院（キー不要）。取れなければ None。

    査定アプリ（8509）は自前の geo_service を持っているのでそちらを使う。
    ここは市区町村コードを持たないアプリ（事業計画 8533 など）のための入口。
    """
    import json
    import urllib.parse
    import urllib.request

    address = str(address or "").strip()
    if not address:
        return None
    url = _GSI_SEARCH + urllib.parse.quote(address)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "area-stats/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
    if not data:
        return None
    lon, lat = data[0].get("geometry", {}).get("coordinates", [None, None])
    if lat is None or lon is None:
        return None
    return float(lat), float(lon)


def fetch_by_address(address: str) -> Dict[str, Any]:
    """住所 → 商圏データ（住所 → 緯度経度 → 市区町村コード → e-Stat）。"""
    import estat_api

    coords = geocode(address)
    if not coords:
        return {"ok": False, "error": "住所から位置を特定できませんでした: {}".format(address)}
    code = estat_api.muni_code(*coords)
    if not code:
        return {"ok": False, "error": "位置から市区町村コードを特定できませんでした"}
    return fetch(code)
