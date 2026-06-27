"""ガイドライン準拠・減価償却エンジン。

国土交通省「原状回復をめぐるトラブルとガイドライン」の考え方に基づき、
各明細の入居者負担率を入居年数から算出し、業者見積金額を按分する。
"""

from __future__ import annotations

import math

from models.restoration_data import (
    RestorationData,
    LineItem,
    FAULT_NATURAL,
)


# 部材種別 → 耐用年数（年）。None は経過年数を考慮しない（償却なし）。
#   ガイドライン: クロス・CF・カーペット等は6年で残存価値1円まで直線償却。
#   畳・襖・障子・ハウスクリーニングは経過年数を考慮しない。
USEFUL_LIFE = {
    "壁クロス": 6,
    "CF": 6,
    "クッションフロア": 6,
    "カーペット": 6,
    "畳": None,
    "襖": None,
    "障子": None,
    "ハウスクリーニング": None,
    "フローリング": None,
    "その他": None,
}


def _tenant_rate(material_type: str, residence_years: float) -> tuple[float, int | None, str]:
    """入居者負担率・耐用年数・根拠メモを返す。

    残存価値率 = (耐用年数 - 経過年数) / 耐用年数。
    フロアは0、フルに償却済みでも0%まで（ガイドラインの残存1円は金額側で表現）。
    """
    life = USEFUL_LIFE.get(material_type, None)

    if life is None:
        # 経過年数を考慮しない部材 → 故意過失なら100%負担
        return 1.0, None, "経過年数考慮なし（耐用年数の定めなし）→ 入居者負担100%"

    # 直線償却で残存価値率を算出
    remaining = (life - residence_years) / life
    remaining = max(0.0, min(1.0, remaining))
    rate = round(remaining, 4)
    basis = (
        f"耐用年数{life}年・経過{residence_years:.2f}年 → "
        f"残存価値率{rate * 100:.1f}%"
    )
    return rate, life, basis


def calculate(data: RestorationData) -> RestorationData:
    """全明細について入居者負担額・オーナー負担額を計算し、`data` を更新して返す。"""
    years = data.residence_years

    for item in data.items:
        _calc_item(item, years)

    return data


def _calc_item(item: LineItem, residence_years: float) -> None:
    # 経年劣化（通常損耗）は一律で入居者負担0円
    if item.fault == FAULT_NATURAL:
        item.useful_life = USEFUL_LIFE.get(item.material_type, None)
        item.tenant_rate = 0.0
        item.tenant_amount = 0
        item.owner_amount = item.vendor_amount
        item.basis = "経年劣化（通常損耗）→ 入居者負担0円（オーナー負担）"
        return

    rate, life, basis = _tenant_rate(item.material_type, residence_years)
    # 1円未満切り捨て
    tenant_amount = int(math.floor(item.vendor_amount * rate))
    owner_amount = item.vendor_amount - tenant_amount

    item.useful_life = life
    item.tenant_rate = rate
    item.tenant_amount = tenant_amount
    item.owner_amount = owner_amount
    item.basis = basis
