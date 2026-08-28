#!/usr/bin/env python3
"""カラー・グラビティのアプリアイコン（1024×1024）を描く。

なぜコードで描くか:
  ゲーム本体が Canvas で全部描いている（画像ファイルを1枚も使っていない）ので、
  アイコンも同じ考えで持つ。あとから色や配置を直すのが差分で分かる。

★ App Store のアイコンは **アルファチャンネルを持てない**（透明があると弾かれる）。
  ここでは RGB（アルファ無し）で書き出している。角丸も付けない（iOS が自動でマスクする）。

書き出し先:
  ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-512@2x.png   ← 実際に使われる1枚
  icon-1024.png                                                        ← 手元確認用の控え

使い方:
    python3 tools/make-icon.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
DESTS = [
    ROOT / "ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-512@2x.png",
    ROOT / "icon-1024.png",
]

S = 1024
SS = 4                      # 4倍で描いて縮小する（円と細線のギザギザを消すため）
N = S * SS

CYAN = (125, 249, 255)
RED = (255, 59, 92)
BLUE = (59, 139, 255)
YELLOW = (255, 225, 77)


def radial(img: Image.Image, cx: float, cy: float, r: float, inner, outer, steps: int = 120) -> None:
    """中心から外へ向かうグラデーション。PIL には無いので同心円を重ねて作る。"""
    d = ImageDraw.Draw(img)
    for i in range(steps, 0, -1):
        t = i / steps
        col = tuple(int(inner[k] + (outer[k] - inner[k]) * t) for k in range(3))
        rr = r * t
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=col)


def glow_ring(size: int, cx: float, cy: float, r: float, w: int, col, blur: int):
    """光る輪。別レイヤーに描いてぼかし、加算合成で乗せる。"""
    lay = Image.new("RGB", (size, size), (0, 0, 0))
    ImageDraw.Draw(lay).ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=w)
    return lay.filter(ImageFilter.GaussianBlur(blur))


def _add_arrays(a: Image.Image, b: Image.Image) -> Image.Image:
    """加算合成（光を重ねる）。PIL の ImageChops.add が同じことをするので numpy は使わない。"""
    from PIL import ImageChops
    return ImageChops.add(a, b)


def sphere(cx, cy, r, base, light=(255, 250, 252), dark=(22, 6, 20)):
    """球。**別レイヤーに描いて円のマスクで貼る**。
    直接キャンバスへ同心円を描くと、はみ出したグラデーションが背景に広がって
    「もう1つ大きな星がある」ように見えてしまう（最初これをやって失敗した）。"""
    lay = Image.new("RGB", (N, N), (0, 0, 0))
    d = ImageDraw.Draw(lay)
    hx, hy = cx - r * 0.34, cy - r * 0.36          # 光源は左上
    steps = 160
    for i in range(steps, 0, -1):
        t = i / steps                                # 1=外側（暗い）→ 0=中心（明るい）
        if t > 0.62:
            k = (t - 0.62) / 0.38
            col = tuple(int(base[j] + (dark[j] - base[j]) * k) for j in range(3))
        else:
            k = 1 - t / 0.62
            col = tuple(int(base[j] + (light[j] - base[j]) * (k ** 1.6)) for j in range(3))
        rr = r * 1.62 * t
        d.ellipse([hx - rr, hy - rr, hx + rr, hy + rr], fill=col)
    # 縞（ガス惑星の帯）
    for i in range(5):
        yy = cy - r + (i + 0.5) * r * 2 / 5
        band = Image.new("RGB", (N, N), (0, 0, 0))
        ImageDraw.Draw(band).ellipse(
            [cx - r * 1.15, yy - r * 0.15, cx + r * 1.15, yy + r * 0.15],
            fill=(0, 0, 0) if i % 2 else (255, 190, 200))
        lay = Image.blend(lay, band, 0.13 if i % 2 else 0.09)
    mask = Image.new("L", (N, N), 0)
    ImageDraw.Draw(mask).ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    return lay, mask


def main() -> None:
    img = Image.new("RGB", (N, N), (8, 5, 24))

    # 星雲。ぼかした楕円を弱く足すだけ（背景に色の気配だけ残す）
    for cx, cy, rx, ry, col in [
        (N * 0.24, N * 0.22, N * 0.34, N * 0.28, (46, 22, 86)),
        (N * 0.82, N * 0.78, N * 0.30, N * 0.26, (18, 40, 84)),
    ]:
        neb = Image.new("RGB", (N, N), (0, 0, 0))
        ImageDraw.Draw(neb).ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=col)
        img = _add_arrays(img, neb.filter(ImageFilter.GaussianBlur(N * 0.06)))

    d = ImageDraw.Draw(img)

    # 星屑。決め打ちの座標（乱数を使うと流すたびにアイコンが変わって差分が読めない）
    for i in range(80):
        a = i * 2.399963                       # 黄金角。等間隔に散る
        rr = (i / 80) ** 0.5 * N * 0.50
        x, y = N / 2 + math.cos(a) * rr, N / 2 + math.sin(a) * rr
        s = N * (0.0016 + 0.0024 * ((i * 7) % 5) / 5)
        v = 130 + (i * 37) % 110
        d.ellipse([x - s, y - s, x + s, y + s], fill=(v, v + 15, 255 - (i % 40)))

    # 惑星（赤）と、その輪
    pcx, pcy, pr = N * 0.635, N * 0.615, N * 0.215
    ring_back = Image.new("RGB", (N, N), (0, 0, 0))
    ImageDraw.Draw(ring_back).ellipse(
        [pcx - pr * 1.9, pcy - pr * 0.52, pcx + pr * 1.9, pcy + pr * 0.52],
        outline=RED, width=int(N * 0.020))
    ring_back = ring_back.rotate(-20, center=(pcx, pcy), resample=Image.BICUBIC)
    ring_back = ring_back.filter(ImageFilter.GaussianBlur(N * 0.003))
    img = _add_arrays(img, Image.eval(ring_back, lambda v: v * 45 // 100))   # 奥側は暗く

    lay, mask = sphere(pcx, pcy, pr, RED)
    img.paste(lay, (0, 0), mask)

    front = ring_back.copy()                    # 手前側は明るく。惑星より下だけ見せる
    cut = Image.new("L", (N, N), 0)
    ImageDraw.Draw(cut).rectangle([0, pcy, N, N], fill=255)
    img = _add_arrays(img, Image.composite(front, Image.new("RGB", (N, N), (0, 0, 0)), cut))

    d = ImageDraw.Draw(img)

    # 星の軌道（惑星の引力で曲がっている様子）。点線で描き、進むほど色が変わる
    for i in range(48):
        t = i / 47
        ang = math.radians(198 - 130 * t)
        rr = N * (0.415 - 0.115 * t)
        x = pcx + math.cos(ang) * rr
        y = pcy + math.sin(ang) * rr * 0.92
        s = N * (0.006 + 0.011 * t)
        col = (int(125 + 130 * t), int(249 * (1 - t) + 225 * t), int(255 * (1 - t) + 77 * t))
        d.ellipse([x - s, y - s, x + s, y + s], fill=col)

    # 先頭の星（白く光る）
    ang = math.radians(198 - 130)
    hx = pcx + math.cos(ang) * N * 0.30
    hy = pcy + math.sin(ang) * N * 0.30 * 0.92
    img = _add_arrays(img, glow_ring(N, hx, hy, N * 0.030, int(N * 0.055), (255, 250, 210), int(N * 0.022)))
    d = ImageDraw.Draw(img)
    d.ellipse([hx - N * 0.040, hy - N * 0.040, hx + N * 0.040, hy + N * 0.040], fill=(255, 255, 255))

    # 3原色のゲート（このゲームの「色が混ざる」を1目で伝える）
    for i, col in enumerate((RED, BLUE, YELLOW)):
        gx = N * (0.175 + i * 0.100)
        gy = N * (0.215 + i * 0.050)
        img = _add_arrays(img, glow_ring(N, gx, gy, N * 0.060, int(N * 0.018), col, int(N * 0.007)))

    img = img.resize((S, S), Image.LANCZOS)
    for dest in DESTS:
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest, "PNG")          # RGB のまま＝アルファ無し
        print("%s  %.0f KB" % (dest.relative_to(ROOT), dest.stat().st_size / 1024))


if __name__ == "__main__":
    main()
