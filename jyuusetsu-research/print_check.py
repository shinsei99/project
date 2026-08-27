#!/usr/bin/env python3
"""印刷イメージの目視用 — 書式を実際に作り、PDF化して1ページずつ画像にする。

**セル座標のズレは値の突き合わせでは見つからない。** 見出しの隣にあるつもりの
セルが実は結合セルの外だった、といった事故は紙面を見ないと分からないので、
出力 → PDF → PNG まで機械で運び、人（または Claude）は画像を見るだけにする。

    .venv/bin/python print_check.py                 # 基本4種を作って画像まで
    .venv/bin/python print_check.py --deal 賃貸      # 賃貸だけ
    .venv/bin/python print_check.py --no-image      # PDFまで（画像にしない）

出力先: reports/print_check/<書式名>/page-XX.png（gitignore）

### PDF 化の方法（2026-08-27 に確定）

**Microsoft Excel の AppleScript で PDF に落とせる。** 過去の記録に
「Excel の AppleScript PDF 化は -50 で不可」とあるが、それは
`save as PDF` の構文違い。`save <workbook> in <POSIX file> as PDF file format`
なら通る（76ページの契約書ブックで実測）。LibreOffice は要らない。

- **Excel が起動する**（ウィンドウは出る）。作業中の Excel があるときは注意
- 開いたブックは `close saving no` で必ず閉じる（元ファイルは書き換えない）
- 画像化は poppler の `pdftoppm`（`brew` で既に入っている）
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services import format_catalog  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "reports", "print_check")

# 目視用のダミー。**実在の人名・物件は使わない**（画像がスクラップに残るため）。
SAMPLE = {
    "所在地": "大阪府大阪市都島区中野町一丁目2番3号",
    "登記所在": "大阪市都島区中野町一丁目",
    "地番": "2番3",
    "家屋番号": "2番3",
    "家屋番号記載": "2番3",
    "地目": "宅地",
    "地積": "123.45",
    "種類": "居宅",
    "種類記載": "居宅",
    "構造": "木造かわらぶき2階建",
    "床面積": "98.76",
    "所有者": "見本　太郎",
    "抵当権": "抵当権設定登記あり",
    # ★土地と建物で別の値にしておく。**入れ違っていないか**を紙面で見分けるため
    "土地抵当権": "抵当権　平成30年3月1日設定　抵当権者　見本銀行株式会社",
    "建物抵当権": "根抵当権　令和2年7月10日設定　根抵当権者　見本信用金庫",
    "用途地域": "第一種住居地域",
    "建ぺい率": "60",
    "容積率": "200",
    "防火地域": "準防火地域",
    "高度地区": "第2種高度地区",
    "洪水浸水想定": "浸水想定区域内（0.5m未満）",
    "土砂災害": "土砂災害警戒区域内",
    "津波": "区域外",
    "高潮浸水想定": "区域外",
    "地区計画": "区域外",
    "都市計画道路": "区域外",
    "急傾斜地崩壊危険区域": "区域外",
    "地すべり防止区域": "区域外",
    "自然公園": "区域外",
    "立地適正化計画区域": "居住誘導区域内",
    "最寄駅": "京橋駅（JR大阪環状線）",
    "駅距離": "徒歩8分（620m）",
    "人口": "107,000人",
    "世帯数": "58,000世帯",
    "路線価": "185,000円/㎡",
    "公示地価": "232,000円/㎡",
    # 追加資料（管理会社の重要事項調査報告書）から入る項目
    "管理費月額": "12,300円",
    "管理費等滞納額": "0円",
    "修繕積立金月額": "8,600円",
    "修繕積立金総額": "45,800,000円",
    "管理形態": "全部委託",
    "管理組合名": "見本マンション管理組合",
    "管理会社名": "見本コミュニティ株式会社",
}

PRESET_TARGETS = [
    ("売買", "土地・建物（戸建て）", "一般売主"),
    ("売買", "区分所有（マンション）", "一般売主"),
    ("賃貸", "土地・建物（戸建て）", "一般売主"),
]


def to_pdf(xlsx: str, pdf: str) -> bool:
    """Excel で PDF 化する。開いたブックは保存せずに閉じる。"""
    script = (
        'tell application "Microsoft Excel"\n'
        '  set wb to open workbook workbook file name POSIX file "{}"\n'
        '  save wb in POSIX file "{}" as PDF file format\n'
        '  close wb saving no\n'
        'end tell'
    ).format(xlsx, pdf)
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode != 0:
        print("  ✗ PDF化に失敗: {}".format(r.stderr.strip()))
        return False
    return os.path.exists(pdf)


def to_png(pdf: str, out_dir: str, dpi: int = 110) -> int:
    if not shutil.which("pdftoppm"):
        print("  ※ pdftoppm が無いので画像化は省略（brew install poppler）")
        return 0
    os.makedirs(out_dir, exist_ok=True)
    subprocess.run(
        ["pdftoppm", "-png", "-r", str(dpi), pdf, os.path.join(out_dir, "page")],
        check=False, capture_output=True)
    return len(glob.glob(os.path.join(out_dir, "page*.png")))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deal", choices=["売買", "賃貸"], help="片方だけ作る")
    ap.add_argument("--no-image", action="store_true", help="PDFまでで止める")
    args = ap.parse_args()

    msg = format_catalog.status_message()
    if msg:
        print(msg)
        return 1

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT, exist_ok=True)

    targets = [t for t in PRESET_TARGETS if not args.deal or t[0] == args.deal]
    total_pages = 0
    for deal, kind, seller in targets:
        entries = format_catalog.preset(deal, kind, seller)
        print("\n■ {} / {} / {} … {}本".format(deal, kind, seller, len(entries)))
        for e in entries:
            work = os.path.join(OUT, "_xlsx")
            path = format_catalog.generate(e, SAMPLE, work)
            name = format_catalog.short_name(e)
            filled = format_catalog.filled_fields(e, SAMPLE)
            print("  ・{}（{}／入る項目 {}）".format(name, e.get("kind"), len(filled)))
            if e.get("kind") != "xlsx":
                print("    ※ Word なのでこの道具では画像にしない")
                continue
            pdf = os.path.join(OUT, name + ".pdf")
            if not to_pdf(path, pdf):
                continue
            if args.no_image:
                print("    → {}".format(pdf))
                continue
            n = to_png(pdf, os.path.join(OUT, name))
            total_pages += n
            print("    → {} ページを画像化".format(n))

    print("\n出力: {}".format(OUT))
    print("合計 {} ページ".format(total_pages))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
