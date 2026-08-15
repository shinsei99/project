"""アイテム: 手元の素材フォルダ（`assets/`）から画像を探す

なぜ「自動ダウンロード」にしないか — 各サイトの規約を確認した結果（2026-08-14）:

| サイト | 商用 | クレジット | 自動収集 |
|---|---|---|---|
| Material Symbols（Google） | 可 | 不要 | **可**（Apache-2.0）→ pictograms.py が自動取得 |
| ソコスト soco-st.com | 可 | 不要 | 直リンク禁止。素材集への転用・AI学習も禁止 |
| いらすとや | 可 | 不要 | **1制作物21点以上は有償**。自動化と相性が悪い |
| ぱくたそ | 可 | 原則不要 | **自動収集を明確に禁止**（違約金 1点3万円/日・上限30万円） |
| ICOOON MONO | 可 | 不要 | 再配布禁止・直リンク非推奨 |

つまり **オープンライセンスのアイコンだけ自動取得し、それ以外は人が手で置く**。
置いてもらえば、各部隊はここから探して使う。規約も守れて、素材の幅も広がる。

置き方:
    agent-platform/assets/ に入れるだけ（サブフォルダ可）
    例: assets/イラスト/自転車_注意.png
        assets/写真/マンション外観.jpg
    ファイル名とフォルダ名がそのまま検索語になる。日本語のままでよい。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

NAME = "assets"
LABEL = "手元の素材フォルダ"
DESCRIPTION = ("assets/ に置いたイラスト・写真を名前で探して使う。"
               "いらすとや・ソコスト・ぱくたそ等の素材はここに入れる（規約上、自動取得しない）")

ROOT = Path(__file__).resolve().parent.parent / "assets"
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif")


# 人がダウンロードして assets/ に置けるサイト（2026-08-14 規約確認）
# ぱくたそは自動収集禁止＋違約金規定があるため候補から外している
SOURCES = [
    ("標準案内用図記号（JIS Z8210）", "公式ピクトグラム",
     "https://www.ecomo.or.jp/barrierfree/pictogram/picto_top2025.html",
     "誰でも自由に使用可。商標・意匠登録は不可。掲示物には第一候補"),
    ("いらすとや", "イラスト全般", "https://www.irasutoya.com", "1制作物21点以上は有償"),
    ("ソコスト", "シンプルなイラスト・人物", "https://soco-st.com", "AI学習・素材集への転用は不可"),
    ("ICOOON MONO", "モノトーンのアイコン", "https://icooon-mono.com", "再配布不可"),
    ("SILHOUETTE DESIGN", "シルエット素材", "https://kage-design.com", "加工・色変更可"),
    ("Pixabay", "写真・イラスト・動画", "https://pixabay.com", "クレジット不要"),
    ("写真AC", "日本の写真", "https://www.photo-ac.com", "無料登録が必要"),
    ("Pexels", "動画・写真", "https://www.pexels.com/ja-jp/videos/", "商用可"),
    ("Mixkit", "動画", "https://mixkit.co", "全素材が商用可"),
    ("魔王魂", "BGM・効果音", "https://maou.audio", "動画のBGM向き"),
    ("DOVA-SYNDROME", "BGM", "https://dova-s.jp", "動画のBGM向き"),
]


def sources_for_prompt() -> str:
    """素材が足りないときに「どこから取ればよいか」を部隊に教える。"""
    return "\n".join("- %s（%s）%s ※%s" % (name, kind, url, note)
                     for name, kind, url, note in SOURCES)


def available() -> Tuple[bool, str]:
    files = _all_files()
    if not files:
        return True, "素材0点（assets/ に入れると使えます）"
    return True, "素材%d点" % len(files)


def _all_files() -> List[Path]:
    if not ROOT.exists():
        return []
    return sorted(p for p in ROOT.rglob("*")
                  if p.is_file() and p.suffix.lower() in IMAGE_EXT
                  and not p.name.startswith("."))


def catalog(limit: int = 200) -> List[Dict[str, Any]]:
    """素材の一覧。部隊に「何が使えるか」を見せるため。"""
    items = []
    for path in _all_files()[:limit]:
        items.append({"name": path.stem,
                      "folder": str(path.parent.relative_to(ROOT)) if path.parent != ROOT else "",
                      "path": str(path),
                      "ext": path.suffix.lower().lstrip(".")})
    return items


def find(keywords, limit: int = 8) -> List[Path]:
    """キーワードに合う素材を探す。

    ファイル名とフォルダ名の両方を見る。日本語のまま部分一致で拾う
    （形態素解析まではしない。素材名は人が付けるので単純一致で足りる）。
    """
    if isinstance(keywords, str):
        keywords = [keywords]
    words = [str(k).strip().lower() for k in keywords if str(k).strip()]
    if not words:
        return []

    scored = []
    for path in _all_files():
        haystack = ("%s/%s" % (path.parent.name, path.stem)).lower()
        score = sum(1 for w in words if w in haystack)
        if score:
            scored.append((score, path))
    scored.sort(key=lambda x: (-x[0], str(x[1])))
    return [path for _, path in scored[:limit]]


def describe_for_prompt(limit: int = 40) -> str:
    """部隊のプロンプトに差し込む「使える素材」の一覧。"""
    items = catalog(limit)
    if not items:
        return "（素材フォルダは空です）"
    lines = []
    for item in items:
        label = "%s/%s" % (item["folder"], item["name"]) if item["folder"] else item["name"]
        lines.append("- %s" % label)
    return "\n".join(lines)
