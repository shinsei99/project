"""KeyTag のアイコン。

★アイコンは 60px で見られる。細部は全部消えるので、
  「離れた2つの塊」と「はっきりした余白」だけで意味を作る。

前の版の失敗（2026-08-18）
  * NFCの電波が鍵の上を横切って、何の絵か読めなくなっていた
  * 構図が左上に寄り、右下が大きく空いていた
  * 鍵の頭が大きすぎて「P」のように見えた
→ 鍵は中央やや左に垂直に立て、電波は右上に**離して**置く。重ねない。
"""
from PIL import Image, ImageDraw
import os

S = 1024
NAVY = (27, 35, 64)
ORANGE = (240, 124, 30)
WHITE = (255, 255, 255)

im = Image.new("RGB", (S, S), NAVY)      # 角丸はiOSが自動で付ける
d = ImageDraw.Draw(im)

# ── 鍵（中央やや左・垂直）──────────────────────────
# 頭は輪、軸はまっすぐ下へ、歯は右側に2つ。小さくしても鍵に見える形だけ残す
KX = 400                    # 鍵の中心x
head_cy, head_r = 330, 132  # 頭の中心yと半径
ring_w = 58                 # 輪の太さ
shaft_w = 62                # 軸の太さ

d.ellipse([KX - head_r, head_cy - head_r, KX + head_r, head_cy + head_r],
          outline=ORANGE, width=ring_w)
d.rounded_rectangle([KX - shaft_w // 2, head_cy + head_r - 18,
                     KX + shaft_w // 2, 800], radius=10, fill=ORANGE)
# 歯（右向き・2枚）。上の歯を長く、下を短くすると鍵らしく見える
d.rounded_rectangle([KX - shaft_w // 2, 610, KX + 116, 668], radius=8, fill=ORANGE)
d.rounded_rectangle([KX - shaft_w // 2, 712, KX + 82, 770], radius=8, fill=ORANGE)

# ── NFCの電波（右上・鍵とは重ねない）──────────────
# 中心を鍵の右外に置き、右上向きの扇形だけを描く
CX, CY = 470, 470
for i, rad in enumerate((250, 350, 450)):
    d.arc([CX - rad, CY - rad, CX + rad, CY + rad],
          start=-72, end=-14, fill=WHITE, width=54 - i * 6)

out = "ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-512@2x.png"
os.makedirs(os.path.dirname(out), exist_ok=True)
im.save(out)
im.resize((180, 180), Image.LANCZOS).save("icon-src/preview-180.png")
im.resize((120, 120), Image.LANCZOS).save("icon-src/preview-120.png")
im.resize((60, 60), Image.LANCZOS).save("icon-src/preview-60.png")

# 実際の見え方を1枚にまとめて確認できるようにする（濃紺だと分からないので明るい下地に置く）
sheet = Image.new("RGB", (760, 260), (232, 234, 240))
x = 40
for size in (180, 120, 60):
    ic = im.resize((size, size), Image.LANCZOS)
    sheet.paste(ic, (x, 40 + (180 - size) // 2))
    ImageDraw.Draw(sheet).text((x, 235), f"{size}px", fill=(90, 95, 110))
    x += size + 60
sheet.save("icon-src/preview-sizes.png")
print("✅ アイコンを作り直しました")
