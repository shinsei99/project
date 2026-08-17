#!/usr/bin/env python3
"""不動産写真AI（photo-inpainter）アプリアイコン生成。

Desktop/社内ツールの既存アイコン踏襲: 角丸スクエア単色背景 + 白フラットグリフ。
グリフ = 写真（山と太陽）＋ 消した跡のキラッ（AI消去を表す）。
既存に無いバイオレット系で差別化する。

出力:
  icon_1024.png … 元画像
  AppIcon.icns  … Desktop/社内ツール の .app 用（iconutil で生成）
  不動産写真AI.ico … Dropbox共有フォルダ（Windows）の .url 用

使い方: python3 make_icon.py
"""
from PIL import Image, ImageDraw
import os
import subprocess

SIZE = 1024
BG = (109, 74, 196, 255)      # violet（既存の緑・青・橙・ティールと重ならない色）
WHITE = (255, 255, 255, 255)
R = 230                        # 角丸半径

HERE = os.path.dirname(os.path.abspath(__file__))

img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# --- 背景（角丸スクエア） ---
d.rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=R, fill=BG)

# --- 写真フレーム（白の角丸） ---
fx1, fy1, fx2, fy2 = 190, 250, 834, 730
d.rounded_rectangle([fx1, fy1, fx2, fy2], radius=48, fill=WHITE)

# 枠の内側をBGでくり抜き、写真の「中身」を描く土台にする
ix1, iy1, ix2, iy2 = fx1 + 42, fy1 + 42, fx2 - 42, fy2 - 42
d.rounded_rectangle([ix1, iy1, ix2, iy2], radius=22, fill=BG)

# --- 写真の中身: 太陽 ---
d.ellipse([ix1 + 62, iy1 + 58, ix1 + 172, iy1 + 168], fill=WHITE)

# --- 写真の中身: 山（奥・手前の2つ） ---
d.polygon([(ix1 + 40, iy2 - 30), (ix1 + 250, iy1 + 180), (ix1 + 430, iy2 - 30)], fill=WHITE)
d.polygon([(ix1 + 250, iy2 - 30), (ix1 + 410, iy1 + 245), (ix2 - 40, iy2 - 30)], fill=WHITE)

# --- 消した跡のキラッ（4方向の光条）×3 ---
def sparkle(cx, cy, r, w):
    """中心から上下左右へ伸びる四芒星。AIで消した跡の「きれいになった」表現。"""
    d.polygon([(cx, cy - r), (cx + w, cy), (cx, cy + r), (cx - w, cy)], fill=WHITE)
    d.polygon([(cx - r, cy), (cx, cy - w), (cx + r, cy), (cx, cy + w)], fill=WHITE)


sparkle(742, 762, 118, 30)   # 右下の大きいもの（写真フレームに重ねる）
sparkle(872, 640, 62, 16)
sparkle(636, 872, 54, 14)

png = os.path.join(HERE, "icon_1024.png")
img.save(png)
print("wrote", png)

# --- .icns（macOS） ---
iconset = os.path.join(HERE, "AppIcon.iconset")
os.makedirs(iconset, exist_ok=True)
for px in (16, 32, 64, 128, 256, 512, 1024):
    img.resize((px, px), Image.LANCZOS).save(os.path.join(iconset, f"icon_{px}x{px}.png"))
    # Retina 用（@2x）は半分のサイズの名前で同じ画像を置く
    if px >= 32:
        img.resize((px, px), Image.LANCZOS).save(
            os.path.join(iconset, f"icon_{px // 2}x{px // 2}@2x.png"))
subprocess.run(["iconutil", "-c", "icns", iconset,
                "-o", os.path.join(HERE, "AppIcon.icns")], check=True)
print("wrote", os.path.join(HERE, "AppIcon.icns"))

# --- .ico（Windows・Dropbox共有フォルダの .url 用） ---
ico = os.path.join(HERE, "不動産写真AI.ico")
img.save(ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("wrote", ico)
