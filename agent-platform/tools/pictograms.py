"""アイテム: 掲示物用のピクトグラム（SVG）

貼り紙で一番効くのは文字より絵。遠くからでも一目で伝わる。
AI画像生成は有料なうえ、この手の記号は形が崩れるので**SVGで描く**。
無料・軽い・どんな大きさでも綺麗。

絵柄は **Google Material Symbols（Apache-2.0・商用利用可・帰属表示不要）** を使う。
自分で描いたものは自転車とバイクの区別が付かず、実際に司令塔の最終確認で
「壊れた自転車が2つ」と指摘された。既製の綺麗な図形を使う方が確実。

初回だけGitHubから取得して `tools/assets/icons/` に保存する（以後はオフラインで動く）。
取得できない環境では、手描きの簡易版に自動で落ちる。

使い方: `svg("no_bicycle", size=520)` → そのままHTMLに埋められるSVG文字列
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Tuple

NAME = "pictograms"
LABEL = "掲示物のピクトグラム（SVG）"
DESCRIPTION = "駐輪禁止・駐車禁止・立入禁止などの記号をSVGで描く。無料・拡大しても綺麗"

RED = "#d43b34"
DARK = "#222833"

# Material Symbols の取得元（Apache-2.0）
ICON_BASE = ("https://raw.githubusercontent.com/google/material-design-icons/master/"
             "symbols/web/{name}/materialsymbolsrounded/{name}_fill1_24px.svg")
ICON_DIR = Path(__file__).resolve().parent / "assets" / "icons"

# 自前の呼び名 → Material Symbols の名前
MATERIAL_NAMES = {
    "bicycle": "pedal_bike",
    "motorcycle": "two_wheeler",
    "car": "directions_car",
    "person": "directions_walk",
    "trash": "delete",
    "cigarette": "smoking_rooms",
    "sound": "volume_up",
}

# 中身だけ（viewBox 0 0 100 100 前提）。禁止マーク（丸＋斜線）は共通で被せる。
_SHAPES = {
    # 自転車
    "bicycle": """
      <circle cx="27" cy="66" r="16" fill="none" stroke="{c}" stroke-width="5"/>
      <circle cx="73" cy="66" r="16" fill="none" stroke="{c}" stroke-width="5"/>
      <path d="M27 66 L45 40 L62 40 M45 40 L57 66 M62 40 L73 66 M40 40 L52 40"
            fill="none" stroke="{c}" stroke-width="5" stroke-linecap="round"
            stroke-linejoin="round"/>
      <path d="M58 34 L68 34" stroke="{c}" stroke-width="5" stroke-linecap="round"/>
      <circle cx="45" cy="40" r="3.5" fill="{c}"/>""",
    # 自動車
    "car": """
      <path d="M18 62 L24 44 C25 41 27 40 30 40 L70 40 C73 40 75 41 76 44 L82 62 Z"
            fill="none" stroke="{c}" stroke-width="5" stroke-linejoin="round"/>
      <rect x="14" y="62" width="72" height="14" rx="4" fill="none"
            stroke="{c}" stroke-width="5"/>
      <circle cx="30" cy="76" r="5" fill="{c}"/>
      <circle cx="70" cy="76" r="5" fill="{c}"/>""",
    # 人（立入禁止）
    "person": """
      <circle cx="50" cy="26" r="9" fill="none" stroke="{c}" stroke-width="5"/>
      <path d="M50 35 L50 62 M50 42 L34 52 M50 42 L66 52 M50 62 L38 82 M50 62 L62 82"
            fill="none" stroke="{c}" stroke-width="5" stroke-linecap="round"/>""",
    # ゴミ袋
    "trash": """
      <path d="M32 38 L68 38 L64 82 L36 82 Z" fill="none" stroke="{c}" stroke-width="5"
            stroke-linejoin="round"/>
      <path d="M28 38 L72 38" stroke="{c}" stroke-width="5" stroke-linecap="round"/>
      <path d="M42 30 L42 38 M58 30 L58 38" stroke="{c}" stroke-width="5"
            stroke-linecap="round"/>
      <path d="M45 50 L45 70 M55 50 L55 70" stroke="{c}" stroke-width="4"
            stroke-linecap="round"/>""",
    # たばこ
    "cigarette": """
      <rect x="20" y="52" width="46" height="12" rx="2" fill="none"
            stroke="{c}" stroke-width="5"/>
      <rect x="66" y="52" width="14" height="12" rx="2" fill="{c}"/>
      <path d="M60 44 C60 38 68 38 68 32" fill="none" stroke="{c}" stroke-width="4"
            stroke-linecap="round"/>""",
    # バイク・原付
    # 自転車との差は「車体の塊」。線だけで描くと自転車と見分けが付かない
    # （実際に司令塔から「壊れた自転車が2つ」と指摘された）ので、
    # 車体・シート・カウルを塗りつぶしで持たせる。
    "motorcycle": """
      <circle cx="25" cy="76" r="13" fill="none" stroke="{c}" stroke-width="8"/>
      <circle cx="76" cy="76" r="13" fill="none" stroke="{c}" stroke-width="8"/>
      <path d="M25 76 L40 68 L58 68 L70 76" fill="none" stroke="{c}" stroke-width="7"
            stroke-linejoin="round" stroke-linecap="round"/>
      <path d="M22 56 L30 50 L52 50 C58 50 60 54 60 58 L60 66 L34 66 C28 66 24 62 22 56 Z"
            fill="{c}"/>
      <path d="M60 58 L70 42" fill="none" stroke="{c}" stroke-width="7"
            stroke-linecap="round"/>
      <path d="M62 40 L82 36" fill="none" stroke="{c}" stroke-width="7"
            stroke-linecap="round"/>
      <path d="M70 44 L84 50" fill="none" stroke="{c}" stroke-width="6"
            stroke-linecap="round"/>""",
    # 音（静粛）
    "sound": """
      <path d="M24 42 L38 42 L52 30 L52 76 L38 62 L24 62 Z" fill="none"
            stroke="{c}" stroke-width="5" stroke-linejoin="round"/>
      <path d="M62 40 C70 48 70 58 62 66" fill="none" stroke="{c}" stroke-width="5"
            stroke-linecap="round"/>
      <path d="M72 32 C85 46 85 60 72 74" fill="none" stroke="{c}" stroke-width="5"
            stroke-linecap="round"/>""",
}

# 用途名 → (形, 禁止マークを被せるか)
PICTOGRAMS = {
    "no_bicycle": ("bicycle", True),
    "no_motorcycle": ("motorcycle", True),
    "no_parking": ("car", True),
    "no_entry": ("person", True),
    "no_trash": ("trash", True),
    "no_smoking": ("cigarette", True),
    "quiet": ("sound", True),
    "bicycle": ("bicycle", False),
    "motorcycle": ("motorcycle", False),
    "car": ("car", False),
}

# 依頼文からピクトを当てるためのキーワード
KEYWORDS = [
    (("バイク", "原付", "オートバイ", "二輪"), "no_motorcycle"),
    (("駐輪", "自転車", "バイク置"), "no_bicycle"),
    (("駐車", "車を停め", "路上駐車"), "no_parking"),
    (("立入", "立ち入り", "進入"), "no_entry"),
    (("ゴミ", "ごみ", "不法投棄"), "no_trash"),
    (("禁煙", "たばこ", "喫煙"), "no_smoking"),
    (("騒音", "静粛", "お静か", "夜間"), "quiet"),
]


def available() -> Tuple[bool, str]:
    return True, "SVGを組み立てるだけ（外部接続なし）"


def guess(text: str) -> str:
    """依頼文からピクトを推測する。分からなければ立入禁止の人型。"""
    for words, name in KEYWORDS:
        if any(w in (text or "") for w in words):
            return name
    return "no_entry"


def guess_all(text: str, limit: int = 2) -> list:
    """依頼文から必要なピクトを**複数**拾う。

    「自転車もバイクも禁止」なら2つ並べないと、遠目には自転車専用の掲示に見える
    （司令塔の最終確認で実際に指摘された）。
    """
    found = []
    for words, name in KEYWORDS:
        if any(w in (text or "") for w in words) and name not in found:
            found.append(name)
    # **当てが外れたときに「人の立入禁止」を出さない。**
    # 意味の合わない記号は、記号が無いより悪い（読み手が誤解する）
    return found[:limit]


def svg_group(names, size: int = 300, color: str = RED, gap: int = 28) -> str:
    """複数のピクトを横に並べたHTMLを返す。1つなら大きく、2つなら少し小さく。"""
    names = [n for n in (names or []) if n in PICTOGRAMS] or ["no_entry"]
    each = size if len(names) == 1 else int(size * 0.72)
    parts = "".join(svg(n, each, color) for n in names)
    return ('<div style="display:flex;align-items:center;justify-content:center;'
            'gap:%dpx">%s</div>' % (gap, parts))


def _material_inner(shape_key: str) -> Optional[str]:
    """Material Symbols のSVGから中身（path）だけ取り出す。無ければ取得して保存。"""
    material = MATERIAL_NAMES.get(shape_key)
    if not material:
        return None
    cached = ICON_DIR / ("%s.svg" % material)
    if not cached.exists():
        try:
            import requests

            resp = requests.get(ICON_BASE.format(name=material), timeout=20)
            resp.raise_for_status()
            ICON_DIR.mkdir(parents=True, exist_ok=True)
            cached.write_text(resp.text, encoding="utf-8")
        except Exception:
            return None
    try:
        text = cached.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r"<svg[^>]*>(.*)</svg>", text, re.S)
    return match.group(1) if match else None


def svg(name: str, size: int = 480, color: str = RED, bar: bool = True) -> str:
    """埋め込み用のSVG文字列を返す。

    既製アイコン（Material Symbols）があればそれを使い、
    取得できないときは手描きの簡易版に落ちる。
    """
    shape_key, forbid = PICTOGRAMS.get(name, PICTOGRAMS["no_entry"])
    inner = _material_inner(shape_key)
    if inner:
        # Material の座標系は viewBox="0 -960 960 960"。入れ子SVGで自分の座標系に収める
        body = ('<svg x="22" y="27" width="56" height="56" viewBox="0 -960 960 960" '
                'fill="%s">%s</svg>' % (color, inner))
    else:
        body = _SHAPES[shape_key].format(c=color)
    overlay = ""
    if forbid and bar:
        overlay = (
            '<circle cx="50" cy="55" r="44" fill="none" stroke="%s" stroke-width="9"/>'
            '<line x1="19" y1="86" x2="81" y2="24" stroke="%s" stroke-width="9" '
            'stroke-linecap="round"/>' % (color, color))
    return ('<svg width="%d" height="%d" viewBox="0 0 100 110" '
            'xmlns="http://www.w3.org/2000/svg">%s%s</svg>'
            % (size, int(size * 1.1), body, overlay))


# 禁止の記号と、その素の記号の対応（素→禁止）
PROHIBITION_OF = {"bicycle": "no_bicycle", "motorcycle": "no_motorcycle",
                  "car": "no_parking", "person": "no_entry",
                  "trash": "no_trash", "cigarette": "no_smoking",
                  "sound": "quiet"}


def to_prohibition(names) -> list:
    """禁止の掲示では、素の記号を禁止の記号に直す。

    「自転車の絵」と「人に斜線」が並ぶと、**自転車は置いてよいと読める**。
    禁止の紙面に素の記号を混ぜてはいけない（実際にそう見える紙面が出た）。
    """
    out = []
    for name in names or []:
        name = str(name)
        fixed = PROHIBITION_OF.get(name, name)
        if fixed in PICTOGRAMS and fixed not in out:
            out.append(fixed)
    return out
