#!/usr/bin/env python3
"""AI業務マネージャー アプリアイコン生成。
Desktop/社内ツールの作法踏襲: 角丸スクエア単色背景 + 白フラットグリフ。
グリフ = チャット吹き出し＋ロボットの顔（＝Chatworkの中のAI社員）。
既存に無いインディゴで差別化。出力: icon_1024.png → iconutil で AppIcon.icns。
"""
import math

from PIL import Image, ImageDraw

SIZE = 1024
BG = (58, 74, 196, 255)          # indigo（AI）
WHITE = (255, 255, 255, 255)
R = 230                          # 角丸半径

img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# --- 背景（角丸スクエア） ---
d.rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=R, fill=BG)

# --- チャット吹き出し（白・角丸＋左下にしっぽ） ---
b_l, b_t, b_r, b_b = 190, 220, 834, 700
d.rounded_rectangle([b_l, b_t, b_r, b_b], radius=90, fill=WHITE)
# しっぽ（左下）
d.polygon([(300, b_b - 10), (300, b_b + 150), (440, b_b - 10)], fill=WHITE)

# --- ロボットの顔（吹き出し内・背景色でくり抜き） ---
cx = (b_l + b_r) // 2
cy = (b_t + b_b) // 2 - 5

# アンテナ
d.line([(cx, b_t + 70), (cx, b_t + 140)], fill=BG, width=26)
d.ellipse([cx - 34, b_t + 40, cx + 34, b_t + 108], fill=BG)

# 顔（角丸スクエア・背景色の枠）
f_w, f_h = 380, 300
f_l, f_t = cx - f_w // 2, cy - f_h // 2 + 30
d.rounded_rectangle([f_l, f_t, f_l + f_w, f_t + f_h], radius=70, outline=BG, width=30)

# 目（背景色の丸2つ）
eye_r = 42
ey = f_t + 110
for ex in (f_l + 110, f_l + f_w - 110):
    d.ellipse([ex - eye_r, ey - eye_r, ex + eye_r, ey + eye_r], fill=BG)

# 口（背景色の角丸バー）
m_l, m_r = f_l + 95, f_l + f_w - 95
m_y = f_t + f_h - 80
d.rounded_rectangle([m_l, m_y, m_r, m_y + 34], radius=17, fill=BG)

# 耳（左右・背景色の小丸）
for ex in (f_l - 8, f_l + f_w + 8):
    d.ellipse([ex - 20, cy + 10, ex + 20, cy + 90], fill=BG)

# --- 角丸の外にはみ出た分をマスク ---
mask = Image.new("L", (SIZE, SIZE), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=R, fill=255)
img.putalpha(mask)

img.save("icon_1024.png")
print("wrote icon_1024.png")
