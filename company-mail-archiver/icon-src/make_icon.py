#!/usr/bin/env python3
"""社内メールアーカイバのアイコンを作る。

    /usr/bin/python3 icon-src/make_icon.py

出力: icon-src/appicon-1024.png ＋ Desktop/社内ツール/社内メールアーカイバ.app 用の .icns

## 作法（Desktop/社内ツール の他アプリに合わせる）

実物を見て合わせた: **単色の角丸四角の背景に、白い図形をひとつ**。
影も文字もグラデーションも使わない（32pxまで縮んでも形が分かるため）。

- 書類キャビネット … 青紫の背景＋白いキャビネット
- AI業務マネージャー … 青の背景＋白い吹き出しとロボット

このアプリは **深い緑（#0F766E）**。近くにある2本（メールアーカイバ＝白基調・
AI業務マネージャー＝青）と並べたときに取り違えないため。

図柄は「会社の建物 ＋ 封筒」。**個人のメールアーカイバ（受信トレイの絵）とは別物**だと
一目で分かるようにしてある。
"""
from __future__ import annotations

import os
import subprocess
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
SIZE = 1024
BG = (15, 118, 110)          # #0F766E 深い緑
FG = (255, 255, 255)


def draw_icon() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 背景（角丸四角）。半径は一辺の約22%＝他のアイコンと同じ見え方
    d.rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=int(SIZE * 0.22), fill=BG)

    # ---- 会社の建物（封筒の後ろに立つ。下半分は封筒に隠れる）
    bx0, bx1 = 372, 652
    d.rectangle([bx0, 200, bx1, 620], fill=FG)
    # 窓（背景色で抜く＝白の中に色が乗る作り。書類キャビネットと同じ手）
    w, gap = 54, 34
    cols = [bx0 + 42, bx0 + 42 + w + gap, bx0 + 42 + 2 * (w + gap)]
    rows = [252, 252 + w + gap, 252 + 2 * (w + gap)]
    for ry in rows:
        for cx in cols:
            d.rectangle([cx, ry, cx + w, ry + w], fill=BG)

    # ---- 封筒（手前）
    ex0, ey0, ex1, ey1 = 190, 520, 834, 838
    d.rounded_rectangle([ex0, ey0, ex1, ey1], radius=44, fill=FG)
    # ふた（V字）。封筒の中だけに出すため、いったん別画像に描いて切り抜く
    flap = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    fd = ImageDraw.Draw(flap)
    fd.line([(ex0 + 26, ey0 + 26), ((ex0 + ex1) // 2, ey0 + 250), (ex1 - 26, ey0 + 26)],
            fill=BG, width=38, joint="curve")
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle([ex0, ey0, ex1, ey1], radius=44, fill=255)
    img.paste(flap, (0, 0), Image.composite(flap.split()[3], Image.new("L", (SIZE, SIZE), 0), mask))
    return img


def main() -> int:
    img = draw_icon()
    png = os.path.join(HERE, "appicon-1024.png")
    img.save(png)
    print("作った: {}".format(png))

    # .icns（Desktop の .app 用）
    iconset = os.path.join(HERE, "AppIcon.iconset")
    os.makedirs(iconset, exist_ok=True)
    for px in (16, 32, 64, 128, 256, 512, 1024):
        for name, s in ((f"icon_{px}x{px}.png", px),
                        (f"icon_{px//2}x{px//2}@2x.png", px)):
            if px == 16 and "@2x" in name:
                continue
            img.resize((s, s), Image.LANCZOS).save(os.path.join(iconset, name))
    icns = os.path.join(HERE, "AppIcon.icns")
    r = subprocess.run(["iconutil", "-c", "icns", iconset, "-o", icns],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("iconutil 失敗: {}".format(r.stderr.strip()[:200]), file=sys.stderr)
        return 1
    print("作った: {}".format(icns))
    return 0


if __name__ == "__main__":
    sys.exit(main())
