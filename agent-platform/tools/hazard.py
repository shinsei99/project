"""アイテム: ハザードマップの該当地点URL（重ねるハザードマップ）

jyuusetsu-research と同じ考え方。APIは公開されていないので、
「その地点を開くURL」を組み立てて人が確認できるようにする。
断定的な浸水深などを機械で書かないこと（誤りが致命的なため）。
"""
from __future__ import annotations

from typing import Tuple

NAME = "hazard"
LABEL = "ハザードマップURL（国土地理院）"
DESCRIPTION = "緯度経度から重ねるハザードマップの該当地点URLを作る。人が目視確認する前提"

PORTAL = "https://disaportal.gsi.go.jp/maps/index.html?ll={lat},{lon}&z={zoom}"


def available() -> Tuple[bool, str]:
    return True, "URL生成のみ（外部接続なし）"


def portal_url(lat: float, lon: float, zoom: int = 16) -> str:
    return PORTAL.format(lat=lat, lon=lon, zoom=zoom)
