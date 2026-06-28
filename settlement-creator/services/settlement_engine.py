"""決済清算のコアロジック。

固都税の日割り（365日ベース）、管理費等の当月日割り＋翌月前払い、
そして単一の計算結果を買主用（持参金＝プラス合算）と売主用（手取り＝
天引きでマイナス）へ符号反転してマッピングする。
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from models.settlement_data import (
    SettlementData,
    SettlementLine,
    SettlementDoc,
    DAYS_BASE,
)


# 月末タイムラグ警告のしきい値（この日以降の決済は引落停止が間に合わない恐れ）
MONTH_END_LAG_DAY = 20


def _yen(n: int) -> str:
    return f"{n:,}円"


def tax_period(settlement_date: date, start_month: int) -> tuple[date, date]:
    """決済日が属する固都税の年度期間（起算日〜翌起算日前日）を返す。

    起算日が4月1日（関西）で決済が1〜3月の場合は前年の4月1日起算となる
    （2期分またぎを正しく期間判定する）。
    """
    y = settlement_date.year
    if settlement_date >= date(y, start_month, 1):
        start = date(y, start_month, 1)
    else:
        start = date(y - 1, start_month, 1)
    end = date(start.year + 1, start.month, 1) - timedelta(days=1)
    return start, end


def compute_tax(data: SettlementData) -> dict:
    """固都税の日割り清算金（買主負担分）を算出する。

    売主は起算日〜決済日前日、買主は決済日〜期末を負担する（決済日は買主負担）。
    精算金は「売主が立替済みの年税額のうち買主負担分」を買主→売主で授受する金額。
    """
    sd = data.settlement_date
    if not sd or data.annual_tax <= 0:
        return {
            "amount": 0, "buyer_days": 0, "seller_days": 0,
            "start": None, "end": None, "note": "",
        }

    start, end = tax_period(sd, data.start_month)
    seller_days = (sd - start).days                 # 起算日〜決済日前日
    buyer_days = DAYS_BASE - seller_days            # 決済日〜期末（365日ベース）
    buyer_days = max(0, min(DAYS_BASE, buyer_days))

    amount = round(data.annual_tax * buyer_days / DAYS_BASE)
    label = data.tax_year_label or "本年度"
    note = (
        f"{label} 年税額 {_yen(data.annual_tax)} × {buyer_days}/{DAYS_BASE} = {_yen(amount)}"
        f"（起算 {start.strftime('%Y/%m/%d')}・売主{seller_days}日／買主{buyer_days}日）"
    )
    return {
        "amount": amount, "buyer_days": buyer_days, "seller_days": seller_days,
        "start": start, "end": end, "note": note,
    }


def compute_fee(data: SettlementData) -> dict:
    """管理費・修繕積立金の清算金（当月日割り＋任意で翌月前払い）を算出する。

    決済日を含む当月分の日割り（決済日以降が買主負担）に、フラグが立っていれば
    翌月分1ヶ月を満額加算する。月末近くの決済は引落停止のタイムラグ警告を返す。
    """
    sd = data.settlement_date
    monthly = data.monthly_fee
    if not sd or monthly <= 0:
        return {"amount": 0, "current": 0, "next": 0, "note": "", "lag_note": ""}

    days_in_month = calendar.monthrange(sd.year, sd.month)[1]
    buyer_days = days_in_month - sd.day + 1          # 決済日を含む当月の残日数
    current = round(monthly * buyer_days / days_in_month)
    nxt = monthly if data.next_month_fee else 0
    amount = current + nxt

    note = (
        f"{sd.month}月 当月日割り {_yen(monthly)} × {buyer_days}/{days_in_month}日 = {_yen(current)}"
    )
    if data.next_month_fee:
        nxt_month = 1 if sd.month == 12 else sd.month + 1
        note += f" ＋ {nxt_month}月分 前払い {_yen(nxt)}"

    lag_note = ""
    if sd.day >= MONTH_END_LAG_DAY:
        nxt_month = 1 if sd.month == 12 else sd.month + 1
        lag_note = (
            f"※ 所有者変更手続きの期限上、{nxt_month}月分の管理費等まで"
            f"旧所有者（売主様）の口座へ請求される場合があります。"
        )

    return {"amount": amount, "current": current, "next": nxt, "note": note, "lag_note": lag_note}


def build_documents(data: SettlementData) -> tuple[SettlementDoc, SettlementDoc]:
    """単一の計算結果から買主用・売主用の決済案内書を組み立てる。

    買主：当日支払う金額をすべてプラスで合算（持参金）。
    売主：受領をプラス、天引き経費をマイナスとし差引手取りを算出。
    """
    tax = compute_tax(data)
    fee = compute_fee(data)

    remaining_note = f"売買代金 {_yen(data.sale_price)} − 手付金 {_yen(data.deposit)}"

    # ---- 買主用（すべてプラス＝当日ご用意いただく金額） ----
    buyer = SettlementDoc(
        role="買主",
        name=data.buyer_name,
        total_label="決済時にご用意いただく金額",
    )
    buyer.lines.append(SettlementLine("売買残代金", data.remaining_price, remaining_note))
    if tax["amount"]:
        buyer.lines.append(SettlementLine("固定資産税・都市計画税 清算金", tax["amount"], tax["note"]))
    if fee["amount"]:
        buyer.lines.append(SettlementLine("管理費・修繕積立金 清算金", fee["amount"], fee["note"]))
    if data.buyer_brokerage:
        buyer.lines.append(SettlementLine("仲介手数料", data.buyer_brokerage))
    if data.buyer_registration:
        buyer.lines.append(SettlementLine("登記費用（所有権移転）", data.buyer_registration))

    # ---- 売主用（受領＝プラス、経費＝マイナスで天引き） ----
    seller = SettlementDoc(
        role="売主",
        name=data.seller_name,
        total_label="決済時にお受け取りになる金額（手取り）",
    )
    seller.lines.append(SettlementLine("売買残代金", data.remaining_price, remaining_note))
    if tax["amount"]:
        seller.lines.append(SettlementLine("固定資産税・都市計画税 清算金", tax["amount"], tax["note"]))
    if fee["amount"]:
        seller.lines.append(SettlementLine("管理費・修繕積立金 清算金", fee["amount"], fee["note"]))
    if data.seller_brokerage:
        seller.lines.append(SettlementLine("仲介手数料", -data.seller_brokerage, "天引き"))
    if data.seller_registration:
        seller.lines.append(SettlementLine("登記費用（抵当権抹消等）", -data.seller_registration, "天引き"))

    if fee["lag_note"]:
        seller.notes.append(fee["lag_note"])

    return buyer, seller
