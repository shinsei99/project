# -*- coding: utf-8 -*-
"""決済の日割り清算が変わっていないかを確かめる（2026-08-23 追加）。

    .venv/bin/python smoke_test.py

**なぜ要るか**: このアプリの中身は「固都税と管理費の日割り」で、壊れても画面は開く。
**決済の席で数字が合わない**という形でしか気づけない。授受する金額そのものなので、
期待値を手計算で書いて固定しておく。

期待値の根拠は各チェックのコメントに書いた。**engine の考え方を変えたら、まずここを直すこと。**
"""

import sys
from datetime import date

from models.settlement_data import DAYS_BASE, SettlementData
from services import settlement_engine as engine

FAILED = []


def check(label, got, want):
    ok = got == want
    print("  {} {:<46} 実際={!s:<12} 期待={!s}".format("✓" if ok else "✗", label, got, want))
    if not ok:
        FAILED.append(label)


def main():
    print("■ 固都税の年度期間（関西＝4月1日起算）")
    # 決済が7月 → その年の4/1〜翌年3/31
    check("2026/07/15 の起算日", engine.tax_period(date(2026, 7, 15), 4)[0], date(2026, 4, 1))
    check("2026/07/15 の期末", engine.tax_period(date(2026, 7, 15), 4)[1], date(2027, 3, 31))
    # 決済が1〜3月 → **前年**の4/1起算（ここを間違えると1年ずれる）
    check("2026/02/10 の起算日（前年度）", engine.tax_period(date(2026, 2, 10), 4)[0], date(2025, 4, 1))
    check("2026/02/10 の期末", engine.tax_period(date(2026, 2, 10), 4)[1], date(2026, 3, 31))
    # 関東（1月1日起算）
    check("関東 2026/07/15 の起算日", engine.tax_period(date(2026, 7, 15), 1)[0], date(2026, 1, 1))

    print("■ 固都税の日割り（決済日は買主負担）")
    # 起算 2026/4/1 → 決済 2026/7/15 まで 105日が売主、残り 260日が買主
    # 年税額 146,000円 × 260/365 = 104,000円
    data = SettlementData(
        settlement_date=date(2026, 7, 15), start_month=4,
        fixed_asset_tax=100000, city_planning_tax=46000, tax_year_label="令和8年度",
        mgmt_fee_monthly=12000, repair_fee_monthly=8000,
    )
    tax = engine.compute_tax(data)
    check("年税額（固都税の合計）", data.annual_tax, 146000)
    check("売主の日数（起算〜決済前日）", tax["seller_days"], 105)
    check("買主の日数（決済日〜期末）", tax["buyer_days"], 260)
    check("売主＋買主＝365日", tax["seller_days"] + tax["buyer_days"], DAYS_BASE)
    check("買主が払う清算金", tax["amount"], 104000)

    # 起算日当日の決済 → 全額が買主負担
    d0 = SettlementData(settlement_date=date(2026, 4, 1), start_month=4, fixed_asset_tax=146000)
    check("起算日に決済したら買主365日", engine.compute_tax(d0)["buyer_days"], 365)
    check("その清算金は年税額と同じ", engine.compute_tax(d0)["amount"], 146000)

    # 税額が無いときは0で返す（例外にしない）
    check("年税額0なら清算金0", engine.compute_tax(SettlementData(
        settlement_date=date(2026, 7, 15)))["amount"], 0)

    print("■ 管理費・修繕積立金の日割り")
    # 月額 20,000円（管理12,000＋修繕8,000）。7月は31日、決済7/15 → 買主17日分
    # 20,000 × 17/31 = 10,967.7… → 四捨五入 10,968
    fee = engine.compute_fee(data)
    check("月額（管理＋修繕）", data.monthly_fee, 20000)
    check("当月の買主負担（7/15〜7/31＝17日）", fee["current"], 10968)
    check("翌月前払いなし", fee["next"], 0)
    check("合計", fee["amount"], 10968)

    # 翌月前払いあり
    data2 = SettlementData(settlement_date=date(2026, 7, 15), mgmt_fee_monthly=12000,
                           repair_fee_monthly=8000, next_month_fee=True)
    fee2 = engine.compute_fee(data2)
    check("翌月分を足すと 10,968＋20,000", fee2["amount"], 30968)

    # 月末近くの決済は引落タイムラグの注意書きが出る（20日以降）
    late = engine.compute_fee(SettlementData(settlement_date=date(2026, 7, 25),
                                             mgmt_fee_monthly=20000))
    check("25日決済はタイムラグ注意あり", bool(late["lag_note"]), True)
    early = engine.compute_fee(SettlementData(settlement_date=date(2026, 7, 5),
                                              mgmt_fee_monthly=20000))
    check("5日決済は注意なし", bool(early["lag_note"]), False)

    # 2月（28日）と閏年（29日）で分母が変わる
    feb = engine.compute_fee(SettlementData(settlement_date=date(2026, 2, 15),
                                            mgmt_fee_monthly=28000))
    check("2026/02/15（28日月）14日分", feb["current"], 14000)
    leap = engine.compute_fee(SettlementData(settlement_date=date(2028, 2, 15),
                                             mgmt_fee_monthly=29000))
    check("2028/02/15（閏年29日月）15日分", leap["current"], 15000)

    print("■ 買主用・売主用の案内書が両方できる")
    buyer_doc, seller_doc = engine.build_documents(data)
    check("買主用ができる", buyer_doc is not None, True)
    check("売主用ができる", seller_doc is not None, True)

    print()
    if FAILED:
        print("✗ {} 件ずれています: {}".format(len(FAILED), " / ".join(FAILED)))
        return 1
    print("ALL SMOKE TESTS PASSED（決済の日割り清算）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
