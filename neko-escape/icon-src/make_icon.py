#!/usr/bin/env python3
"""にゃんこ大脱出のアプリアイコンと起動画面を作る。

なぜ自前で描くか:
  ゲーム本編（canvas の手描き）とアイコンの絵柄が違うと「別のアプリ」に見える。
  本編のネコと同じ配色（クリーム色の顔・キジトラのぶち・濃い輪郭）で顔を大きく描き、
  ホーム画面 → タイトル画面が地続きに見えるようにする。

守っていること（App Store の要件・過去の事故）:
  - **アルファチャンネルを持たせない**（透過があると審査で弾かれる）
  - **角丸を付けない**。iOS が自動で丸めるので、角まで地色で塗りつぶす
    （支給画像をそのまま使って角が白く欠けた事故が digital-shosai であった）
  - 小さく表示されても潰れないよう、要素を絞る（顔・耳・目・鼻・ひげだけ。体は描かない）
  - 輪郭は太く（1024pxで28px）。細いと 60px 表示でグレーの塊になる

使い方:
    python3 icon-src/make_icon.py            # 書き出して ios/ に差し込む
    python3 icon-src/make_icon.py --preview  # icon-src/ に置くだけ（差し込まない）
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "icon-src"
ICON_DEST = ROOT / "ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-512@2x.png"
SPLASH_DIR = ROOT / "ios/App/App/Assets.xcassets/Splash.imageset"

INK = (58, 46, 38)            # 本編の輪郭色
CREAM = (253, 243, 226)       # ネコの毛
TABBY = (232, 163, 61)        # キジトラのぶち
PINK = (240, 169, 160)        # 耳の内側
NOSE = (229, 138, 134)
BG_TOP = (246, 231, 200)      # 部屋のかべ（本編の地の色）
BG_BOT = (226, 202, 164)


def vgrad(size: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    """縦のグラデーション。1px幅で作って引き伸ばす（size回ループより速い）"""
    strip = Image.new("RGB", (1, size))
    d = ImageDraw.Draw(strip)
    for y in range(size):
        t = y / (size - 1)
        d.point((0, y), tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return strip.resize((size, size), Image.BILINEAR)


def draw_cat(d: ImageDraw.ImageDraw, cx: float, cy: float, s: float) -> None:
    """ネコの顔。s=1 のとき顔の幅がおよそ 560px。座標は本編の drawCat に合わせてある。"""
    def P(x, y):                      # ローカル座標 → 画像座標
        return (cx + x * s, cy + y * s)
    def ellipse(x, y, rx, ry, fill, width=0):
        d.ellipse([P(x - rx, y - ry), P(x + rx, y + ry)], fill=fill,
                  outline=INK if width else None, width=int(width * s))
    lw = 28                            # 輪郭の太さ（1024px 基準）

    # 耳（先に描いて頭で根元を隠す）
    for sx in (-1, 1):
        pts = [P(sx * 210, -150), P(sx * 268, -400), P(sx * 92, -300)]
        d.polygon(pts, fill=CREAM, outline=INK)
        d.line(pts + [pts[0]], fill=INK, width=int(lw * s), joint="curve")
        inner = [P(sx * 208, -178), P(sx * 240, -320), P(sx * 130, -262)]
        d.polygon(inner, fill=PINK)

    # 顔
    ellipse(0, 0, 300, 268, CREAM, lw)

    # キジトラのぶち（左上）。顔からはみ出さないよう、顔の形で切り抜いてから貼る
    patch = Image.new("RGB", (int(600 * s), int(536 * s)), CREAM)
    pd = ImageDraw.Draw(patch)
    pd.polygon([(int(70 * s), 0), (int(330 * s), int(40 * s)),
                (int(250 * s), int(230 * s)), (int(20 * s), int(150 * s))], fill=TABBY)
    mask = Image.new("L", patch.size, 0)
    ImageDraw.Draw(mask).ellipse([0, 0, patch.size[0] - 1, patch.size[1] - 1], fill=255)
    d._image.paste(patch, (int(cx - 300 * s), int(cy - 268 * s)), mask)
    ellipse(0, 0, 300, 268, None, lw)          # ぶちの上から輪郭を引き直す

    # 目（白いハイライト入り）
    for sx in (-1, 1):
        ellipse(sx * 108, -34, 46, 56, INK)
        ellipse(sx * 108 + 16, -54, 16, 16, (255, 255, 255))
    # 鼻と口
    d.polygon([P(-42, 60), P(42, 60), P(0, 108)], fill=NOSE)
    for sx in (-1, 1):
        d.arc([P(sx * 88 - 88, 96), P(sx * 88 + 88, 200)],
              200 if sx < 0 else 300, 340 if sx < 0 else 80, fill=INK, width=int(20 * s))
    # ひげ
    for sx in (-1, 1):
        for k, (y0, y1) in enumerate(((-20, -46), (40, 34))):
            d.line([P(sx * 280, y0), P(sx * 470, y1)], fill=INK, width=int(18 * s))


def build_icon(size: int = 1024) -> Image.Image:
    img = vgrad(size, BG_TOP, BG_BOT)
    d = ImageDraw.Draw(img)
    s = size / 1024
    draw_cat(d, size * 0.5, size * 0.54, s * 0.86)
    return img


def build_splash(size: int = 2732) -> Image.Image:
    img = vgrad(size, BG_TOP, BG_BOT)
    d = ImageDraw.Draw(img)
    # 起動画面はアイコンより小さめに置く（端末の縦横比で切られるため中央に寄せる）
    draw_cat(d, size * 0.5, size * 0.5, size / 1024 * 0.42)
    return img


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true", help="ios/ に差し込まない")
    args = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    icon = build_icon()
    icon_path = OUT / "icon_1024.png"
    icon.convert("RGB").save(icon_path)          # ★RGB＝アルファ無し
    splash = build_splash()
    splash_path = OUT / "splash_2732.png"
    splash.convert("RGB").save(splash_path)
    print("書き出した: %s / %s" % (icon_path.name, splash_path.name))

    if args.preview:
        print("--preview なので差し込みはしない")
        return
    ICON_DEST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(icon_path, ICON_DEST)
    for name in ("splash-2732x2732.png", "splash-2732x2732-1.png", "splash-2732x2732-2.png"):
        shutil.copy(splash_path, SPLASH_DIR / name)
    print("差し込んだ: %s と %s の3枚" % (ICON_DEST.relative_to(ROOT), SPLASH_DIR.relative_to(ROOT)))


if __name__ == "__main__":
    main()
