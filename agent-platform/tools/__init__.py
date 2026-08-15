"""各部隊が使う「アイテム」（道具）。

方針:
  この45本のリポジトリで**すでに作って動いているもの**を、部隊から呼べる形にする。
  ゼロから作らない。同じ調査・同じ実装を二度やらないため。

いま持たせているアイテム:
  flyer     … HTML → A4のPDF/PNG（Playwright）。チラシ・帳票が実際に作れる
  geo       … 住所 → 緯度経度、逆引き（国土地理院・キー不要）
  mlit      … 不動産の実取引価格・地価（国交省 不動産情報ライブラリ。既存キーを自動検出）
  hazard    … ハザードマップの該当地点URL（国土地理院）
  photo_fix … 写真から電線・車・家具を消す（photo-inpainter の LaMa をそのまま利用）
  pdf_read  … PDFの向き補正つきテキスト/画像化（既存の pdf_orient.py を利用）

各アイテムは `available()` で「今この環境で使えるか」を自己申告する。
使えないものは部隊に渡さない（存在しない道具を前提にした計画を立てさせないため）。
"""
from __future__ import annotations

from typing import Any, Dict, List

from . import (assets_lib, flyer, fonts_lib, free_photos, geo, hazard, mlit,
               motion,
               feature_icons, pdf_images, pdf_read, photo_fix, photos, pictograms, qr,
               symbols,
               webread)

MODULES = [flyer, pictograms, symbols, free_photos, feature_icons, fonts_lib,
           assets_lib,
           photos, pdf_images,
           webread, geo, mlit,
           hazard, photo_fix, pdf_read, motion]


def catalog() -> List[Dict[str, Any]]:
    """アイテム一覧（画面・--doctor 用）。"""
    items = []
    for module in MODULES:
        try:
            ok, note = module.available()
        except Exception as exc:  # アイテム側の不調で全体を止めない
            ok, note = False, str(exc)[:80]
        items.append({"name": module.NAME, "label": module.LABEL,
                      "description": module.DESCRIPTION, "available": ok, "note": note})
    return items


def available_names() -> List[str]:
    return [item["name"] for item in catalog() if item["available"]]


def describe_for_prompt() -> str:
    """部隊のプロンプトに差し込む「いま使える道具」の説明。"""
    lines = []
    for item in catalog():
        if item["available"]:
            lines.append("- %s: %s" % (item["label"], item["description"]))
    return "\n".join(lines)
