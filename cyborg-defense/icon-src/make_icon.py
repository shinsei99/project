#!/usr/bin/env python3
"""サイボーグ防衛軍のアプリアイコンと起動画面を作る。

なぜ自前で描くか:
  ゲーム本編が canvas の手描きベクターなので、アイコンだけ別の絵柄にすると
  「別のアプリ」に見える。**本編の兵士と同じ色（金属＋シアンのバイザー）**で
  サイボーグの顔を大きく描き、ホーム画面と本編がつながって見えるようにする。

守っていること（App Store の要件・過去の事故）:
  - **アルファチャンネルを持たせない**（透過があると審査で弾かれる）
  - 角丸は付けない。**iOS が自動で角を丸める**ので、角まで地色で塗りつぶす
  - 小さく表示されても潰れないよう、要素は3つに絞る（金属の頭・光るバイザー・赤い義眼）

★ネオンの光は必ず「加算」で足すこと。
  `Image.blend(img, 黒い光レイヤ, 0.9)` と書くと、光を足すどころか**画像が黒く潰れる**
  （blend は黒への線形補間）。実際に一度それで全面真っ黒のアイコンを作った。
  光は `ImageChops.add`、実体は `ImageDraw` で直接描くか `paste(..., mask)` で置く。

使い方:
    python3 icon-src/make_icon.py           # アイコンと起動画面を書き出して差し込む
    python3 icon-src/make_icon.py --preview # icon-src/ に置くだけ（差し込まない）
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "icon-src"
ICON_DEST = ROOT / "ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-512@2x.png"
SPLASH_DIR = ROOT / "ios/App/App/Assets.xcassets/Splash.imageset"

CYAN = (65, 227, 255)
MINT = (125, 255, 208)
RED = (255, 77, 94)
DARK = (11, 34, 45)
SEAM = (26, 44, 58)


def vgrad(size: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    """縦のグラデーション。1px幅で作ってから引き伸ばす（size回のループより速い）"""
    strip = Image.new("RGB", (1, size))
    d = ImageDraw.Draw(strip)
    for y in range(size):
        t = y / (size - 1)
        d.point((0, y), tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return strip.resize((size, size), Image.BILINEAR)


def add_light(img: Image.Image, layer: Image.Image, radius: int, strength: float = 1.0) -> Image.Image:
    """光レイヤをぼかして**加算**する（ネオンのにじみ）"""
    blur = layer.filter(ImageFilter.GaussianBlur(radius))
    if strength != 1.0:
        blur = blur.point(lambda v: int(v * strength))
    return ImageChops.add(img, blur)


def build_icon(S: int = 1024) -> Image.Image:
    """サイボーグの顔をひとつ大きく置く。

    左右を非対称（右目だけ機械の赤い義眼）にすると、ロボットではなく
    **サイボーグ**（半分は人間）に見える。
    """
    img = vgrad(S, (16, 10, 42), (5, 4, 16))

    # 奥のグリッド（本編の床と同じ雰囲気）。薄く加算する
    grid = Image.new("RGB", (S, S), (0, 0, 0))
    gd = ImageDraw.Draw(grid)
    step = S // 13
    for i in range(0, S + step, step):
        gd.line([(i, 0), (i, S)], fill=(5, 17, 23), width=2)
        gd.line([(0, i), (S, i)], fill=(5, 17, 23), width=2)
    img = ImageChops.add(img, grid)

    # 頭の後ろの光（輪郭を浮かせる）
    halo = Image.new("RGB", (S, S), (0, 0, 0))
    ImageDraw.Draw(halo).ellipse([S * 0.18, S * 0.16, S * 0.82, S * 0.94], fill=(16, 78, 104))
    img = add_light(img, halo, S // 9)

    cx = S / 2
    top, bot = S * 0.13, S * 0.86
    hw = S * 0.325                      # 頭の半分の幅

    # ケーブルは**頭より先に**描く（後から描くと顔の上を横切ってしまう）
    d0 = ImageDraw.Draw(img)
    for k in (-1, 1):
        d0.line([(cx + k * hw * 0.80, top + S * 0.30),
                 (cx + k * (hw + S * 0.075), top + S * 0.52),
                 (cx + k * hw * 0.62, bot + S * 0.01)],
                fill=(38, 62, 80), width=int(S * 0.030), joint="curve")

    # --- 頭（金属）。上が明るいグラデにすると板ではなく立体に見える ---
    metal = vgrad(S, (208, 234, 246), (52, 86, 106))
    shape = Image.new("L", (S, S), 0)
    sd = ImageDraw.Draw(shape)
    sd.rounded_rectangle([cx - hw, top, cx + hw, bot - S * 0.10], radius=int(S * 0.20), fill=255)
    sd.polygon([(cx - hw * 0.72, bot - S * 0.22), (cx + hw * 0.72, bot - S * 0.22),
                (cx + hw * 0.42, bot), (cx - hw * 0.42, bot)], fill=255)      # あご
    img.paste(metal, (0, 0), shape)

    d = ImageDraw.Draw(img)
    # 兜の稜線（真ん中の峰と、両肩へ落ちる面の切り替え線）
    d.polygon([(cx - S * 0.022, top + S * 0.150), (cx, top + S * 0.030),
               (cx + S * 0.022, top + S * 0.150)], fill=(226, 242, 250))
    for k in (-1, 1):
        d.line([(cx + k * S * 0.030, top + S * 0.145), (cx + k * hw * 0.92, top + S * 0.115)],
               fill=SEAM, width=int(S * 0.007))

    # --- 面（フェイスプレート）。暗くしてバイザーを目立たせる ---
    d.rounded_rectangle([cx - hw * 0.93, top + S * 0.185, cx + hw * 0.93, bot - S * 0.235],
                        radius=int(S * 0.055), fill=DARK)
    # 頬の装甲の継ぎ目
    d.line([(cx - hw * 0.93, top + S * 0.42), (cx + hw * 0.93, top + S * 0.42)],
           fill=(20, 54, 68), width=int(S * 0.006))

    # --- バイザー（光る帯） ---
    vy0, vy1 = top + S * 0.255, top + S * 0.335
    d.rounded_rectangle([cx - hw * 0.84, vy0, cx + hw * 0.84, vy1], radius=int(S * 0.022), fill=CYAN)
    visor = Image.new("RGB", (S, S), (0, 0, 0))
    ImageDraw.Draw(visor).rounded_rectangle([cx - hw * 0.84, vy0, cx + hw * 0.84, vy1],
                                            radius=int(S * 0.022), fill=CYAN)
    img = add_light(img, visor, int(S * 0.028), 0.85)
    d = ImageDraw.Draw(img)
    # バイザーの中の走査線（ただの帯だと機械に見えない）
    for i in range(1, 4):
        yy = vy0 + (vy1 - vy0) * i / 4
        d.line([(cx - hw * 0.80, yy), (cx + hw * 0.80, yy)], fill=(20, 120, 150), width=2)

    # --- 右目だけ機械の赤い義眼（左右非対称＝サイボーグ） ---
    ex, ey, er = cx + hw * 0.47, (vy0 + vy1) / 2, S * 0.052
    d.ellipse([ex - er * 1.45, ey - er * 1.45, ex + er * 1.45, ey + er * 1.45], fill=(18, 22, 30))
    d.ellipse([ex - er, ey - er, ex + er, ey + er], fill=RED)
    eye = Image.new("RGB", (S, S), (0, 0, 0))
    ImageDraw.Draw(eye).ellipse([ex - er, ey - er, ex + er, ey + er], fill=RED)
    img = add_light(img, eye, int(S * 0.022), 0.9)
    d = ImageDraw.Draw(img)
    d.ellipse([ex - er * 0.40, ey - er * 0.50, ex + er * 0.06, ey - er * 0.04], fill=(255, 225, 230))

    # --- 口元の排気スリット ---
    for i in range(3):
        y = bot - S * 0.30 + i * S * 0.036
        d.rounded_rectangle([cx - hw * 0.36, y, cx + hw * 0.36, y + S * 0.019],
                            radius=int(S * 0.009), fill=(24, 40, 52))

    # --- 側頭のユニットとケーブル ---
    # ★PIL の rounded_rectangle / arc は x0<x1 でないと落ちる。左右対称に描くときは
    #   計算してから min/max で並べ替えること（左側で x が逆転して1度落とした）
    for k in (-1, 1):
        xa, xb = cx + k * (hw + S * 0.035), cx + k * (hw - S * 0.055)
        d.rounded_rectangle([min(xa, xb), top + S * 0.285, max(xa, xb), top + S * 0.285 + S * 0.155],
                            radius=int(S * 0.022), fill=SEAM)
        lx = cx + k * (hw - S * 0.010)
        d.ellipse([lx - S * 0.015, top + S * 0.345, lx + S * 0.015, top + S * 0.375], fill=MINT)

    # 側頭ユニットのランプも光らせる
    lamps = Image.new("RGB", (S, S), (0, 0, 0))
    ld = ImageDraw.Draw(lamps)
    for k in (-1, 1):
        lx = cx + k * (hw - S * 0.010)
        ld.ellipse([lx - S * 0.015, top + S * 0.345, lx + S * 0.015, top + S * 0.375], fill=MINT)
    img = add_light(img, lamps, int(S * 0.02), 0.8)

    # 左の縁光（背景から浮かせる）
    rim = Image.new("RGB", (S, S), (0, 0, 0))
    rimmask = shape.filter(ImageFilter.GaussianBlur(int(S * 0.006)))
    rimlayer = Image.new("RGB", (S, S), (18, 70, 92))
    rim.paste(rimlayer, (-int(S * 0.012), 0), rimmask)
    rim = ImageChops.subtract(rim, Image.merge("RGB", (shape, shape, shape)))
    img = add_light(img, rim, int(S * 0.010), 0.9)
    d = ImageDraw.Draw(img)

    # --- 首の下の迎撃ライン（守っている線。本編の防衛ラインと同じ赤） ---
    d = ImageDraw.Draw(img)
    ly = bot + S * 0.035
    d.rectangle([S * 0.15, ly, S * 0.85, ly + S * 0.016], fill=RED)
    bar = Image.new("RGB", (S, S), (0, 0, 0))
    ImageDraw.Draw(bar).rectangle([S * 0.15, ly, S * 0.85, ly + S * 0.016], fill=RED)
    img = add_light(img, bar, int(S * 0.016), 0.75)

    return img.convert("RGB")           # ★アルファを持たせない


def build_splash(S: int = 2732) -> Image.Image:
    """起動画面。アイコンと同じ顔を中央に小さく置くだけ（読み込みは一瞬なので凝らない）"""
    img = vgrad(S, (16, 10, 42), (4, 3, 12))
    mark = build_icon(1024).resize((int(S * 0.30), int(S * 0.30)), Image.LANCZOS)
    # 四角い地が見えないよう、丸くぼかしたマスクで抜く
    mask = Image.new("L", mark.size, 0)
    ImageDraw.Draw(mask).ellipse([0, 0, mark.size[0], mark.size[1]], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(mark.size[0] // 10))
    img.paste(mark, (int(S * 0.35), int(S * 0.35)), mask)
    return img.convert("RGB")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true", help="差し込まず icon-src/ に置くだけ")
    args = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    icon = build_icon()
    icon_path = OUT / "icon_1024.png"
    icon.save(icon_path)
    splash = build_splash()
    splash_path = OUT / "splash_2732.png"
    splash.save(splash_path)
    print("書き出した: %s / %s" % (icon_path.name, splash_path.name))

    if args.preview:
        return
    shutil.copy(icon_path, ICON_DEST)
    for name in ("splash-2732x2732.png", "splash-2732x2732-1.png", "splash-2732x2732-2.png"):
        shutil.copy(splash_path, SPLASH_DIR / name)
    print("差し込んだ: %s / %s" % (ICON_DEST.relative_to(ROOT), SPLASH_DIR.relative_to(ROOT)))


if __name__ == "__main__":
    main()
