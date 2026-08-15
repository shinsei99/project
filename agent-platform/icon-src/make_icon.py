#!/usr/bin/env python3
"""マルチプロダクション（agent-platform）アプリアイコン。
角丸スクエア単色背景＋白フラットグリフ（既存作法）。
グリフ＝重なるメディア層（紙面/スライド/動画）＋再生三角＝1入力から多メディアを生成。
色は既存に無いバイオレットで差別化。出力: icon_1024.png → iconutil で AppIcon.icns。
"""
from PIL import Image, ImageDraw

SIZE = 1024
BG = (124, 58, 196, 255)     # violet
WHITE = (255, 255, 255, 255)
R = 230

img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=R, fill=BG)

# 重なる3枚のカード（奥→手前にずらす）。多メディア生成の象徴。
cards = [(-70, 90), (0, 0), (70, -90)]  # (dx, dy) 奥から手前
w, h, rr = 440, 300, 46
cx, cy = SIZE // 2, SIZE // 2
for i, (dx, dy) in enumerate(cards):
    l, t = cx - w // 2 + dx, cy - h // 2 + dy
    # 白カード＋背景色の細縁で分離
    d.rounded_rectangle([l - 6, t - 6, l + w + 6, t + h + 6], radius=rr + 6, fill=BG)
    d.rounded_rectangle([l, t, l + w, t + h], radius=rr, fill=WHITE)

# 一番手前のカードに再生三角（動画・発信）
l, t = cx - w // 2 + 70, cy - h // 2 - 90
tri_cx, tri_cy, s = l + w // 2, t + h // 2, 70
d.polygon([(tri_cx - s + 12, tri_cy - s), (tri_cx - s + 12, tri_cy + s),
           (tri_cx + s + 18, tri_cy)], fill=BG)

# 角丸マスク
mask = Image.new("L", (SIZE, SIZE), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=R, fill=255)
img.putalpha(mask)
img.save("icon_1024.png")
print("wrote icon_1024.png")
