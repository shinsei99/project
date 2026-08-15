"""A4チラシ（300dpi）を1枚描く。看板と同じ橙×濃紺で、屋外ホルダーに入れる前提。

PDFはPILの画像PDFとして出す。ベクターにはならないが300dpiあれば掲示物としては十分で、
和文フォントの埋め込みで悩まなくて済む。
"""
from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFont, ImageOps

from properties import LICENSE

# A4 / 300dpi
W, H = 2480, 3508
MARGIN = 130

ORG = (240, 124, 30)
NAVY = (27, 35, 64)
CREAM = (255, 244, 230)
WHITE = (255, 255, 255)
GRAY = (110, 116, 132)
INK = (32, 35, 45)
LINE = (214, 218, 228)

FONT_DIR = "/System/Library/Fonts/ヒラギノ角ゴシック {}.ttc"


def font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_DIR.format(weight), size)


@dataclass
class Flyer:
    kicker: str = "兵庫県加東市秋津 別荘地"
    catch: str = "大阪から1時間。\n別荘を、借りる。"
    title: str = "加東市秋津 貸家"
    rent: str = "59,000"
    rent_note: str = "敷金・礼金なし／管理費なし"
    specs: list[tuple[str, str]] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    body: str = ""
    tel: str = "06-6935-7267"
    company: str = "新誠プロパティマネジメント株式会社"
    address: str = "〒531-0076 大阪市北区大淀中3-1-15　TEL 06-6935-7267 ／ FAX 06-7635-7811"
    qr_url: str = ""
    qr_label: str = "写真と間取りをもっと見る"
    main_photo: str | None = None
    sub_photos: list[str] = field(default_factory=list)
    madori: str | None = None


def load_image(path: str) -> Image.Image:
    """CR2はPILで開けないのでsipsに投げる。macOSのImage I/OがCanon RAWを読める。"""
    p = Path(path)
    if p.suffix.lower() in (".cr2", ".cr3", ".arw", ".nef", ".dng"):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            out = tmp.name
        subprocess.run(
            ["sips", "-s", "format", "jpeg", str(p), "--out", out],
            check=True, capture_output=True,
        )
        im = Image.open(out)
        im.load()
        Path(out).unlink(missing_ok=True)
        return im.convert("RGB")
    return ImageOps.exif_transpose(Image.open(p)).convert("RGB")


def _cover(im: Image.Image, box: tuple[int, int]) -> Image.Image:
    """boxを埋めるように中央でトリミング。"""
    bw, bh = box
    scale = max(bw / im.width, bh / im.height)
    im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)
    x = (im.width - bw) // 2
    y = (im.height - bh) // 2
    return im.crop((x, y, x + bw, y + bh))


def _contain(im: Image.Image, box: tuple[int, int]) -> Image.Image:
    im = im.copy()
    im.thumbnail(box, Image.LANCZOS)
    return im


def _wrap(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, width: int) -> list[str]:
    """和文は単語で折れないので1文字ずつ詰める。改行は尊重する。"""
    lines: list[str] = []
    for para in text.split("\n"):
        cur = ""
        for ch in para:
            if draw.textlength(cur + ch, font=f) > width and cur:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        lines.append(cur)
    return lines


