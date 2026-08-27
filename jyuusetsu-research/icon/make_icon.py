#!/usr/bin/env python3
"""社内配布用アイコンを作る（Mac の .icns と Windows の .ico）。

社内ツールのアイコンは **角丸の一色ベタ＋白い絵** で揃えてある。
色は他の25本と重ならないものを選んだ（実測して空いていた深いプラム）。
絵は「書類＋チェック」＝重要事項説明書を作って検算する、の意。

    ~/agent-platform/.venv/bin/python icon/make_icon.py

出力:
    icon/AppIcon.icns   … Desktop/社内ツール/<名前>.app に入れる
    icon/AI重説アシスタント.ico … Dropbox の 社内ツール/icons/ に置く

Pillow が要る。このアプリの .venv には入れていないので
`agent-platform/.venv` の python で動かす（アイコンは1回作れば済むため）。
"""

import os
import subprocess
import tempfile

from PIL import Image, ImageDraw

BASE = os.path.dirname(os.path.abspath(__file__))
BG = (142, 47, 94)          # 深いプラム。既存25本のどれとも重ならない
FG = (255, 255, 255)
SIZE = 1024


def draw(size: int = SIZE) -> Image.Image:
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = int(size * 0.22)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=BG)

    # 書類（右上の角を折った紙）
    m = size * 0.24
    w, h = size * 0.46, size * 0.58
    x0, y0 = m, size * 0.19
    x1, y1 = x0 + w, y0 + h
    fold = size * 0.13
    d.polygon([(x0, y0), (x1 - fold, y0), (x1, y0 + fold), (x1, y1), (x0, y1)], fill=FG)
    # 折り返しの三角（背景色で抜く）
    d.polygon([(x1 - fold, y0), (x1 - fold, y0 + fold), (x1, y0 + fold)], fill=BG)

    # 本文の線
    lw = max(2, int(size * 0.022))
    for i in range(4):
        ly = y0 + size * 0.20 + i * size * 0.075
        d.line([(x0 + size * 0.06, ly), (x1 - size * 0.06, ly)], fill=BG, width=lw)

    # 右下のチェック（検算・確認）
    cx, cy, cr = size * 0.70, size * 0.70, size * 0.20
    d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=FG)
    d.ellipse([cx - cr * 0.82, cy - cr * 0.82, cx + cr * 0.82, cy + cr * 0.82], fill=BG)
    cw = max(3, int(size * 0.045))
    d.line([(cx - cr * 0.42, cy), (cx - cr * 0.08, cy + cr * 0.34)], fill=FG, width=cw)
    d.line([(cx - cr * 0.08, cy + cr * 0.34), (cx + cr * 0.46, cy - cr * 0.38)],
           fill=FG, width=cw)
    return im


def main() -> None:
    master = draw()
    png = os.path.join(BASE, "icon-1024.png")
    master.save(png)

    # ---- macOS .icns（iconutil は .iconset フォルダを食う）----
    with tempfile.TemporaryDirectory() as td:
        iconset = os.path.join(td, "AppIcon.iconset")
        os.makedirs(iconset)
        for px in (16, 32, 64, 128, 256, 512, 1024):
            master.resize((px, px), Image.LANCZOS).save(
                os.path.join(iconset, "icon_{0}x{0}.png".format(px)))
            if px <= 512:
                master.resize((px * 2, px * 2), Image.LANCZOS).save(
                    os.path.join(iconset, "icon_{0}x{0}@2x.png".format(px)))
        subprocess.run(["iconutil", "-c", "icns", iconset,
                        "-o", os.path.join(BASE, "AppIcon.icns")], check=True)

    # ---- Windows .ico ----
    master.save(os.path.join(BASE, "AI重説アシスタント.ico"),
                sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("作成:", os.path.join(BASE, "AppIcon.icns"))
    print("作成:", os.path.join(BASE, "AI重説アシスタント.ico"))


if __name__ == "__main__":
    main()
