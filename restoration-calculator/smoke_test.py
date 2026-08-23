# -*- coding: utf-8 -*-
"""原状回復の按分計算が変わっていないかを確かめる（2026-08-23 追加）。

    .venv/bin/python smoke_test.py     （依存が要るのは Excel 出力のところだけ）

**なぜ要るか**: このアプリの中身は「国交省ガイドラインに沿った負担割合の計算」で、
壊れても画面はふつうに開く。**間違った精算書が出て初めて気づく**種類の壊れ方をする。
金額は退去者に請求する数字なので、期待値を直に書いて固定しておく。

期待値は手計算（下のコメント）。**engine の仕様を変えたときは、まずここを直すこと。**
"""

import sys
from datetime import date

from models.restoration_data import (FAULT_NATURAL, FAULT_TENANT, LineItem,
                                     RestorationData)
from services import depreciation_engine as engine

FAILED = []


def check(label, got, want):
    ok = got == want
    print("  {} {:<44} 実際={!s:<10} 期待={!s}".format("✓" if ok else "✗", label, got, want))
    if not ok:
        FAILED.append(label)


def main():
    # 入居 2020-04-01 → 退去 2023-04-01 ＝ 1095日 ＝ 3.0年
    data = RestorationData(
        tenant_name="テスト太郎", property_name="テストマンション", room_number="101",
        move_in_date=date(2020, 4, 1), move_out_date=date(2023, 4, 1), deposit=100000,
        items=[
            # ① 壁クロス（耐用6年・故意過失・全額対象）
            #    残存率 =(6-3)/6 = 0.5 → 入居者 60,000×0.5 = 30,000
            LineItem(name="壁クロス張替", vendor_amount=60000,
                     material_type="壁クロス", fault=FAULT_TENANT),
            # ② CF（耐用6年・故意過失・部分補修 10/50＝20%）
            #    対象 60,000×0.2 = 12,000 → 入居者 12,000×0.5 = 6,000
            LineItem(name="CF張替", vendor_amount=60000, material_type="CF",
                     fault=FAULT_TENANT, total_qty=50, fault_qty=10, unit="㎡"),
            # ③ 畳（耐用年数の定めなし・故意過失）→ 全額入居者
            LineItem(name="畳表替", vendor_amount=20000, material_type="畳",
                     fault=FAULT_TENANT),
            # ④ ハウスクリーニング（経年劣化＝通常損耗）→ 入居者0・オーナー全額
            LineItem(name="ハウスクリーニング", vendor_amount=30000,
                     material_type="ハウスクリーニング", fault=FAULT_NATURAL),
            # ⑤ 諸経費（按分）: 工事費の入居者:オーナー ＝ 56,000 : 114,000
            #    率 = 56,000/170,000 = 0.32941… → 入居者 floor(10,000×0.3294)=3,294
            LineItem(name="諸経費", vendor_amount=10000, material_type="諸経費",
                     fault=FAULT_NATURAL),
        ],
    )

    print("■ 入居期間")
    check("入居日数", data.residence_days, 1095)
    check("入居年数（償却に使う）", data.residence_years, 3.0)

    print("■ 残存価値率（直線償却）")
    check("耐用6年・経過3年", engine.residual_rate(6, 3.0), 0.5)
    check("耐用6年・経過6年（下限0）", engine.residual_rate(6, 6.0), 0.0)
    check("耐用6年・経過8年（マイナスにしない）", engine.residual_rate(6, 8.0), 0.0)
    check("耐用6年・経過0年（上限1）", engine.residual_rate(6, 0.0), 1.0)

    engine.calculate(data)
    kabe, cf, tatami, hc, shokei = data.items

    print("■ 明細ごとの負担額")
    check("① 壁クロス 入居者", kabe.tenant_amount, 30000)
    check("① 壁クロス オーナー", kabe.owner_amount, 30000)
    check("② CF 入居者（部分補修20%）", cf.tenant_amount, 6000)
    check("② CF オーナー", cf.owner_amount, 54000)
    check("③ 畳 入居者（全額）", tatami.tenant_amount, 20000)
    check("④ クリーニング 入居者（経年劣化）", hc.tenant_amount, 0)
    check("④ クリーニング オーナー", hc.owner_amount, 30000)
    check("⑤ 諸経費 入居者（按分）", shokei.tenant_amount, 3294)
    check("⑤ 諸経費 オーナー", shokei.owner_amount, 6706)

    print("■ 合計（精算書に出る数字）")
    tenant_total = sum(i.tenant_amount for i in data.items)
    owner_total = sum(i.owner_amount for i in data.items)
    check("入居者負担 合計", tenant_total, 59294)
    check("オーナー負担 合計", owner_total, 120706)
    check("業者見積 合計と一致", tenant_total + owner_total,
          sum(i.vendor_amount for i in data.items))

    print("■ 部材の方針（ガイドラインの対応表）")
    check("壁クロスは償却対象", engine.policy_of("壁クロス"), engine.DEPRECIABLE)
    check("壁クロスの耐用年数", engine.life_of("壁クロス"), 6)
    check("畳は耐用年数なし", engine.life_of("畳"), None)
    check("諸経費は按分", engine.policy_of("諸経費"), engine.APPORTION)
    check("未知の部材は全額扱い（既定）", engine.policy_of("知らない部材"), engine.FULL_FAULT)

    print()
    if FAILED:
        print("✗ {} 件ずれています: {}".format(len(FAILED), " / ".join(FAILED)))
        return 1
    print("ALL SMOKE TESTS PASSED（原状回復の按分計算）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
