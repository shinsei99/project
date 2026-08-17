#!/usr/bin/env python3
"""事業計画案ジェネレーター（business-plan-generator）アプリアイコン生成。

Desktop/社内ツールの既存アイコン踏襲: 角丸スクエア単色背景 + 白フラットグリフ。
グリフ = 右肩上がりの棒グラフ＋伸びる矢印（投資収支・キャッシュフローを表す）。
既存に無いディープブルー系で差別化する。

出力:
  icon_1024.png … 元画像
  AppIcon.icns  … Desktop/社内ツール の .app 用（iconutil で生成）
  事業計画案ジェネレーター.ico … Dropbox共有フォルダ（Windows）の .url 用

使い方: python3 make_icon.py
"""
from PIL import Image, ImageDraw
import os
import subprocess

SIZE = 1024
BG = (18, 74, 132, 255)       # deep blue（violet/teal/緑/橙とは別系統）
WHITE = (255, 255, 255, 255)
R = 230                        # 角丸半径

HERE = os.path.dirname(os.path.abspath(__file__))

img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# --- 背景（角丸スクエア） ---
d.rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=R, fill=BG)

# --- 棒グラフ（3本・右肩上がり） ---
base_y = 780
bars = [(230, 560), (430, 470), (630, 380)]   # (左x, 上y)
bar_w = 150
for x, top in bars:
    d.rounded_rectangle([x, top, x + bar_w, base_y], radius=26, fill=WHITE)

# --- 台座（横軸） ---
d.rounded_rectangle([200, base_y + 20, 824, base_y + 66], radius=23, fill=WHITE)

# --- 伸びる矢印（左下から右上へ） ---
d.line([(250, 470), (430, 370), (620, 300), (790, 215)], fill=WHITE, width=42, joint="curve")
# 矢じり（右上）。中を抜くと小サイズで潰れて見えるため、塗りつぶしの三角にする
d.polygon([(672, 168), (840, 168), (840, 336)], fill=WHITE)

png = os.path.join(HERE, "icon_1024.png")
img.save(png)
print("wrote", png)

# --- .icns（macOS） ---
iconset = os.path.join(HERE, "AppIcon.iconset")
os.makedirs(iconset, exist_ok=True)
for px in (16, 32, 64, 128, 256, 512, 1024):
    img.resize((px, px), Image.LANCZOS).save(os.path.join(iconset, f"icon_{px}x{px}.png"))
    if px >= 32:
        img.resize((px, px), Image.LANCZOS).save(
            os.path.join(iconset, f"icon_{px // 2}x{px // 2}@2x.png"))
subprocess.run(["iconutil", "-c", "icns", iconset,
                "-o", os.path.join(HERE, "AppIcon.icns")], check=True)
print("wrote", os.path.join(HERE, "AppIcon.icns"))

# --- .ico（Windows・Dropbox共有フォルダの .url 用） ---
ico = os.path.join(HERE, "事業計画案ジェネレーター.ico")
img.save(ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("wrote", ico)
