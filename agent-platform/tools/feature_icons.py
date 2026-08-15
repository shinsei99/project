"""アイテム: 物件の特色アイコン（73種）

出どころ:
  マイソクコンバーター（maisoku-converter/features/）で使っている自社のアイコン集。
  「南向き」「宅配ボックス」「ペット飼育可」など、不動産の紙面で繰り返し使う項目が
  一通り揃っている。**自社の素材なので権利の心配がない。**

なぜ文字のタグより効くか:
  「南向き・追焚き・宅配ボックス」と文字で並べても読み飛ばされる。
  絵が付くと目に留まり、離れていても何の設備か分かる。マイソクでは実際にこの形。

色:
  元は緑一色。紙面の色（accent）に合わせて塗り替えて使う。塗り替えた版はキャッシュする。
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.config import ROOT

NAME = "feature_icons"
LABEL = "物件の特色アイコン"
DESCRIPTION = "南向き・宅配ボックス・ペット可など、不動産の設備条件アイコン73種（自社素材）"

DIR = ROOT / "assets" / "feature_icons"
CACHE = ROOT / ".cache" / "feature_icons"

# 名前の言い換え。紙面に書かれる言葉とファイル名は一致しないことが多い
ALIASES = {
    "宅配ボックス": ("宅配BOX", "宅配ロッカー"),
    "追焚き機能": ("追焚", "追い焚き", "追焚き"),
    "温水洗浄便座": ("ウォシュレット", "シャワートイレ"),
    "オートロック": ("オートロック付",),
    "ペット飼育可犬": ("ペット可", "ペット相談可", "犬"),
    "ペット飼育可猫": ("猫",),
    "駐車場有": ("駐車場", "駐車場あり", "駐車1台", "駐車場付"),
    "駐輪場有": ("駐輪場", "自転車置場"),
    "エアコン付": ("エアコン",),
    "システムキッチン": ("システムK",),
    "浴室乾燥機": ("浴室乾燥",),
    "モニター付インターホン": ("TVモニタホン", "モニターホン", "インターホン"),
    "リフォーム済": ("リノベーション", "リノベ済", "改装済"),
    "南向き": ("南面", "日当たり良好"),
    "日照良好": ("日当たり", "陽当たり良好"),
    "24時間ゴミ出し可": ("ゴミ出し自由", "24時間ゴミ"),
    "光回線有": ("光回線", "インターネット"),
    "エレベーター": ("EV",),
    "RC造": ("鉄筋コンクリート",),
    "オール電化": ("電化",),
    "床暖房": ("床暖",),
    "駅徒歩5分以内": ("駅近", "徒歩5分"),
    "駅徒歩10分以内": ("徒歩10分",),
    "新築": ("新築物件",),
    "広々リビング": ("広いLDK", "リビング広々"),
    "専用庭": ("庭付",),
    "ルーフバルコニー": ("ルーバル",),
    "角住戸": ("角部屋",),
    "最上階": ("最上階角部屋",),
}


def available() -> Tuple[bool, str]:
    if not DIR.exists():
        return False, "assets/feature_icons が見つかりません"
    count = len(list(DIR.glob("*.png")))
    return bool(count), "物件の特色アイコン %d種" % count


def _catalog() -> Dict[str, Path]:
    """表示名 → ファイル。ファイル名の連番は落とす。"""
    items = {}
    for path in sorted(DIR.glob("*.png")):
        name = re.sub(r"^\d+_", "", path.stem)
        items[name] = path
    return items


def names() -> List[str]:
    return list(_catalog())


def find(word: str) -> Optional[str]:
    """言葉に合うアイコンを1つ返す。無ければ None。

    完全一致 → 言い換え → 部分一致 の順に見る。
    **無いのに似た絵を出さない**（「浴室乾燥機」に「浴室」の絵を出すと嘘になる）。
    """
    word = str(word or "").strip()
    if not word:
        return None
    catalog = _catalog()
    if word in catalog:
        return str(catalog[word])
    for name, alts in ALIASES.items():
        if word == name or word in alts:
            if name in catalog:
                return str(catalog[name])
    for name, path in catalog.items():
        if word in name or name in word:
            return str(path)
    return None


def match_all(words) -> List[Dict[str, str]]:
    """複数の言葉をまとめて引く。見つかったものだけ返す。"""
    found, seen = [], set()
    for word in words or []:
        path = find(word)
        if path and path not in seen:
            seen.add(path)
            found.append({"label": str(word).strip(), "path": path})
    return found


def split(words) -> Tuple[List[str], List[str]]:
    """アイコンがある言葉と、無い言葉に分ける。

    無い言葉をアイコン行に混ぜると、そこだけ絵が抜けて**高さが揃わず崩れる**
    （「駅徒歩7分以内」「3沿線以上利用可」が文字だけで浮いた）。
    絵の無いものは文字のタグに回す。
    """
    with_icon, without = [], []
    for word in words or []:
        name = str(word).strip()
        if not name:
            continue
        (with_icon if find(name) else without).append(name)
    return with_icon, without


def recolor(path: str, color: str = "#c1272d") -> str:
    """アイコンの色を紙面の色に合わせる。

    元は緑一色。紙面の色と合わないと、そこだけ浮いて見える。
    **白（抜きの部分）は残し、それ以外を塗り替える**。塗り替えた版は残す。
    """
    try:
        from PIL import Image
    except ImportError:
        return path
    src = Path(path)
    key = hashlib.md5(("%s|%s" % (src.name, color)).encode("utf-8")).hexdigest()
    out = CACHE / ("%s.png" % key)
    if out.exists():
        return str(out)
    try:
        rgb = color.lstrip("#")
        target = (int(rgb[0:2], 16), int(rgb[2:4], 16), int(rgb[4:6], 16))
        img = Image.open(src).convert("RGB")
        pixels = img.load()
        width, height = img.size
        for y in range(height):
            for x in range(width):
                r, g, b = pixels[x, y]
                # 白に近い画素は抜きの部分。それ以外を塗り替える
                if r > 225 and g > 225 and b > 225:
                    continue
                pixels[x, y] = target
        CACHE.mkdir(parents=True, exist_ok=True)
        img.save(out)
        return str(out)
    except Exception:
        return path


def describe_for_prompt(limit: int = 73) -> str:
    """部隊に渡す一覧。**ここに無い名前を書かせない**ため全部見せる。"""
    items = names()[:limit]
    return ("【使える特色アイコン（この名前で指定すること。無いものは書かない）】\n"
            + "／".join(items))
