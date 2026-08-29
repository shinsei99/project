#!/usr/bin/env python3
"""ひよこ防衛軍の日本語フォントを取ってきて、使う文字だけに絞って同梱する。

なぜ要るか:
  1. 旧版は Google Fonts の CDN（fonts.googleapis.com）から Kosugi Maru を読んでいた。
     **Capacitor でiOSアプリにすると通信できる保証がなく、機内モードでは豆腐になる。**
     ゲームの見た目が通信状況で変わるのは避けたいので、同梱に切り替えた。
  2. Kosugi Maru はウェイトが 400 しかなく、タイトルの `bold 46px` は
     ブラウザの合成太字（にじむ）だった。Zen Maru Gothic には 500/900 の実ウェイトがある。

なぜサーバ側サブセットか:
  Google Fonts の css2 API は `text=` を付けると **その文字だけを含むフォント** を返す。
  fonttools を入れなくてよく、ダウンロードした時点で既に小さい。

ライセンス:
  Zen Maru Gothic は SIL Open Font License 1.1。商用可・埋め込み可・改変可・**再配布可**。
  → public リポジトリに入れてよい。

使い方:
    python3 tools/fetch-font.py          # assets/fonts/ に .woff2 を書き出す
    python3 tools/fetch-font.py --check  # 取得せず、いま何文字使っているかだけ見る

**画面に出る文字を書き換えたら、必ずこれを流し直すこと。**
流し忘れると、増やした文字が □（豆腐）になる。
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# ★実体は www/ のほう（Capacitor と集合ゲームが読むのはここ）。
#   直下の index.html / js/ は同じ内容の控え。文言を変えたら両方そろえること。
SRC_ROOT = ROOT / "www"
# 画面に文字を出すのはこの本数（描画は canvas なので DOM には文字が無い）
SOURCES = [
    SRC_ROOT / "index.html",
    SRC_ROOT / "game.js",
    SRC_ROOT / "js" / "ui.js",
    SRC_ROOT / "js" / "render.js",
    SRC_ROOT / "js" / "entities.js",
    SRC_ROOT / "js" / "upgrades.js",
    SRC_ROOT / "js" / "save.js",
]
OUT_DIR = SRC_ROOT / "assets" / "fonts"

# ★2026-08-29: 丸ゴシックをやめ、角ゴシック＋Orbitron へ（画面をネオンにしたため）
FAMILIES = [
    ("Zen Kaku Gothic New", ["500", "900"], "ZenKakuGothicNew", False),
    ("Orbitron",            ["700", "900"], "Orbitron",         True),   # True = ASCII だけ
]
CSS_URL = "https://fonts.googleapis.com/css2?family={fam}:wght@{w}&text={text}"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 常に入れる土台。ここに無い文字はソースから拾う。
# かなを全部入れておくのは、あとで文言を少し変えたくらいでは豆腐にならないようにするため。
BASE = (
    "".join(chr(c) for c in range(0x20, 0x7F))                  # ASCII
    + "".join(chr(c) for c in range(0x3041, 0x3097))            # ひらがな
    + "".join(chr(c) for c in range(0x30A1, 0x30FB))            # カタカナ
    + "ー、。・「」！？…‥〜（）［］【】｜"
    + "¥￥±×÷→←↑↓★☆♪♥♡✕✓○●◎△▲□■"
)


def screen_text() -> str:
    """**画面に出る文字だけ**を取り出す。

    ソース全体をなめてはいけない。日本語のコメントを大量に書いているので、
    そのまま拾うと漢字が数百字になりフォントが倍以上に膨らむ。
    拾うのは「HTMLのテキスト」と「JSの文字列リテラル」だけにする。
    """
    pieces: list[str] = []
    for path in SOURCES:
        if not path.exists():
            continue
        raw = path.read_text(encoding="utf-8")
        if path.suffix == ".html":
            body = re.sub(r"<style[\s\S]*?</style>", " ", raw)
            scripts = re.findall(r"<script[^>]*>([\s\S]*?)</script>", body)
            html = re.sub(r"<script[\s\S]*?</script>", " ", body)
            pieces.append(re.sub(r"<[^>]+>", " ", html))   # タグを外した表示テキスト
            srcs = scripts
        else:
            srcs = [raw]

        for src in srcs:
            src = re.sub(r"/\*[\s\S]*?\*/", " ", src)                # ブロックコメント
            src = re.sub(r"(^|[^:])//.*$", r"\1 ", src, flags=re.M)  # 行コメント（https:// は残す）
            pieces += re.findall(r"'([^'\\\n]*)'", src)
            pieces += re.findall(r'"([^"\\\n]*)"', src)
            pieces += re.findall(r"`([^`\\]*)`", src)
    return " ".join(pieces)


def used_chars() -> set[str]:
    """フォントに要る文字の集合。土台（かな・ASCII）＋ 画面に出る文字。"""
    keep = set(BASE)
    for ch in screen_text():
        code = ord(ch)
        if code < 0x80:
            continue                      # ASCII は BASE 済み
        if 0x3000 <= code <= 0x30FF:      # 約物・かな
            keep.add(ch)
        elif 0x4E00 <= code <= 0x9FFF:    # 漢字
            keep.add(ch)
        elif 0xFF00 <= code <= 0xFFEF:    # 全角英数・記号
            keep.add(ch)
        elif 0x2000 <= code <= 0x27BF:    # 各種記号・矢印
            keep.add(ch)
    return keep


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="取得せず文字数だけ見る")
    args = ap.parse_args()

    chars = sorted(used_chars())
    kanji = [c for c in chars if 0x4E00 <= ord(c) <= 0x9FFF]
    print("使用文字 %d字（うち漢字 %d字）" % (len(chars), len(kanji)))
    print("漢字: %s" % "".join(kanji))
    if args.check:
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ascii_only = "".join(c for c in chars if ord(c) < 0x80)
    for family, weights, stem, only_ascii in FAMILIES:
        quoted = urllib.parse.quote(ascii_only if only_ascii else "".join(chars))
        for weight in weights:
            css = fetch(CSS_URL.format(fam=family.replace(" ", "+"), w=weight, text=quoted)).decode()
            mm = re.search(r"src:\s*url\((https://[^)]+)\)", css)
            if not mm:
                sys.exit("CSSからフォントURLを取り出せなかった（%s weight=%s）" % (family, weight))
            data = fetch(mm.group(1))
            dest = OUT_DIR / ("%s-%s.woff2" % (stem, weight))
            dest.write_bytes(data)
            print("  %s  %.1f KB" % (dest.relative_to(ROOT), len(data) / 1024))

    print("\n★ style.css の @font-face が上のファイルを指していることを確認すること")


if __name__ == "__main__":
    main()
