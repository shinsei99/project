#!/usr/bin/env python3
"""アプリアイコンを作る（1024×1024・角丸なし・アルファなし）。

    ../../agent-platform/.venv/bin/python make_icon.py

2026-08-27 にオーナー支給の画像（`source_2026-08-27.png`）へ差し替えた。
それ以前は PIL で図案を描いていた（開いた本＋空色の虫めがね）。旧版のコードは
git 履歴にある（`git log -p icon-src/make_icon.py`）。

支給画像の扱い（ここを外すとホーム画面で角が白く欠ける）
----------------------------------------------------------
支給画像は **白背景の上に角丸の正方形アイコンが乗った状態**（1254×1254・周囲に白い余白）。
iOS は自分で角丸マスクを掛けるので、**アイコンは角まで塗った四角**で渡さなければならない。
そのため次の順で整える。

1. 角丸正方形の本体だけを切り出す（白余白と落ち影を落とす）
2. 1024×1024 に縮める
3. **角丸の外側（＝白が残る部分）をアイコンの地色で塗り潰す**
   iOS のマスク半径（1024 なら約 229px）よりわずかに大きい半径で塗るので、
   マスク後に地色が見えるのは輪郭のごく細い部分だけ

App Store のアイコンは**透明を含められない**ので、必ず RGB（アルファ無し）で保存する。
"""
from PIL import Image, ImageDraw, ImageFilter
import numpy as np

SRC = "source_2026-08-27.png"
S = 1024
CORNER_RADIUS = 239   # 支給画像の角丸を 1024 に換算した値（iOS の約229より少し大きい）

img = Image.open(SRC).convert("RGB")

# --- 1. 角丸正方形の本体だけを切り出す -------------------------------------
# 白でない（＝暗い）画素が縦横に長く連なる範囲を本体とみなす。
# しきい値の 600 は「1254px の半分近く連なっていれば本体の辺」という意味で、
# 落ち影のような薄く短い帯を拾わないために置いている。
arr = np.asarray(img).astype(int)
dark = arr.mean(axis=2) < 200
cols = np.where(dark.sum(axis=0) > 600)[0]
rows = np.where(dark.sum(axis=1) > 600)[0]
x0, x1 = int(cols.min()), int(cols.max())
y0, y1 = int(rows.min()), int(rows.max())
# 落ち影のぶん縦横がわずかにずれるので、短い方の辺に合わせて正方形にする
side = min(x1 - x0 + 1, y1 - y0 + 1)
body = img.crop((x0, y0, x0 + side, y0 + side)).resize((S, S), Image.LANCZOS)

# --- 2. 角の外側をアイコンの地色で塗る --------------------------------------
# 地色は「辺の内側 40px の帯」の中央値（濃紺）。角の白は帯に入らないので混ざらない。
b = np.asarray(body).astype(int)
band = np.concatenate([b[40:80, :, :].reshape(-1, 3), b[-80:-40, :, :].reshape(-1, 3)])
bg = tuple(int(v) for v in np.median(band, axis=0))

mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=CORNER_RADIUS, fill=255)
mask = mask.filter(ImageFilter.GaussianBlur(1.2))   # 角のジャギを消す
icon = Image.composite(body, Image.new("RGB", (S, S), bg), mask)

icon.save("icon_1024.png")
for size in (180, 152, 120, 76, 60):
    icon.resize((size, size), Image.LANCZOS).save(f"icon_{size}.png")

print(f"icon_1024.png ほかを書き出した（地色 {bg} ・切り出し {side}px 四方）")
