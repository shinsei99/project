"""クロスチェック（4点連動）を、このアプリの調査結果につなぐアダプタ。

`legal-crosscheck` から検閲エンジン（`law_validator` / `legal_check_data` /
`document_parser`）を持ち込み、**行政の正解と謄本ファクトは、このアプリが
すでに調べた `PropertyData` から作る**。

  🌐 行政の正解  … PropertyData の用途地域・建ぺい率・容積率（国交省 XKT002）
  📄 謄本ファクト … PropertyData の所在地・地番・地積・家屋番号・床面積・構造・所有者
  📝 重説        … アップロードされたPDFから抽出
  🛒 契約書      … アップロードされたPDFから抽出

**元アプリの `_MOCK_MASTERS` は持ち込んでいない。** あれはキー未設定のとき
「新宿→商業地域80/600」のような架空の値を"行政の正解"として返すもので、
**その値を基準に赤字判定をしてしまう**（検閲アプリとして事故の芽）。
値が無いときは空のまま渡す。検閲エンジンは片側が空なら「確認不可」を返すので、
嘘の判定は出ない。
"""

from __future__ import annotations

import re
from typing import Dict, Optional

from models.legal_check_data import AdminMaster, LegalCrossCheckData, RegistryFact
from services import document_parser, law_validator

_NUM = re.compile(r"[\d]+(?:\.\d+)?")


def _to_float(value) -> float:
    """「165.28㎡」「80%」「1,234.5」などから数値だけ取り出す。取れなければ 0.0。"""
    if value in (None, ""):
        return 0.0
    s = str(value).replace(",", "").replace("，", "")
    m = _NUM.search(s)
    return float(m.group()) if m else 0.0


def build_admin(data: Dict[str, str], source: str = "") -> AdminMaster:
    """調査済み PropertyData から行政マスターを作る（取れていない項目は空のまま）。"""
    return AdminMaster(
        use_district=data.get("用途地域", "") or "",
        building_coverage=_to_float(data.get("建ぺい率")),
        floor_area_ratio=_to_float(data.get("容積率")),
        fire_zone=data.get("防火地域", "") or "",
        height_district=data.get("高度地区", "") or "",
        source=source or "国交省 不動産情報ライブラリ XKT002",
    )


def build_registry(data: Dict[str, str]) -> RegistryFact:
    """調査済み PropertyData から謄本ファクトを作る。"""
    return RegistryFact(
        location=data.get("所在地", "") or "",
        chiban=data.get("地番", "") or "",
        land_area=_to_float(data.get("地積")),
        kaoku_number=data.get("家屋番号", "") or "",
        floor_area=_to_float(data.get("床面積")),
        structure=data.get("構造", "") or "",
        owner_name=data.get("所有者", "") or "",
    )


def missing_basis(data: Dict[str, str]) -> list:
    """判定の基準にできない（＝確認不可になる）項目を返す。画面で正直に出すため。"""
    labels = [
        ("用途地域", "用途地域"),
        ("建ぺい率", "指定建ぺい率"),
        ("容積率", "指定容積率"),
        ("地番", "地番"),
        ("地積", "地積"),
        ("床面積", "床面積"),
    ]
    return [name for key, name in labels if not str(data.get(key, "") or "").strip()]


def run(
    data: Dict[str, str],
    explanation_pdf: Optional[bytes],
    contract_pdf: Optional[bytes],
    seller_is_pro: bool = False,
    address: str = "",
) -> LegalCrossCheckData:
    """4者照合を実行して結果を返す。

    重説・契約書のどちらか一方だけでも走る（片方が無い項目は「確認不可」になる）。
    """
    cc = LegalCrossCheckData()
    cc.address = address or data.get("所在地", "")
    cc.admin = build_admin(data)
    cc.registry = build_registry(data)
    cc.explanation = document_parser.parse_explanation(explanation_pdf) if explanation_pdf else {}
    cc.contract = document_parser.parse_contract(contract_pdf) if contract_pdf else {}
    cc.seller_is_pro = seller_is_pro
    law_validator.validate(cc)
    return cc
