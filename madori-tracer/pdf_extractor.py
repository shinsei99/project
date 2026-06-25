"""マイソク PDF から間取り図を抽出する。"""
from __future__ import annotations

import io

import fitz  # PyMuPDF
from PIL import Image


def pdf_to_image(pdf_bytes: bytes, dpi: int = 150) -> Image.Image:
    """PDF の 1 ページ目をラスタ画像に変換する。"""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    pix = page.get_pixmap(dpi=dpi)
    img = Image.open(io.BytesIO(pix.tobytes("jpeg"))).convert("RGB")
    # 解析に使いやすい幅に縮小
    if img.width > 1400:
        r = 1400 / img.width
        img = img.resize((1400, int(img.height * r)), Image.LANCZOS)
    return img


def extract_floor_plan_from_pdf(pdf_bytes: bytes) -> Image.Image:
    """PDF バイト列 → ページ全体画像を返す（間取り図抽出はanalyzerで行う）。"""
    return pdf_to_image(pdf_bytes)
