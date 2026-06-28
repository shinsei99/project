"""賃貸初回精算のコアロジック。

入居者用の初期費用請求明細（当月日割り＋翌月満額＋一時金＋仲介手数料）と、
オーナー用の初回送金精算（礼金・初月賃料の受取 − AD・仲介・管理手数料の天引き）を
生成する。日割りは実務の請求書に合わせ切り捨て（floor）で算出する。
"""

from __future__ import annotations

import calendar
from datetime import date

from models.rental_data import RentalData, RentLine


def _yen(n: int) -> str:
    return f"{n:,}円"


def proration(monthly: int, d: date) -> tuple[int, int, int]:
    """入居日 d を含む当月の日割り額を返す。

    returns (日割り額, 当月残日数, 当月日数)。端数は切り捨て（実務慣習）。
    """
    days_in_month = calendar.monthrange(d.year, d.month)[1]
    days = days_in_month - d.day + 1          # 入居日〜月末（入居日を含む）
    amount = monthly * days // days_in_month  # 切り捨て
    return amount, days, days_in_month


def build_tenant_invoice(data: RentalData) -> list[RentLine]:
    """入居者向け初期費用 精算明細（請求書）を生成する。

    請求書2.xls の項目を網羅：当月日割り（家賃・共益費・火災保険・駐車場）、
    翌月満額、礼金・敷金・保証料・鍵交換・駐車場礼金・リモコン代、仲介手数料（割引可）。
    """
    lines: list[RentLine] = []
    d = data.move_in_date

    # ---- 当月分（日割り） ----
    if d:
        cur_month = d.month
        components = [
            (f"{cur_month}月分 家賃", data.rent),
            (f"{cur_month}月分 共益費", data.common_fee),
            (f"{cur_month}月分 火災保険・サポート", data.insurance),
            (f"{cur_month}月分 駐車場", data.parking),
        ]
        for label, monthly in components:
            if monthly > 0:
                amt, days, dim = proration(monthly, d)
                lines.append(RentLine(label, amt, f"日割{days}日分（{monthly:,}円×{days}/{dim}）"))

        # ---- 翌月分（満額） ----
        nxt = 1 if d.month == 12 else d.month + 1
        nxt_components = [
            (f"{nxt}月分 家賃", data.rent),
            (f"{nxt}月分 共益費", data.common_fee),
            (f"{nxt}月分 火災保険・サポート", data.insurance),
            (f"{nxt}月分 駐車場", data.parking),
        ]
        for label, monthly in nxt_components:
            if monthly > 0:
                lines.append(RentLine(label, monthly, ""))

    # ---- 一時金 ----
    onetime = [
        ("敷金", data.deposit, "預り金"),
        ("礼金", data.key_money, ""),
        ("家賃保証料", data.guarantee_fee, ""),
        ("鍵交換代", data.key_exchange, ""),
        ("駐車場礼金", data.parking_key_money, ""),
        ("リモコン代", data.remote_fee, ""),
    ]
    for label, amt, note in onetime:
        if amt > 0:
            lines.append(RentLine(label, amt, note))

    # ---- 仲介手数料（割引はマイナス行） ----
    if data.brokerage > 0:
        lines.append(RentLine("仲介手数料", data.brokerage, ""))
    if data.brokerage_discount > 0:
        lines.append(RentLine("仲介手数料 紹介割引", -data.brokerage_discount, ""))

    return lines


def build_owner_remittance(data: RentalData) -> list[RentLine]:
    """オーナー向け初回送金精算（契約時）を生成する。

    受取：礼金・当月日割り賃料・翌月賃料。天引き：広告料(AD)・仲介手数料(貸主負担)・
    集金代行(管理)手数料。差引がオーナー手取り（送金額）。
    """
    lines: list[RentLine] = []
    d = data.move_in_date

    # ---- 受取 ----
    if data.key_money > 0:
        lines.append(RentLine("礼金", data.key_money, "オーナー受取"))
    if d and data.rent > 0:
        amt, days, dim = proration(data.rent, d)
        lines.append(RentLine(f"{d.month}月分 家賃（日割）", amt, f"日割{days}日分（{data.rent:,}円×{days}/{dim}）"))
        nxt = 1 if d.month == 12 else d.month + 1
        lines.append(RentLine(f"{nxt}月分 家賃", data.rent, ""))

    # ---- 天引き（管理会社等への支払い） ----
    if data.ad_fee > 0:
        lines.append(RentLine("広告料（AD）", -data.ad_fee, "管理会社へ"))
    if data.owner_brokerage > 0:
        lines.append(RentLine("仲介手数料（貸主負担）", -data.owner_brokerage, "天引き"))
    if data.rent > 0 and data.mgmt_fee_rate > 0:
        mgmt = int(data.rent * data.mgmt_fee_rate / 100)   # 切り捨て
        lines.append(RentLine("集金代行（管理）手数料", -mgmt, f"家賃の{data.mgmt_fee_rate:g}%"))

    return lines


def build_defaults(data: RentalData) -> RentalData:
    """tenant_items / owner_items を自動生成して埋めた RentalData を返す。"""
    data.tenant_items = build_tenant_invoice(data)
    data.owner_items = build_owner_remittance(data)
    return data
