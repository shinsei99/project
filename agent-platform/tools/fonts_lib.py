"""アイテム: 日本語フォント（Google Fonts・SIL OFL）

なぜ要るか:
  掲示物やチラシの見栄えは、書体でほぼ決まる。
  OS標準のヒラギノは太さが足りず、「駐輪禁止」を遠くから読ませる迫力が出ない。
  Google Fonts の Noto Sans JP には **Black(900)** があり、掲示物向きの極太が使える。

ライセンス: SIL Open Font License 1.1（商用可・埋め込み可・改変可・帰属不要）。
  Google Fonts は API/CSS の自動取得も認めているので、**自動でダウンロードしてよい**。

初回だけ取得して `tools/assets/fonts/` に保存する。以後はオフラインで動く。
取得できない環境では OS 標準フォントに自動で落ちる。
"""
from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

NAME = "fonts"
LABEL = "日本語フォント（Google Fonts）"
DESCRIPTION = ("Noto Sans JP など商用可の日本語書体を使う。"
               "掲示物の極太見出しなど、OS標準では出せない太さが出せる")

CSS_URL = "https://fonts.googleapis.com/css2?family={family}:wght@{weights}&display=swap"
FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"

# 用途別に使う書体。増やすときはここに足す
FAMILIES = {
    "Noto Sans JP": "400;700;900",       # 本文〜極太見出し。掲示物の主役
    "Zen Kaku Gothic New": "400;700;900",  # 角ゴシック。落ち着いた掲示物向き
}
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def available() -> Tuple[bool, str]:
    cached = list(FONT_DIR.glob("*.ttf")) if FONT_DIR.exists() else []
    if cached:
        return True, "%d書体を取得済み（オフラインで使えます）" % len(cached)
    try:
        import requests  # noqa: F401
    except Exception:
        return False, "requests 未導入"
    return True, "初回にGoogle Fontsから取得します（SIL OFL・商用可）"


def ensure(family: str = "Noto Sans JP") -> List[Path]:
    """書体をダウンロードして保存し、ttfのパス一覧を返す。"""
    import requests

    weights = FAMILIES.get(family, "400;700")
    slug = family.replace(" ", "_")
    existing = sorted(FONT_DIR.glob("%s-*.ttf" % slug))
    if existing:
        return existing

    css = requests.get(CSS_URL.format(family=family.replace(" ", "+"), weights=weights),
                       headers={"User-Agent": UA}, timeout=30)
    css.raise_for_status()
    FONT_DIR.mkdir(parents=True, exist_ok=True)

    saved = []
    blocks = re.findall(r"font-weight:\s*(\d+);.*?src:\s*url\(([^)]+)\)", css.text, re.S)
    for weight, url in blocks:
        dest = FONT_DIR / ("%s-%s.ttf" % (slug, weight))
        if not dest.exists():
            data = requests.get(url, headers={"User-Agent": UA}, timeout=60)
            data.raise_for_status()
            dest.write_bytes(data.content)
        saved.append(dest)
    return sorted(set(saved))


def face_css(family: str = "Noto Sans JP") -> str:
    """紙面に埋め込む @font-face のCSSを返す。

    ファイルをbase64で埋め込む。Playwrightに読ませるとき、
    file:// の相対参照は基準が無くて読めないため。
    取得に失敗したら空文字を返し、呼び出し側はOS標準フォントで組む。
    """
    try:
        files = ensure(family)
    except Exception:
        files = sorted(FONT_DIR.glob("%s-*.ttf" % family.replace(" ", "_"))) \
            if FONT_DIR.exists() else []
    if not files:
        return ""

    faces = []
    for path in files:
        weight = path.stem.rsplit("-", 1)[-1]
        try:
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        except OSError:
            continue
        faces.append("@font-face{font-family:'%s';font-style:normal;font-weight:%s;"
                     "src:url(data:font/ttf;base64,%s) format('truetype')}"
                     % (family, weight, encoded))
    return "".join(faces)


def stack(family: str = "Noto Sans JP") -> str:
    """font-family に書く並び。取得できていなくても破綻しないよう標準を後ろに置く。"""
    return "'%s','Hiragino Sans','Yu Gothic',sans-serif" % family
