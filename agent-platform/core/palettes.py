"""紙面の配色パターン

なぜ用意するか:
  同じ型でも、色が違えば紙面の印象は別物になる。赤は勢い、紺は信頼、緑は自然。
  物件や用途に合う色を毎回その場で決めさせると、彩度の高すぎる色や
  文字が読めない組み合わせが出る。**あらかじめ組んだ配色から選ばせる**方が確実で速い。

決め方の原則:
  - accent（主役の色）… 賃料・キャッチ・帯に使う。**濃い色だけ**にする。
    薄い色を主役にすると白抜き文字が読めなくなる
  - ink（締めの色）… 連絡先帯など、紙面の下を締める濃色
  - 2色だけで組む。3色以上使うと素人っぽくなる
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

PALETTES: List[Dict[str, Any]] = [
    {"id": "classic", "name": "赤×紺（標準）", "accent": "#c1272d", "ink": "#1b2a4a",
     "best_for": "汎用。募集チラシ全般。勢いを出したいとき"},
    {"id": "forest", "name": "緑×深緑（自然）", "accent": "#1f6b3a", "ink": "#14331f",
     "best_for": "郊外・別荘・庭付き・ログハウスなど自然が売りの物件"},
    {"id": "marine", "name": "青×濃紺（清潔）", "accent": "#1668b3", "ink": "#102a44",
     "best_for": "新築・リフォーム済み・水回りが売り。清潔感を出したいとき"},
    {"id": "sunset", "name": "橙×濃紺（明るい）", "accent": "#e2701a", "ink": "#1b2a4a",
     "best_for": "ファミリー向け、日当たりが売り、賑やかに見せたいとき"},
    {"id": "earth", "name": "茶×焦茶（落ち着き）", "accent": "#8a5a2b", "ink": "#332218",
     "best_for": "木造・和室・古民家・レトロな物件"},
    {"id": "sakura", "name": "桃×濃紅（やわらかい）", "accent": "#cf4368", "ink": "#3a1f28",
     "best_for": "女性向け・単身向け・かわいらしさを出したいとき"},
    {"id": "mint", "name": "碧×深緑（さわやか）", "accent": "#12867f", "ink": "#12302e",
     "best_for": "学生向け・ワンルーム・軽やかに見せたいとき"},
    {"id": "noir", "name": "金×黒（高級）", "accent": "#a8822f", "ink": "#16181c",
     "best_for": "高額物件・デザイナーズ・落ち着いた高級感を出したいとき"},
    {"id": "mono", "name": "黒×灰（無彩）", "accent": "#2b2f36", "ink": "#1a1d22",
     "best_for": "業者向けの資料。色で主張したくないとき"},
]

DEFAULT = "classic"

# 依頼文から配色を推測する手がかり。外れても実害が無い程度に控えめにする
HINTS = [
    (("ログハウス", "別荘", "森", "山", "庭", "自然", "田舎", "農地"), "forest"),
    (("新築", "リフォーム済", "リノベ", "築浅"), "marine"),
    (("ファミリー", "子育て", "南向き", "日当たり"), "sunset"),
    (("和室", "古民家", "木造", "レトロ", "昭和"), "earth"),
    (("女性", "単身女性", "オートロック"), "sakura"),
    (("学生", "ワンルーム", "1K"), "mint"),
    (("高級", "デザイナーズ", "タワー", "billion"), "noir"),
    (("マイソク", "業者", "物件概要"), "mono"),
]


def all_palettes() -> List[Dict[str, Any]]:
    return list(PALETTES)


def get(palette_id: str) -> Dict[str, Any]:
    for item in PALETTES:
        if item["id"] == palette_id:
            return item
    return PALETTES[0]


def colors(palette_id: str) -> Dict[str, str]:
    item = get(palette_id)
    return {"accent": item["accent"], "ink": item["ink"]}


def guess(text: str, genre: str = "") -> str:
    """依頼文と型から配色を当てる。当たらなければ標準。"""
    if genre == "maisoku":
        return "mono"
    body = str(text or "")
    for words, palette_id in HINTS:
        if any(word in body for word in words):
            return palette_id
    return DEFAULT


def id_from_answer(answer: str) -> str:
    text = str(answer or "").strip()
    if not text:
        return ""
    for item in PALETTES:
        if text == item["id"] or text.startswith(item["name"]) or item["name"] in text:
            return item["id"]
    return ""


def describe_for_prompt() -> str:
    lines = ["【配色（この中から1つ選ぶ）】"]
    for item in PALETTES:
        lines.append("- %s（%s）… %s" % (item["id"], item["name"], item["best_for"]))
    return "\n".join(lines)


def swatch_html(palette_id: str) -> str:
    """色見本。画面で色そのものを見せるため（名前だけでは伝わらない）。"""
    item = get(palette_id)
    return (
        '<div style="display:flex;align-items:center;gap:8px">'
        '<span style="width:26px;height:26px;border-radius:5px;background:%s;'
        'display:inline-block;border:1px solid rgba(0,0,0,.15)"></span>'
        '<span style="width:26px;height:26px;border-radius:5px;background:%s;'
        'display:inline-block;border:1px solid rgba(0,0,0,.15)"></span>'
        '<span style="font-size:13px">%s</span></div>'
        % (item["accent"], item["ink"], item["name"]))
