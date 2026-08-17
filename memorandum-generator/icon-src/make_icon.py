#!/usr/bin/env python3
"""覚書・合意書ジェネレーター アプリアイコン生成。
Desktop/社内ツールの既存アイコン踏襲: 角丸スクエア単色背景 + 白フラットグリフ。
グリフ = 書類（角折れ）＋ 署名ペン。既存に無いティール系で差別化。
出力: icon_1024.png → iconutil で AppIcon.icns。
"""
from PIL import Image, ImageDraw
import math

SIZE = 1024
BG = (23, 140, 122, 255)        # teal green
WHITE = (255, 255, 255, 255)
R = 230                          # 角丸半径

img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# --- 背景（角丸スクエア） ---
d.rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=R, fill=BG)


def rrect(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


# --- 書類（白・角折れ） ---
# シートは中央やや左上寄り。右下にペンを重ねる余白を確保。
doc_l, doc_t, doc_r, doc_b = 250, 210, 700, 815
fold = 130  # 右上の折れ寸法

# 折れ角を除いた書類の輪郭（多角形）
doc_poly = [
    (doc_l, doc_t),
    (doc_r - fold, doc_t),
    (doc_r, doc_t + fold),
    (doc_r, doc_b),
    (doc_l, doc_b),
]
# 角丸っぽさは corner を少し丸めるため、まず多角形→後で角を丸めるのは複雑なので
# 素直に多角形で描画（既存アイコンも直線的）
d.polygon(doc_poly, fill=WHITE)
# 左右上下の角を軽く丸める（左上・左下・右下）ため小円で補正は省略。

# 折れ部分の陰（背景色の三角）で「めくれ」を表現
d.polygon([(doc_r - fold, doc_t), (doc_r - fold, doc_t + fold), (doc_r, doc_t + fold)], fill=BG)

# --- 本文行（背景色バー） ---
line_x1, line_x2 = doc_l + 55, doc_r - 55
ys = [doc_t + 220, doc_t + 300, doc_t + 380]
for i, y in enumerate(ys):
    x2 = line_x2 if i < len(ys) - 1 else doc_l + 250
    rrect(d, [line_x1, y, x2, y + 30], radius=15, fill=BG)

# --- 署名の波線（合意/覚書の要） ---
sig_y = doc_b - 120
pts = []
for t in range(0, 101):
    x = line_x1 + (line_x2 - line_x1 - 40) * t / 100
    y = sig_y + 34 * math.sin(t / 100 * math.pi * 3)
    pts.append((x, y))
d.line(pts, fill=BG, width=22, joint="curve")

# --- 署名ペン（白・右下から斜め。書類と重なる部分は背景色の隙間で分離） ---
# ペン本体を斜め45度の角丸長方形として描き、先端に三角ニブ。
pen = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
pd = ImageDraw.Draw(pen)
pen_w = 110
pen_len = 560
# ペンを水平に描いてから回転
px1, py1 = 0, (SIZE - pen_w) // 2
rrect(pd, [px1 + 120, py1, px1 + 120 + pen_len, py1 + pen_w], radius=40, fill=WHITE)
# ニブ（左先端の三角）
nib = 120
d_tip_y = py1 + pen_w // 2
pd.polygon([(px1 + 120, py1), (px1 + 120, py1 + pen_w), (px1, d_tip_y)], fill=WHITE)
# ニブ中央のスリット
pd.line([(px1 + 30, d_tip_y), (px1 + 150, d_tip_y)], fill=BG, width=14)
# グリップ帯
rrect(pd, [px1 + 120 + pen_len - 150, py1 + 10, px1 + 120 + pen_len - 110, py1 + pen_w - 10], radius=20, fill=BG)

pen = pen.rotate(-38, resample=Image.BICUBIC, center=(SIZE // 2, SIZE // 2))
# ペンを右下に配置するためオフセット
pen = pen.transform(
    (SIZE, SIZE), Image.AFFINE, (1, 0, -190, 0, 1, 250), resample=Image.BICUBIC
)

# 書類と分離する隙間: ペンのアルファを太らせた背景色マスクを先に敷く
from PIL import ImageFilter
gap = pen.split()[3].filter(ImageFilter.MaxFilter(31))
gap_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
gap_layer.putalpha(gap)
gap_rgb = Image.new("RGBA", (SIZE, SIZE), BG)
gap_rgb.putalpha(gap)
img.alpha_composite(gap_rgb)
img.alpha_composite(pen)

# 角丸の外にはみ出た分をマスク
mask = Image.new("L", (SIZE, SIZE), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=R, fill=255)
img.putalpha(mask)

img.save("icon_1024.png")
print("wrote icon_1024.png")
