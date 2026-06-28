#!/usr/bin/env python3
"""
make-icon.py
Mail Merge Pro のアプリアイコン(1024px)を生成する。
デザイン: 白の角丸スクエア背景に、青い「循環矢印（くるりと回る輪＋右向き矢印）」と封筒。
一斉送信／繰り返し送信のイメージ。
"""
from PIL import Image, ImageDraw
import math
import os

S = 1024
center = S / 2

# ---- 青のグラデーション素材（左上=明 → 右下=暗）----
blue_top = (40, 150, 255)
blue_bottom = (10, 95, 230)
blue = Image.new("RGBA", (S, S), (0, 0, 0, 0))
bd = ImageDraw.Draw(blue)
for y in range(S):
    t = y / S
    col = tuple(int(blue_top[i] + (blue_bottom[i] - blue_top[i]) * t) for i in range(3)) + (255,)
    bd.line([(0, y), (S, y)], fill=col)

# ---- 青で塗る形のマスク（白=塗る）----
mask = Image.new("L", (S, S), 0)
m = ImageDraw.Draw(mask)

# 循環の輪（太いリング・右下に開口部を残す）。
cx, cy = S * 0.49, S * 0.47
R = S * 0.33
thick = S * 0.052
# PIL の角度は3時方向=0°、時計回り。右下(開口)を避けて長い弧を描く。
start_ang, end_ang = 55, 310
m.arc([cx - R, cy - R, cx + R, cy + R], start=start_ang, end=end_ang,
      fill=255, width=int(thick))
# 矢印側(start_ang)の端だけ丸める。矢印で隠れる位置なので自然になじむ。
rad = math.radians(start_ang)
ex, ey = cx + R * math.cos(rad), cy + R * math.sin(rad)
r = thick / 2
m.ellipse([ex - r, ey - r, ex + r, ey + r], fill=255)

# 右向きの矢印（輪の右下から外へ）。
ax = cx + R * math.cos(math.radians(start_ang))
ay = cy + R * math.sin(math.radians(start_ang))
sh = S * 0.052   # シャフト半幅
hh = S * 0.105   # 矢じり半幅
shaft_len = S * 0.085
head_len = S * 0.12
arrow = [
    (ax - shaft_len, ay - sh),
    (ax, ay - sh),
    (ax, ay - hh),
    (ax + head_len, ay),
    (ax, ay + hh),
    (ax, ay + sh),
    (ax - shaft_len, ay + sh),
]
m.polygon(arrow, fill=255)

# 封筒（中央・角丸の長方形）。
ex0, ey0, ex1, ey1 = S * 0.25, S * 0.345, S * 0.73, S * 0.655
m.rounded_rectangle([ex0, ey0, ex1, ey1], radius=int(S * 0.035), fill=255)

# ---- 合成: 白背景に青を流し込む ----
bg = Image.new("RGBA", (S, S), (247, 247, 248, 255))
img = bg.copy()
img.paste(blue, (0, 0), mask)

# ---- 封筒のフラップ（白いV字）を上から描く ----
dr = ImageDraw.Draw(img)
pad = (ey1 - ey0) * 0.16
v_top = ey0 + pad
v_bottom = ey0 + (ey1 - ey0) * 0.58
lw = int(S * 0.028)
dr.line([(ex0 + pad, v_top), ((ex0 + ex1) / 2, v_bottom)], fill=(255, 255, 255, 255), width=lw)
dr.line([((ex0 + ex1) / 2, v_bottom), (ex1 - pad, v_top)], fill=(255, 255, 255, 255), width=lw)

# ---- 全体を角丸スクエアにクリップ ----
corner = Image.new("L", (S, S), 0)
ImageDraw.Draw(corner).rounded_rectangle([0, 0, S, S], radius=int(S * 0.225), fill=255)
out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
out.paste(img, (0, 0), corner)

# ---- iconset 書き出し ----
out_dir = os.path.join(os.path.dirname(__file__), "icon.iconset")
os.makedirs(out_dir, exist_ok=True)


def write(name, px):
    out.resize((px, px), Image.LANCZOS).save(os.path.join(out_dir, name))


for base in [16, 32, 128, 256, 512]:
    write(f"icon_{base}x{base}.png", base)
    write(f"icon_{base}x{base}@2x.png", base * 2)

# プレビュー用に 512 を別名でも保存。
out.resize((512, 512), Image.LANCZOS).save(os.path.join(os.path.dirname(__file__), "icon-preview.png"))
print("iconset written to", out_dir)
