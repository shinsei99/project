#!/usr/bin/env python3
"""チラシクリエーター（flyer-creator）アプリアイコン。
角丸スクエア単色背景＋白フラットグリフ（既存作法）。
グリフ＝チラシ（紙面）＋家＝物件チラシ生成。色は既存に無いアンバーで差別化。
出力: icon_1024.png → iconutil で AppIcon.icns。
"""
from PIL import Image, ImageDraw

SIZE = 1024
BG = (235, 140, 40, 255)     # amber
WHITE = (255, 255, 255, 255)
R = 230

img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=R, fill=BG)

# チラシ（白い紙面・縦長）
p_l, p_t, p_r, p_b = 300, 210, 724, 815
d.rounded_rectangle([p_l, p_t, p_r, p_b], radius=36, fill=WHITE)

# 上部に家アイコン（背景色）
hx, hy = (p_l + p_r) // 2, p_t + 170
roof_w, roof_h = 190, 110
# 屋根（三角）
d.polygon([(hx, hy - roof_h), (hx - roof_w, hy + 10), (hx + roof_w, hy + 10)], fill=BG)
# 家本体
d.rounded_rectangle([hx - 130, hy + 10, hx + 130, hy + 170], radius=14, fill=BG)
# ドア（白抜き）
d.rounded_rectangle([hx - 34, hy + 80, hx + 34, hy + 170], radius=10, fill=WHITE)

# 下部にテキスト行（背景色バー＝チラシの文章）
for i, y in enumerate([p_b - 220, p_b - 160, p_b - 100]):
    x2 = p_r - 60 if i < 2 else p_l + 190
    d.rounded_rectangle([p_l + 60, y, x2, y + 26], radius=13, fill=BG)

# 角丸マスク
mask = Image.new("L", (SIZE, SIZE), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=R, fill=255)
img.putalpha(mask)
img.save("icon_1024.png")
print("wrote icon_1024.png")
