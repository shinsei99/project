"""KeyLine Tag のアイコン。KeyLine本体（濃紺×橙の鍵）と揃えつつ、
NFCの電波を足して「タグを読み書きするアプリ」だと分かるようにする。"""
from PIL import Image, ImageDraw
import os, math

S = 1024
im = Image.new("RGB", (S, S), (27, 35, 64))     # 濃紺（角丸はiOSが自動で付ける）
d = ImageDraw.Draw(im)
O = (240, 124, 30)

# 鍵（左下寄り）
cx, cy, r = 400, 300, 150
d.ellipse([cx-r, cy-r, cx+r, cy+r], outline=O, width=64)
d.rectangle([cx-34, cy+95, cx+34, cy+480], fill=O)
d.rectangle([cx-34, cy+250, cx+120, cy+308], fill=O)
d.rectangle([cx-34, cy+360, cx+90,  cy+418], fill=O)

# NFCの電波（右上へ広がる3本の弧）
for i, rad in enumerate((165, 260, 355)):
    box = [700 - rad, 640 - rad, 700 + rad, 640 + rad]
    d.arc(box, start=200, end=290, fill=(255, 255, 255), width=34 - i * 4)

os.makedirs("ios/App/App/Assets.xcassets/AppIcon.appiconset", exist_ok=True)
im.save("ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-512@2x.png")
im.resize((180, 180), Image.LANCZOS).save("icon-src/preview-180.png")
print("✅ アイコンを作成（1024x1024）")
