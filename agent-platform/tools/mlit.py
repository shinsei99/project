"""アイテム: 不動産の実取引価格・地価（国交省 不動産情報ライブラリ）

キーは新たに取らない。**この機械に既にあるキーを探して使う**（実測で疎通確認済み）。
  1. 環境変数 REINFOLIB_API_KEY
  2. realestate-valuation / legal-crosscheck / jyuusetsu-research の
     .streamlit/secrets.toml にある reinfolib_api_key

これがあると「相場は〜と思われる」ではなく、実際の取引データで書ける。
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

NAME = "mlit"
LABEL = "実取引価格・地価（国交省）"
DESCRIPTION = ("都道府県・年・四半期を指定して不動産の実取引データを取る。"
               "相場を推測せず実データで書くために使う")

_BASE = "https://www.reinfolib.mlit.go.jp/ex-api/external"
_SECRET_PATHS = [
    "realestate-valuation/.streamlit/secrets.toml",
    "legal-crosscheck/.streamlit/secrets.toml",
    "jyuusetsu-research/.streamlit/secrets.toml",
]
# 都道府県コード（よく使うものだけ。全国は 01〜47）
PREFECTURES = {"東京都": "13", "大阪府": "27", "兵庫県": "28", "京都府": "26",
               "奈良県": "29", "和歌山県": "30", "滋賀県": "25", "愛知県": "23",
               "神奈川県": "14", "埼玉県": "11", "千葉県": "12", "福岡県": "40"}


def find_api_key() -> Optional[str]:
    key = os.getenv("REINFOLIB_API_KEY", "").strip()
    if key:
        return key
    home = Path(__file__).resolve().parent.parent.parent  # /Users/apple
    for rel in _SECRET_PATHS:
        path = home / rel
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        found = re.search(r'^\s*reinfolib_api_key\s*=\s*"([^"]+)"', text, re.M)
        if found and len(found.group(1)) > 8:
            return found.group(1)
    return None


def available() -> Tuple[bool, str]:
    try:
        import requests  # noqa: F401
    except Exception:
        return False, "requests 未導入"
    if not find_api_key():
        return False, "APIキーが見つかりません（reinfolib.mlit.go.jp で無料発行）"
    return True, "既存アプリのキーを流用して使えます"


def prefecture_code(name: str) -> Optional[str]:
    for key, code in PREFECTURES.items():
        if key.rstrip("都府県") in (name or ""):
            return code
    return None


def transactions(area: str, year: int, quarter: int = 1,
                 city_keyword: str = "", limit: int = 50,
                 timeout: int = 60) -> List[Dict[str, Any]]:
    """取引価格情報。area は都道府県コード（"28"）か都道府県名（"兵庫県"）。

    件数が多い（1県1四半期で数千件）ので、市区町村名で絞ってから返す。
    """
    import requests

    key = find_api_key()
    if not key:
        raise RuntimeError("国交省APIキーが見つかりません")
    code = area if str(area).isdigit() else prefecture_code(area)
    if not code:
        raise ValueError("都道府県を特定できません: %s" % area)

    resp = requests.get("%s/XIT001" % _BASE,
                        params={"year": year, "quarter": quarter, "area": code},
                        headers={"Ocp-Apim-Subscription-Key": key}, timeout=timeout)
    resp.raise_for_status()
    items = (resp.json() or {}).get("data") or []
    if city_keyword:
        items = [x for x in items
                 if city_keyword in "%s%s" % (x.get("Municipality") or "",
                                              x.get("DistrictName") or "")]
    return items[:limit]


def summarize(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """取引データを要約する。中央値まで出しておくと原稿にそのまま書ける。"""
    prices, unit_prices = [], []
    for x in items:
        try:
            price = int(x.get("TradePrice") or 0)
            area = float(x.get("Area") or 0)
        except (TypeError, ValueError):
            continue
        if price > 0:
            prices.append(price)
            if area > 0:
                unit_prices.append(price / area)

    def median(values):
        if not values:
            return 0
        values = sorted(values)
        mid = len(values) // 2
        return values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2

    return {"count": len(items),
            "median_price": int(median(prices)),
            "median_unit_price_per_sqm": int(median(unit_prices)),
            "min_price": min(prices) if prices else 0,
            "max_price": max(prices) if prices else 0}