def render(fl: Flyer) -> Image.Image:
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    # ── ヘッダー（橙）
    head_h = 470
    d.rectangle([0, 0, W, 26], fill=NAVY)
    d.rectangle([0, 26, W, head_h], fill=ORG)
    d.text((MARGIN, 78), fl.kicker, font=font("W6", 46), fill=(122, 61, 5))

    f_catch = font("W8", 118)
    y = 150
    for ln in fl.catch.split("\n")[:2]:
        d.text((MARGIN, y), ln, font=f_catch, fill=NAVY)
        y += 138

    # ── メイン写真
    top = head_h
    ph_h = 900
    if fl.main_photo:
        img.paste(_cover(load_image(fl.main_photo), (W, ph_h)), (0, top))
    else:
        d.rectangle([0, top, W, top + ph_h], fill=(238, 240, 245))
    y = top + ph_h

    # ── 物件名と賃料
    band_h = 250
    d.rectangle([0, y, W, y + band_h], fill=NAVY)
    d.text((MARGIN, y + 46), fl.title, font=font("W6", 60), fill=WHITE)
    d.text((MARGIN, y + 128), fl.rent_note, font=font("W3", 40), fill=(180, 190, 220))

    f_num = font("W9", 130)
    f_unit = font("W6", 52)
    unit_w = d.textlength("円 / 月", font=f_unit)
    num_w = d.textlength(fl.rent, font=f_num)
    rx = W - MARGIN - unit_w - num_w - 16
    d.text((rx, y + 62), fl.rent, font=f_num, fill=ORG)
    d.text((rx + num_w + 16, y + 138), "円 / 月", font=f_unit, fill=WHITE)
    y += band_h

    # ── サブ写真（最大3枚）
    if fl.sub_photos:
        gap = 16
        n = min(3, len(fl.sub_photos))
        cw = (W - gap * (n - 1)) // n
        ch = 380
        for i, p in enumerate(fl.sub_photos[:n]):
            img.paste(_cover(load_image(p), (cw, ch)), (i * (cw + gap), y))
        y += ch

    # ── 特徴タグ
    if fl.tags:
        y += 30
        f_tag = font("W6", 44)
        x = MARGIN
        for t in fl.tags:
            tw = d.textlength(t, font=f_tag)
            if x + tw + 60 > W - MARGIN:
                x = MARGIN
                y += 90
            d.rounded_rectangle([x, y, x + tw + 56, y + 74], radius=37, fill=CREAM,
                                outline=ORG, width=3)
            d.text((x + 28, y + 12), t, font=f_tag, fill=(150, 70, 8))
            x += tw + 56 + 18
        y += 74

    # ── 本文
    if fl.body.strip():
        y += 30
        f_body = font("W3", 44)
        for ln in _wrap(d, fl.body.strip(), f_body, W - MARGIN * 2):
            d.text((MARGIN, y), ln, font=f_body, fill=INK)
            y += 66

    # ── スペック表（左）と間取り図（右）
    y += 40
    foot_h = 440
    area_bottom = H - foot_h - 40
    col_w = int((W - MARGIN * 2) * 0.53)
    row_h = 68
    f_k = font("W6", 36)
    f_v = font("W3", 36)
    ty = y
    for i, (k, v) in enumerate(fl.specs):
        if ty + row_h > area_bottom:
            break
        if i % 2 == 0:
            d.rectangle([MARGIN, ty, MARGIN + col_w, ty + row_h], fill=(246, 248, 252))
        d.text((MARGIN + 22, ty + 15), k, font=f_k, fill=NAVY)
        d.text((MARGIN + 300, ty + 15), v, font=f_v, fill=INK)
        d.line([MARGIN, ty + row_h, MARGIN + col_w, ty + row_h], fill=LINE, width=2)
        ty += row_h

    if fl.madori:
        mx = MARGIN + col_w + 50
        mw = W - MARGIN - mx
        mh = area_bottom - y
        m = _contain(load_image(fl.madori), (mw, mh))
        img.paste(m, (mx + (mw - m.width) // 2, y + (mh - m.height) // 2))
        d.text((mx, y - 46), "間取り", font=font("W6", 34), fill=GRAY)

    # ── フッター（濃紺）
    fy = H - foot_h
    d.rectangle([0, fy, W, H], fill=NAVY)
    d.text((MARGIN, fy + 56), "内覧・お問い合わせ", font=font("W3", 42), fill=(170, 182, 216))
    d.text((MARGIN - 6, fy + 112), f"☎ {fl.tel}", font=font("W9", 116), fill=ORG)
    # 社名はロゴで出す（名刺 名刺-鷲見慎一新誠v9.ai から抜いたSPMロゴの白版）。
    # 宅建業免許番号は変わるのでロゴには入れず、下の住所行に文字で出す（表示義務はそちらで満たす）。
    logo = Path(__file__).parent / "assets" / "spm_logo_white_name.png"
    if logo.exists():
        lg = Image.open(logo).convert("RGBA")
        lh = 74
        lg = lg.resize((round(lg.width * lh / lg.height), lh), Image.LANCZOS)
        img.paste(lg, (MARGIN, fy + 252), lg)
    else:
        d.text((MARGIN, fy + 268), fl.company, font=font("W6", 44), fill=WHITE)
    d.text((MARGIN, fy + 344), f"{fl.address}　{LICENSE}",
           font=font("W3", 32), fill=(170, 182, 216))

    if fl.qr_url:
        qr = qrcode.QRCode(box_size=10, border=1)
        qr.add_data(fl.qr_url)
        qr.make(fit=True)
        qi = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        side = 300
        qi = qi.resize((side, side), Image.NEAREST)
        qx = W - MARGIN - side
        img.paste(qi, (qx, fy + 70))
        lf = font("W3", 28)
        lw = d.textlength(fl.qr_label, font=lf)
        d.text((qx + (side - lw) / 2, fy + 70 + side + 14), fl.qr_label, font=lf, fill=(170, 182, 216))

    return img


def save_pdf(img: Image.Image, path: str) -> None:
    img.save(path, "PDF", resolution=300.0)
