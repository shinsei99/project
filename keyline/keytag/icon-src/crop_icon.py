"""アイコン画像から、アイコン本体だけを切り出して規定サイズにする。

★アイコンの元絵は画像生成で作ったものを利用者から受け取っている。
  再生成が必要になったら、同じ構図（濃紺の角丸・橙の鍵・白いNFC電波・
  青〜橙のリング）で作り直し、このスクリプトに通すこと。

★iOSは1024×1024の**角を丸めていない正方形**を要求し、角丸は自分でかける。
  実測（2026-08-18）: iOSが切る位置は角から約66px、元絵に描かれた角丸の縁は
  約70px。差は4pxで目視では分からない。四隅を「絵の続き」で埋めてあるので、
  マスクが多少ズレても暗い三角形は出ない。

元画像は 1024×1024 の中に、角丸四角のアイコンが**余白付きで**置かれている。
そのまま使うと iOS がさらに角丸で切るため、絵が小さくなり四隅に余計な背景が残る。

やること
  1. 明るさの段差からアイコン本体の四角を見つけて切り出す
  2. 角丸の外側（元の背景）を、アイコン自身の地色で塗り潰す
     → iOS の角丸マスクとズレても、暗い縁が出ない
  3. 1024×1024（App Store 提出の規定サイズ）にする
  4. **アルファチャンネルを持たせない**（App Store は透過を弾く）
"""
from PIL import Image, ImageDraw
import numpy as np
import os

SRC = "/Users/apple/Library/CloudStorage/Dropbox-個人/カメラアップロード/2026-08-18 10.17.57.png"
OUT_SIZE = 1024

im = Image.open(SRC).convert("RGB")
a = np.asarray(im).astype(int)
lum = a.sum(axis=2)


def span(profile):
    """外側の暗い背景とアイコンの段差から、端の位置を返す。"""
    base = np.median(np.r_[profile[:60], profile[-60:]])
    peak = np.median(profile[len(profile) // 2 - 100:len(profile) // 2 + 100])
    idx = np.where(profile > base + (peak - base) * 0.35)[0]
    return int(idx.min()), int(idx.max())


# 横は中央行が安定している。縦は絵の下側が地色に近く段差が出ないため、
# 「正方形である」ことを使って横幅から決める（アイコンは必ず正方形）
x0, x1 = span(lum[im.height // 2, :])
size = x1 - x0 + 1
y0, _ = span(lum[:, 300])          # 上端だけは左寄りの列で安定して取れる
y1 = y0 + size - 1
print(f"切り出し: ({x0}, {y0}) から {size}×{size}")

crop = im.crop((x0, y0, x0 + size, y0 + size))

# 角丸の外側（元の背景）をどう埋めるか。
#
# ★ここを単色で塗ると縁が浮く（最初にやって失敗した）。
#   アイコンは中央が明るく端が暗いグラデーションなので、
#   内側から拾った色は角には明るすぎる。
# → 切り出した絵そのものを少し拡大して下敷きにする。
#   角には「その位置の絵の続き」が来るので、境目が出ない。
c = np.asarray(crop).astype(int)
grow = int(size * 1.18)
canvas = crop.resize((grow, grow), Image.LANCZOS).crop(
    ((grow - size) // 2, (grow - size) // 2,
     (grow - size) // 2 + size, (grow - size) // 2 + size))

mask = Image.new("L", (size, size), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1],
                                       radius=int(size * 0.225), fill=255)
canvas.paste(crop, (0, 0), mask)

edge = np.vstack([c[0:24, size // 3:size * 2 // 3].reshape(-1, 3),
                  c[size // 3:size * 2 // 3, 0:24].reshape(-1, 3)])
print("端の色（参考）:", tuple(np.median(edge, axis=0).astype(int)))

icon = canvas.resize((OUT_SIZE, OUT_SIZE), Image.LANCZOS)

out = "ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-512@2x.png"
os.makedirs(os.path.dirname(out), exist_ok=True)
icon.save(out, "PNG")                      # RGB のまま＝アルファ無し
print(f"✅ {out}  {icon.size}  mode={icon.mode}")

# 実際の見え方を確かめる（アイコンは60pxでも読めないと意味がない）
os.makedirs("icon-src", exist_ok=True)
for s in (180, 120, 60):
    icon.resize((s, s), Image.LANCZOS).save(f"icon-src/preview-{s}.png")

sheet = Image.new("RGB", (760, 270), (232, 234, 240))
d = ImageDraw.Draw(sheet)
x = 40
for s in (180, 120, 60):
    r = icon.resize((s, s), Image.LANCZOS)
    m = Image.new("L", (s, s), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.225), fill=255)
    sheet.paste(r, (x, 45 + (180 - s) // 2), m)      # iOSの角丸を再現して確認する
    d.text((x, 240), f"{s}px", fill=(90, 95, 110))
    x += s + 60
sheet.save("icon-src/preview-sizes.png")
print("✅ icon-src/preview-sizes.png（iOSの角丸を当てた状態）")
