# -*- coding: utf-8 -*-
"""計算エンジンと Excel 生成の疎通確認。venv で: .venv/bin/python smoke_test.py"""

from services.proforma import Inputs, compute
from services.excel_builder import build_workbook


def main():
    # 三神マンション相当のサンプル（万円）
    inp = Inputs(
        物件名="三神マンション", 所在地="大阪市城東区中央2丁目6-1",
        敷地面積=330.57, 延床面積=913.09, 建物構造="共同住宅 RC造 地上6階",
        戸数="14戸", 駐車場="パーキング10台", 築年="H5年3月",
        用途地域="第1種", 建ぺい率="60", 容積率="300", 交通="京阪野江駅 徒歩6分",
        基準日="2024/01/10",
        土地代=11000, 建物代=12000, 消費税=1200, 保証金=1000, 借入総額=10000,
        土地評価額=2050, 建物評価額=6500,
        借入金利=0.38, 借入年数=10, 月額賃料=141,
        固都税土地=21, 固都税建物=110, 火災保険=30, リフォーム代=323,
        管理費月=13.5, 法定耐用年数=48, 築年数=30,
        印紙=16, 司法書士その他=20, 予備費=73,
    )
    res = compute(inp)
    print("総事業費:", res["資金計画"]["総事業費"], "万")
    print("借入/自己資金:", res["資金計画"]["借入総額"], "/", res["資金計画"]["自己資金"])
    print("年収:", res["収入"]["年収"])
    print("金利平均:", res["支出"]["金利平均"], "償却:", res["支出"]["償却"], "(", res["支出"]["償却年数"], "年)")
    print("利回り 実/経費込/単純:", res["利回り"]["実利回り"], res["利回り"]["経費込利回り"], res["利回り"]["単純利回り"])
    print("CF あり/なし:", res["CF"]["借入あり"], res["CF"]["借入なし"])
    print("諸費用: 仲介料", res["諸費用内訳"]["仲介料"], " 合計", res["諸費用内訳"]["合計"])

    buf = build_workbook(inp)
    with open("_smoke_out.xlsx", "wb") as f:
        f.write(buf.getvalue())
    print("Excel 出力 OK -> _smoke_out.xlsx (", len(buf.getvalue()), "bytes )")


if __name__ == "__main__":
    main()
