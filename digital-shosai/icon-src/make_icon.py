#!/usr/bin/env python3
"""アプリアイコンを作る（1024×1024・角丸なし・アルファなし）。

    ../../agent-platform/.venv/bin/python make_icon.py

App Store のアイコンは**透明を含められない**ので、背景を必ず塗る。
角丸は iOS が自動で付けるため、こちらでは四角のまま出す。
図案: 開いた本＋そこから立ち上がる検索の光（本文を検索する道具、という意味）。
色はアプリ本体の画面と揃える（濃紺 #0f172a ／ 空色 #38bdf8）。
"""
from PIL import Image, ImageDraw

S = 1024
BG = (15, 23, 42)        # slate-900：本体画面と同じ濃紺
PAGE = (241, 245, 249)   # slate-100：紙
PAGE_SHADE = (203, 213, 225)
ACCENT = (56, 189, 248)  # sky-400：検索・アクセント
LINE = (100, 116, 139)   # slate-500：本文の行

img = Image.new("RGB", (S, S), BG)
d = ImageDraw.Draw(img)

# 開いた本（左右のページ）。中央でわずかに山を作る
# 余白を詰めて中央に大きく置く（iOSのアイコンは画面いっぱいに使うのが定石）
cx, top, bottom = S // 2, int(S * 0.34), int(S * 0.82)
left, right = int(S * 0.09), int(S * 0.91)
spine_lift = int(S * 0.045)

for sign, x_out in ((-1, left), (1, right)):
    d.polygon(
        [
            (cx, top + spine_lift),
            (x_out, top),
            (x_out, bottom - spine_lift),
            (cx, bottom),
        ],
        fill=PAGE if sign < 0 else PAGE_SHADE,
    )

# 本文の行（左ページに数本、右ページに数本）
for i in range(7):
    y = top + spine_lift + int(S * 0.055) * (i + 1)
    d.line([(left + int(S * 0.045), y + int(S * 0.012)), (cx - int(S * 0.03), y)], fill=LINE, width=9)
    d.line([(cx + int(S * 0.03), y), (right - int(S * 0.045), y + int(S * 0.012))], fill=LINE, width=9)

# 綴じ目
d.line([(cx, top + spine_lift), (cx, bottom)], fill=(148, 163, 184), width=7)

# 検索の光（虫めがね）を本の上に重ねる
r = int(S * 0.175)
gx, gy = int(S * 0.62), int(S * 0.36)
d.ellipse([gx - r, gy - r, gx + r, gy + r], outline=ACCENT, width=int(S * 0.035))
d.line(
    [(gx + int(r * 0.74), gy + int(r * 0.74)), (gx + int(r * 1.45), gy + int(r * 1.45))],
    fill=ACCENT,
    width=int(S * 0.045),
)
# 虫めがねの中だけ本文を透かす（ガラスの内側を少し明るくする）
d.ellipse([gx - r + 22, gy - r + 22, gx + r - 22, gy + r - 22], fill=(23, 37, 63))

img.save("icon_1024.png")

# iOS 用の各サイズ（Xcode は 1024 だけでも良いが、確認用に主要サイズも出す）
for size in (180, 152, 120, 76, 60):
    img.resize((size, size), Image.LANCZOS).save(f"icon_{size}.png")

print("icon_1024.png ほかを書き出した")
