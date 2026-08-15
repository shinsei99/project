"""日本語フォントの解決（Pillow で文字を描くときに使う）。

macOS標準のフォントを上から順に探す。見つからなければ Pillow の既定フォントに
落ちるが、その場合日本語は豆腐（□）になるので、呼び出し側は
`has_japanese_font()` で判定して英数字だけ描くなどの判断ができる。
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

CANDIDATES = [
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
]


def japanese_font_path() -> Optional[str]:
    for path in CANDIDATES:
        if Path(path).exists():
            return path
    return None


def has_japanese_font() -> bool:
    return japanese_font_path() is not None


def load_font(size: int):
    """Pillow の ImageFont を返す。Pillow が無い場合は None。"""
    try:
        from PIL import ImageFont  # type: ignore
    except Exception:
        return None
    path = japanese_font_path()
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    try:
        return ImageFont.load_default()
    except Exception:
        return None
