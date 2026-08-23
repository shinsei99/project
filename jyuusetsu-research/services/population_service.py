"""人口・世帯数を e-Stat（政府統計）API で取得する。

**2026-08-20 に実装**（それまでは地域名を抽出するだけで API を呼んでいなかった）。
**2026-08-23 に直下の共有クライアント `estat_api.py` へ付け替えた**
（AI業務マネージャー `chatwork-ai-manager` からも同じ統計を引くようになり、
API の叩き方を2か所に持つのをやめたため。**このモジュールの戻り値は従来どおり**）。

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
- 地域の正式名称も API から取る（住所文字列から作ると「大阪府大阪市」のように
  **区が落ちて実データと食い違う**ため）

appId・キャッシュ・API の細かい仕様は `estat_api.py` 側に書いてある。
appId が無ければ空欄で継続する（アプリは止めない）。
"""

import pathlib
import re
import sys
from typing import Dict, Optional, Tuple

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import estat_api  # 直下の共有クライアント（他アプリと同じ1本）

CAT_POPULATION = "A1101"  # 総人口
CAT_HOUSEHOLDS = "A7101"  # 世帯数


def get_app_id() -> str:
    """appId を取得する（環境変数 → st.secrets → 直下 .env.estat）。"""
    return estat_api.get_app_id()


def muni_code(lat: float, lon: float) -> str:
    """緯度経度 → 全国地方公共団体コード（5桁）。取れなければ空文字。"""
    return estat_api.muni_code(lat, lon)


def _extract_municipality(address: str) -> str:
    """住所文字列から「市区町村」までを簡易抽出する（API 名称が取れなかったときの控え）。"""
    if not address:
        return ""
    m = re.search(r"(.+?[都道府県])?(.+?[市区町村])", address)
    if m:
        return (m.group(1) or "") + m.group(2)
    return ""


def get_population(address: str, coords: Optional[Tuple[float, float]] = None) -> Dict[str, str]:
    """人口・世帯数を取得する。appId 未設定・取得失敗時は空文字で継続。

    `coords` を渡すと逆ジオコーディングだけで済む（app.py は調査済みの座標を渡す）。
    """
    result = {"人口": "", "世帯数": ""}
    if not get_app_id():
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
        area = estat_api.city_values(code, "population", [CAT_POPULATION, CAT_HOUSEHOLDS])
    except Exception:
        return result  # 通信失敗・appId 不正でもアプリは止めない

    values = area["values"]
    label = area["name"] or _extract_municipality(address) or "当該市区町村"

    pop = values.get(CAT_POPULATION)
    if pop and pop.get("value") is not None:
        result["人口"] = "{:,}人（{}年・{}）".format(int(pop["value"]), pop["year"], label)
    house = values.get(CAT_HOUSEHOLDS)
    if house and house.get("value") is not None:
        result["世帯数"] = "{:,}世帯（{}年）".format(int(house["value"]), house["year"])
    return result
