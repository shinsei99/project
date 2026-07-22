#!/usr/bin/env python3
"""スクラップメモ アプリアイコン試作 (1024x1024)。付箋を重ねた"ペタペタ"デザイン。"""
from PIL import Image, ImageDraw, ImageFilter
import math

S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

# ---- 背景（温かいクリーム色の縦グラデーション）----
bg = Image.new("RGBA", (S, S))
top = (253, 245, 224)   # #FDF5E0
bot = (244, 224, 190)   # #F4E0BE
for y in range(S):
    t = y / (S - 1)
    r = int(top[0] * (1 - t) + bot[0] * t)
    g = int(top[1] * (1 - t) + bot[1] * t)
    b = int(top[2] * (1 - t) + bot[2] * t)
    for x_layer in (bg,):
        pass
    ImageDraw.Draw(bg).line([(0, y), (S, y)], fill=(r, g, b, 255))
img.alpha_composite(bg)

def rounded(size, radius, color):
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, size[0]-1, size[1]-1], radius=radius, fill=color)
    return im

def paste_note(base, color, angle, cx, cy, w=440, h=440, lines=False, check=False):
    # 影
    shadow = Image.new("RGBA", (w+120, h+120), (0, 0, 0, 0))
    ds = ImageDraw.Draw(shadow)
    ds.rounded_rectangle([60, 70, 60+w, 70+h], radius=34, fill=(60, 45, 20, 120))
    shadow = shadow.filter(ImageFilter.GaussianBlur(22))
    shadow = shadow.rotate(angle, expand=True, resample=Image.BICUBIC)
    base.alpha_composite(shadow, (int(cx - shadow.width/2), int(cy - shadow.height/2 + 14)))

    # 付箋本体
    note = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dn = ImageDraw.Draw(note)
    dn.rounded_rectangle([0, 0, w-1, h-1], radius=30, fill=color)
    # 上部にわずかな濃いバンド（テープ感）
    top_band = tuple(max(0, c-25) for c in color[:3]) + (90,)
    dn.rounded_rectangle([0, 0, w-1, 46], radius=30, fill=top_band)
    dn.rectangle([0, 30, w-1, 46], fill=top_band)

    if lines:
        lc = (70, 60, 45, 210)
        widths = [0.72, 0.86, 0.55, 0.78]
        for i, wf in enumerate(widths):
            y = 130 + i * 62
            dn.rounded_rectangle([56, y, 56 + int((w-112)*wf), y+22], radius=11, fill=lc)
    if check:
        # TODO風レイアウト：チェックボックス＋横に行、下にさらに2行
        lc = (70, 60, 45, 205)
        rows = [(120, True), (196, False), (272, False)]
        for (y, done) in rows:
            bx = 52
            dn.rounded_rectangle([bx, y, bx+50, y+50], radius=12,
                                 outline=(70,60,45,225), width=8)
            if done:
                dn.line([(bx+11, y+27), (bx+21, y+39), (bx+42, y+9)],
                        fill=(40,150,90,255), width=12, joint="curve")
            lw = 0.62 if done else (0.74 if y == 196 else 0.5)
            dn.rounded_rectangle([bx+74, y+13, bx+74 + int((w-bx-110)*lw), y+37],
                                 radius=12, fill=lc)

    note = note.rotate(angle, expand=True, resample=Image.BICUBIC)
    base.alpha_composite(note, (int(cx - note.width/2), int(cy - note.height/2)))
    return (cx, cy, angle, w, h)

# 3枚重ね
paste_note(img, (255, 214, 92, 255),  -11, 430, 560, lines=True)   # 黄
paste_note(img, (255, 150, 168, 255),   9, 610, 545, lines=True)   # ピンク
top_info = paste_note(img, (128, 224, 196, 255), -3, 512, 512, check=True, lines=False)  # ミント(最前面)

# ---- 押しピン（最前面の付箋の上部中央）----
def pushpin(base, cx, cy):
    pin = Image.new("RGBA", (170, 170), (0,0,0,0))
    dp = ImageDraw.Draw(pin)
    dp.ellipse([35, 35, 135, 135], fill=(70, 50, 25, 90))  # 影
    pin = pin.filter(ImageFilter.GaussianBlur(8))
    dp = ImageDraw.Draw(pin)
    dp.ellipse([30, 30, 120, 120], fill=(230, 60, 70, 255))
    dp.ellipse([50, 48, 88, 82], fill=(255, 150, 155, 235))  # ハイライト
    base.alpha_composite(pin, (int(cx-85), int(cy-85)))

pushpin(img, 512, 322)

SCR = "/private/tmp/claude-501/-Users-apple/baf95b7c-287e-4860-b8bc-37f1b1c03db8/scratchpad"
img.save(SCR + "/scrapmemo_icon_v1.png")

# App Store 用：アルファ無しの不透明 RGB（1024x1024）
flat = Image.new("RGB", (S, S), (253, 245, 224))
flat.paste(img, (0, 0), img)
flat.save(SCR + "/scrapmemo_appicon_1024.png")

# プレビュー用に iOS 角丸マスクを当てた版も出力
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([0,0,S-1,S-1], radius=225, fill=255)
masked = img.copy()
masked.putalpha(mask)
masked.save("/private/tmp/claude-501/-Users-apple/baf95b7c-287e-4860-b8bc-37f1b1c03db8/scratchpad/scrapmemo_icon_v1_rounded.png")
print("saved")
