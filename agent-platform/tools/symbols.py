"""アイテム: 記号（Material Symbols・2,500種）

なぜ要るか:
  「フリー素材を使って」と言われても、`assets/` は人が手で落として置く前提で、
  実際には空のままだった。結果、紙面も動画も**文字だけ**になっていた。

  Material Symbols は Apache-2.0（商用可・帰属表示不要）で、
  **1つずつSVGを取りに行ける**。人の作業を挟まずに使える唯一の素材源なので、
  ここを既定の絵柄にする。

  いらすとや・ソコスト等は規約上、機械での一括取得をしない。
  使いたい場合は人が落として `assets/イラスト` に置く（assets_lib が拾う）。

取り方:
  GitHub の material-design-icons から1つずつ取得して `tools/assets/icons` に残す。
  一度取れば次からは通信しない。取れなければ何も描かない（似た絵で誤魔化さない）。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple

NAME = "symbols"
LABEL = "記号（Material Symbols）"
DESCRIPTION = "地図・人・イベント・食事など2,500種の記号（Apache-2.0・商用可）"

BASE = ("https://raw.githubusercontent.com/google/material-design-icons/master/"
        "symbols/web/{name}/materialsymbolsrounded/{name}_{fill}24px.svg")
DIR = Path(__file__).resolve().parent / "assets" / "icons"

# よく使う記号。**部隊にはこの一覧から選ばせる**（存在しない名前を書かせないため）
CATALOG = {
    "まち・場所": ["location_city", "store", "storefront", "home", "apartment",
                   "map", "place", "directions_walk", "train", "directions_bus",
                   "restaurant", "local_cafe", "park", "temple_buddhist"],
    "人・つながり": ["groups", "group_add", "diversity_3", "handshake", "family_restroom",
                     "volunteer_activism", "child_care", "elderly", "person_add",
                     "connect_without_contact"],
    "発信・記録": ["campaign", "newspaper", "podcasts", "photo_camera", "movie",
                   "record_voice_over", "share", "trending_up", "insights",
                   "query_stats", "menu_book", "history_edu"],
    "運営・仕組み": ["lightbulb", "flag", "target", "checklist", "schedule",
                     "savings", "payments", "handyman", "build", "settings",
                     "rocket_launch", "school"],
    "催し": ["celebration", "local_activity", "music_note", "sports_esports",
             "theater_comedy", "emoji_food_beverage", "shopping_bag", "storefront"],
}

ALL_NAMES = sorted({n for names in CATALOG.values() for n in names})


def available() -> Tuple[bool, str]:
    cached = len(list(DIR.glob("*.svg"))) if DIR.exists() else 0
    return True, "記号（Material Symbols・取得済み%d点）" % cached


def _fetch(name: str, filled: bool = True) -> Optional[str]:
    path = DIR / ("%s%s.svg" % (name, "_fill1" if filled else ""))
    if path.exists():
        return path.read_text(encoding="utf-8")
    try:
        import requests

        url = BASE.format(name=name, fill="fill1_" if filled else "")
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200 or "<svg" not in resp.text:
            return None
        DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(resp.text, encoding="utf-8")
        return resp.text
    except Exception:
        return None


def svg(name: str, color: str = "#1b2a4a", size: int = 96,
        filled: bool = True) -> str:
    """記号のSVG。**取れなければ空文字**（似た絵で代用しない）。"""
    raw = _fetch(str(name).strip(), filled=filled)
    if not raw:
        return ""
    body = re.sub(r"<svg[^>]*>", "", raw).replace("</svg>", "").strip()
    body = re.sub(r'fill="[^"]*"', "", body)
    return ('<svg viewBox="0 -960 960 960" width="%d" height="%d" fill="%s" '
            'xmlns="http://www.w3.org/2000/svg">%s</svg>' % (size, size, color, body))


def ensure_many(names, color: str = "#1b2a4a", size: int = 96) -> dict:
    """複数まとめて。使えたものだけ返す。"""
    out = {}
    for name in names or []:
        drawn = svg(name, color=color, size=size)
        if drawn:
            out[str(name)] = drawn
    return out


def png(name: str, color: str = "#1b2a4a", size: int = 256) -> Optional[str]:
    """記号をPNGにする。**PowerPointはSVGを安定して扱えない**ため。

    透過PNGで書き出し、色ごとにキャッシュする。
    """
    import hashlib

    drawn = svg(name, color=color, size=size)
    if not drawn:
        return None
    key = hashlib.md5(("%s|%s|%d" % (name, color, size)).encode("utf-8")).hexdigest()
    out = DIR / "png" / ("%s.png" % key)
    if out.exists():
        return str(out)
    try:
        from playwright.sync_api import sync_playwright

        out.parent.mkdir(parents=True, exist_ok=True)
        html = ("<style>html,body{margin:0;background:transparent}"
                "svg{display:block}</style>%s" % drawn)
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": size, "height": size})
            page.set_content(html, wait_until="load")
            page.screenshot(path=str(out), omit_background=True)
            browser.close()
        return str(out)
    except Exception:
        return None


def describe_for_prompt() -> str:
    lines = ["【使える記号（この名前で指定すること。無い名前は書かない）】"]
    for group, names in CATALOG.items():
        lines.append("- %s: %s" % (group, " / ".join(names)))
    return "\n".join(lines)
