"""登記簿謄本（土地・建物）PDFを pdfplumber + 正規表現で解析し
RegistryFact（公式ファクト値）を抽出する。

realestate-valuation/services/registry_parser.py と同じ作法。
謄本のレイアウトは様々なので、取れなかった項目は空のまま（確認不可）にする。
"""

from __future__ import annotations

import io
import re

import pdfplumber

from models.legal_check_data import RegistryFact


def extract_text(pdf_bytes: bytes) -> str:
    """謄本PDF → 全文テキスト。"""
    parts: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


def _to_float(s: str) -> float:
    """'123.45㎡' '1,234.5' 等 → float。"""
    if not s:
        return 0.0
    s = s.replace(",", "").replace("，", "")
    m = re.search(r"\d+(?:\.\d+)?", s)
    return float(m.group()) if m else 0.0


def _clean(s: str) -> str:
    return re.sub(r"\s+", "", s or "").strip()


def parse_text(text: str) -> RegistryFact:
    """謄本テキストから各項目を正規表現抽出。"""
    fact = RegistryFact()

    # ---- 所在 ----
    m = re.search(r"所\s*在[\s　]*([^\n]+)", text)
    if m:
        fact.location = _clean(m.group(1))

    # ---- 地番 ----
    m = re.search(r"地\s*番[\s　]*([0-9０-９\-－番地ノの]+)", text)
    if m:
        fact.chiban = _clean(m.group(1))

    # ---- 地積（土地面積） ----
    m = re.search(r"地\s*積[^\d]*([\d,，]+(?:\.\d+)?)", text)
    if m:
        fact.land_area = _to_float(m.group(1))

    # ---- 家屋番号 ----
    m = re.search(r"家\s*屋\s*番\s*号[\s　]*([0-9０-９\-－番地ノの]+)", text)
    if m:
        fact.kaoku_number = _clean(m.group(1))

    # ---- 床面積／専有面積 ----
    m = re.search(r"(?:床\s*面\s*積|専\s*有\s*面\s*積)[^\d]*([\d,，]+(?:\.\d+)?)", text)
    if m:
        fact.floor_area = _to_float(m.group(1))

    # ---- 構造 ----
    m = re.search(r"構\s*造[\s　]*([^\n]+)", text)
    if m:
        fact.structure = _clean(m.group(1))[:40]

    # ---- 所有者（甲区・最新の所有権登記名義人） ----
    # 「所有者」表記、または甲区の「権利者その他の事項 ... 所有者 住所 氏名」
    owners = re.findall(r"所\s*有\s*者[\s　]*([^\n]+)", text)
    if owners:
        raw = _clean(owners[-1])  # 最新（末尾）を採用
        fact.owner_address, fact.owner_name = _split_owner(raw)

    return fact


def _split_owner(raw: str) -> tuple[str, str]:
    """'東京都新宿区西新宿1-1-1山田太郎' → (住所, 氏名)。
    住所末尾の番地以降を切れ目とみなす素朴な分割。"""
    raw = _clean(raw)
    # 番地（数字＋ハイフン）の塊の直後を氏名の開始とみなす
    m = re.search(r"^(.*?[0-9０-９]+(?:[\-－ー][0-9０-９]+)*)([^\d0-9].*)$", raw)
    if m:
        return m.group(1), m.group(2)
    return "", raw


def parse(pdf_bytes: bytes) -> RegistryFact:
    return parse_text(extract_text(pdf_bytes))
