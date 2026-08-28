#!/usr/bin/env python3
"""にゃんこ大脱出の日本語フォントを取ってきて、使う文字だけに絞って同梱する。

（にゃんこアイスの tools/fetch-font.py と同じ作り。パスだけ違う）

なぜ要るか:
  ゲームの印象は書体でほぼ決まる。OS標準の sans-serif は日本語がヒラギノ／游ゴシックになり、
  「かわいいネコのゲーム」の見た目にならない。かといって日本語フォントは丸ごとだと 2〜5MB あり、
  ゲーム1本に同梱するには重すぎる。

なぜサーバ側サブセットか:
  Google Fonts の css2 API は `text=` を付けると **その文字だけを含むフォント** を返す。
  fonttools を入れなくてよく、ダウンロードした時点で既に小さい（全かな＋ASCII＋漢字で 50KB 前後）。

ライセンス:
  Zen Maru Gothic は SIL Open Font License 1.1。商用可・埋め込み可・改変可・**再配布可**。
  Google Fonts は API 経由の自動取得を認めている。→ public リポジトリに入れてよい。

使い方:
    python3 tools/fetch-font.py          # www/assets/fonts/ に .woff2 を書き出す
    python3 tools/fetch-font.py --check  # 取得せず、いま何文字使っているかだけ見る

**www/index.html の文字を書き換えたら、必ずこれを流し直すこと。**
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
SRC = ROOT / "www" / "index.html"
OUT_DIR = ROOT / "www" / "assets" / "fonts"

FAMILY = "Zen Maru Gothic"
WEIGHTS = ["500", "900"]          # 本文と、スコア・見出しの極太
CSS_URL = "https://fonts.googleapis.com/css2?family={fam}:wght@{w}&text={text}"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 常に入れる土台。ここに無い文字は index.html から拾う。
# かなを全部入れておくのは、あとで文言を少し変えたくらいでは豆腐にならないようにするため
# （全かなを足しても 20KB 程度にしかならない）。
BASE = (
    "".join(chr(c) for c in range(0x20, 0x7F))                  # ASCII
    + "".join(chr(c) for c in range(0x3041, 0x3097))            # ひらがな
    + "".join(chr(c) for c in range(0x30A1, 0x30FB))            # カタカナ
    + "ー、。・「」！？…‥〜（）［］【】"
    + "¥￥±×÷→←↑↓★☆♪♥♡✕✓○●◎△▲□■"
)


def screen_text() -> str:
    """**画面に出る文字だけ**を index.html から取り出す。

    ソース全体をなめてはいけない。日本語のコメントを大量に書いているので、
    そのまま拾うと漢字が 300字を超えてフォントが倍近く膨らむ（実測 92KB → 46KB）。
    拾うのは「HTMLのテキスト」と「JSの文字列リテラル」だけにする。
    """
    raw = SRC.read_text(encoding="utf-8")
    body = re.sub(r"<style[\s\S]*?</style>", " ", raw)

    scripts = re.findall(r"<script[^>]*>([\s\S]*?)</script>", body)
    html = re.sub(r"<script[\s\S]*?</script>", " ", body)
    pieces = [re.sub(r"<[^>]+>", " ", html)]      # タグを外した表示テキスト

    for src in scripts:
        src = re.sub(r"/\*[\s\S]*?\*/", " ", src)             # ブロックコメント
        src = re.sub(r"(^|[^:])//.*$", r"\1 ", src, flags=re.M)  # 行コメント（https:// は残す）
        pieces += re.findall(r"'([^'\\\n]*)'", src)
        pieces += re.findall(r'"([^"\\\n]*)"', src)
        pieces += re.findall(r"`([^`\\]*)`", src)
    return " ".join(pieces)


def used_chars() -> set[str]:
    """フォントに要る文字の集合。土台（かな・ASCII）＋ 画面に出る文字。"""
    if not SRC.exists():
        sys.exit("見つからない: %s" % SRC)
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
    quoted = urllib.parse.quote("".join(chars))
    for weight in WEIGHTS:
        css = fetch(CSS_URL.format(fam=FAMILY.replace(" ", "+"), w=weight, text=quoted)).decode()
        m = re.search(r"src:\s*url\((https://[^)]+)\)", css)
        if not m:
            sys.exit("CSSからフォントURLを取り出せなかった（weight=%s）" % weight)
        data = fetch(m.group(1))
        dest = OUT_DIR / ("ZenMaruGothic-%s.woff2" % weight)
        dest.write_bytes(data)
        print("  %s  %.1f KB" % (dest.relative_to(ROOT), len(data) / 1024))

    print("\n★ www/index.html の @font-face が上のファイルを指していることを確認すること")


if __name__ == "__main__":
    main()
