"""重要事項説明書（35条）・売買契約書（37条）PDFの前面入力ページから、
照合に必要なキーワード・数値・パーセンテージを正規表現で抽出する。

抽出結果は dict で返し、LegalCrossCheckData.explanation / .contract に格納する。
レイアウトに依存しすぎないよう、ラベル近傍のテキストを緩く拾う方針。
"""

from __future__ import annotations

import io
import re

import pdfplumber

# 用途地域の候補（長い名称を先にマッチさせる）
_USE_DISTRICTS = [
    "第一種低層住居専用地域", "第二種低層住居専用地域",
    "第一種中高層住居専用地域", "第二種中高層住居専用地域",
    "第一種住居地域", "第二種住居地域", "準住居地域", "田園住居地域",
    "近隣商業地域", "商業地域", "準工業地域", "工業専用地域", "工業地域",
]


def extract_text(pdf_bytes: bytes) -> str:
    parts: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


def _clean(s: str) -> str:
    return re.sub(r"\s+", "", s or "").strip()


def _num_near(text: str, label_pat: str) -> float | None:
    """ラベル近傍の最初の数値を返す。"""
    m = re.search(label_pat + r"[^\d]{0,12}([\d,，]+(?:\.\d+)?)", text)
    if not m:
        return None
    return float(m.group(1).replace(",", "").replace("，", ""))


def _find_use_district(text: str) -> str:
    for name in _USE_DISTRICTS:
        if name in text:
            return name
    return ""


def parse_common(text: str) -> dict:
    """重説・契約書 共通の物件表示・面積・名義・日付・地域を抽出。"""
    t = text.replace(" ", "")
    out: dict = {}

    # 地番・家屋番号
    m = re.search(r"地番[\s　]*([0-9０-９\-－番地ノの]+)", t)
    if m:
        out["chiban"] = _clean(m.group(1))
    m = re.search(r"家屋番号[\s　]*([0-9０-９\-－番地ノの]+)", t)
    if m:
        out["kaoku_number"] = _clean(m.group(1))

    # 面積（土地・建物/専有）
    land = _num_near(t, r"(?:土地面積|地積)")
    if land is not None:
        out["land_area"] = land
    floor = _num_near(t, r"(?:建物面積|床面積|専有面積)")
    if floor is not None:
        out["floor_area"] = floor

    # 用途地域・建ぺい率・容積率
    ud = _find_use_district(t)
    if ud:
        out["use_district"] = ud
    bc = _num_near(t, r"建ぺい率|建蔽率")
    if bc is not None:
        out["building_coverage"] = bc
    far = _num_near(t, r"容積率")
    if far is not None:
        out["floor_area_ratio"] = far

    # セットバック面積（あれば）
    m = re.search(r"セットバック[^\d]{0,20}([\d,，]+(?:\.\d+)?)\s*[㎡m]", t)
    if m:
        out["setback_area"] = float(m.group(1).replace(",", "").replace("，", ""))
    # 算定根拠の敷地面積（建ぺい/容積の計算に使う面積）
    base = _num_near(t, r"(?:敷地面積|算定[^\d]{0,6}面積|有効敷地)")
    if base is not None:
        out["calc_site_area"] = base

    # 売主 氏名・住所
    m = re.search(r"売主[\s　:：]*(?:住所[\s　:：]*)?([^\n]{0,40})", text)
    if m:
        out["seller_raw"] = _clean(m.group(1))

    # 日付（契約日／説明日／ローン承認期日）
    for key, pat in (
        ("contract_date", r"(?:契約締結日|売買契約日|契約日)"),
        ("explain_date", r"(?:説明日|重要事項説明.{0,6}日)"),
        ("loan_deadline", r"(?:融資承認|ローン承認|融資利用.{0,6}期日)"),
    ):
        d = _find_date(text, pat)
        if d:
            out[key] = d

    return out


def _find_date(text: str, label_pat: str) -> str:
    """ラベル近傍の日付（和暦/西暦）を正規化した文字列で返す。"""
    m = re.search(
        label_pat + r"[^\d令平昭]{0,10}"
        r"((?:令和|平成|昭和)?\s*[0-9０-９元]+\s*年\s*[0-9０-９]+\s*月\s*[0-9０-９]+\s*日)",
        text,
    )
    if m:
        return _clean(m.group(1))
    # 西暦 yyyy/mm/dd, yyyy-mm-dd
    m = re.search(label_pat + r"[^\d]{0,10}(\d{4}[/\-.]\d{1,2}[/\-.]\d{1,2})", text)
    if m:
        return _clean(m.group(1))
    return ""


def parse_explanation(pdf_bytes: bytes) -> dict:
    """重要事項説明書の抽出。共通項目をそのまま使う。"""
    text = extract_text(pdf_bytes)
    out = parse_common(text)
    out["_text"] = text
    return out


# ---- 契約書 特有：宅建業法リスク条項 ----
def parse_contract(pdf_bytes: bytes) -> dict:
    text = extract_text(pdf_bytes)
    out = parse_common(text)
    out["_text"] = text
    t = text.replace(" ", "")

    # 売買代金（違約金2割制限の母数）
    price = _num_near(t, r"(?:売買代金|売買価格|代金総額)")
    if price is not None:
        out["sale_price"] = price

    # 違約金・損害賠償の予定額
    penalty = _num_near(t, r"(?:違約金|損害賠償の予定|損害賠償額の予定)")
    if penalty is not None:
        out["penalty_amount"] = penalty

    # 契約不適合責任（瑕疵担保）の通知期間（か月／年）
    m = re.search(r"(?:契約不適合|瑕疵担保)[^\n]{0,40}?([0-9０-９]+)\s*(年|か月|ヶ月|カ月|箇月)", t)
    if m:
        num = int(_zen2han(m.group(1)))
        unit = m.group(2)
        months = num * 12 if unit == "年" else num
        out["nonconformity_months"] = months

    # 反社会的勢力排除条項の有無
    out["has_antisocial_clause"] = bool(re.search(r"反社会的勢力|暴力団", t))

    # 手付解除（倍額償還／倍返し）の文言
    out["has_double_return"] = bool(re.search(r"倍額(?:を)?償還|倍返し|手付.{0,4}倍", t))

    return out


def _zen2han(s: str) -> str:
    return s.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
