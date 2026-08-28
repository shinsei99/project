#!/usr/bin/env python3
"""サイボーグ防衛軍の書体を取ってきて、使う文字だけに絞って同梱する。

なぜ要るか:
  ゲームの印象は書体でほぼ決まる。OS標準の sans-serif だと、英字は Helvetica、
  日本語はヒラギノ／游ゴシックになり、「サイバーな戦場」の見た目にならない。
  かといって日本語フォントは丸ごとだと 2〜5MB あり、GitHub Pages に置くには重い。

なぜサーバ側サブセットか:
  Google Fonts の css2 API は `text=` を付けると **その文字だけを含むフォント** を返す。
  fonttools を入れなくてよく、ダウンロードした時点で既に小さい。

2書体を使い分ける:
  Orbitron            … 数字・英字（スコア・WAVE・×2 などの見出し）。角ばった SF 書体
  Zen Kaku Gothic New … 日本語（説明・バナー・フロートテキスト）

ライセンス:
  どちらも SIL Open Font License 1.1。商用可・埋め込み可・改変可・**再配布可**。
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

# (Google Fonts のファミリ名, 出力ファイル名の頭, ウェイト, 日本語を含めるか)
FAMILIES = [
    ("Orbitron", "Orbitron", ["700", "900"], False),
    ("Zen Kaku Gothic New", "ZenKakuGothicNew", ["500", "900"], True),
]
CSS_URL = "https://fonts.googleapis.com/css2?family={fam}:wght@{w}&text={text}"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 常に入れる土台。ここに無い文字は index.html から拾う。
# かなを全部入れておくのは、あとで文言を少し変えたくらいでは豆腐にならないようにするため。
ASCII = "".join(chr(c) for c in range(0x20, 0x7F))
BASE_JP = (
    "".join(chr(c) for c in range(0x3041, 0x3097))            # ひらがな
    + "".join(chr(c) for c in range(0x30A1, 0x30FB))          # カタカナ
    + "ー、。・「」！？…〜（）［］【】"
    # 記号。× ÷ → ◈ は Orbitron に無いので**日本語側に必ず入れる**
    # （index.html の font 指定が Orbitron → ZenKaku の順なので、ここが受け皿になる）
    + "±×÷→←↑↓★☆♪♥○●◎△▲□■◈"
)


def screen_text() -> str:
    """**画面に出る文字だけ**を www/index.html から取り出す。

    ソース全体をなめてはいけない。日本語のコメントを大量に書いているので、
    そのまま拾うと漢字が数百字になりフォントが倍近く膨らむ。
    拾うのは「HTMLのテキスト」と「JSの文字列リテラル」だけにする。
    """
    raw = SRC.read_text(encoding="utf-8")
    body = re.sub(r"<style[\s\S]*?</style>", " ", raw)

    scripts = re.findall(r"<script[^>]*>([\s\S]*?)</script>", body)
    html = re.sub(r"<script[\s\S]*?</script>", " ", body)
    pieces = [re.sub(r"<[^>]+>", " ", html)]      # タグを外した表示テキスト

    for src in scripts:
        src = re.sub(r"/\*[\s\S]*?\*/", " ", src)                # ブロックコメント
        src = re.sub(r"(^|[^:])//.*$", r"\1 ", src, flags=re.M)  # 行コメント（https:// は残す）
        pieces += re.findall(r"'([^'\\\n]*)'", src)
        pieces += re.findall(r'"([^"\\\n]*)"', src)
        pieces += re.findall(r"`([^`\\]*)`", src)
    return " ".join(pieces)


def used_chars(with_jp: bool) -> list[str]:
    if not SRC.exists():
        sys.exit("見つからない: %s" % SRC)
    keep = set(ASCII)
    if with_jp:
        keep |= set(BASE_JP)
    for ch in screen_text():
        code = ord(ch)
        if code < 0x80:
            continue                      # ASCII は土台に入っている
        if not with_jp:
            continue                      # 英字用の書体に日本語は入れない
        if (0x3000 <= code <= 0x30FF or 0x4E00 <= code <= 0x9FFF
                or 0xFF00 <= code <= 0xFFEF or 0x2000 <= code <= 0x27BF):
            keep.add(ch)
    return sorted(keep)


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="取得せず文字数だけ見る")
    args = ap.parse_args()

    total = 0
    for family, stem, weights, with_jp in FAMILIES:
        chars = used_chars(with_jp)
        kanji = [c for c in chars if 0x4E00 <= ord(c) <= 0x9FFF]
        print("%s: %d字（うち漢字 %d字）" % (family, len(chars), len(kanji)))
        if kanji:
            print("  漢字: %s" % "".join(kanji))
        if args.check:
            continue

        OUT_DIR.mkdir(parents=True, exist_ok=True)
        quoted = urllib.parse.quote("".join(chars))
        for weight in weights:
            css = fetch(CSS_URL.format(fam=family.replace(" ", "+"), w=weight, text=quoted)).decode()
            m = re.search(r"src:\s*url\((https://[^)]+)\)", css)
            if not m:
                sys.exit("CSSからフォントURLを取り出せなかった（%s %s）" % (family, weight))
            data = fetch(m.group(1))
            dest = OUT_DIR / ("%s-%s.woff2" % (stem, weight))
            dest.write_bytes(data)
            total += len(data)
            print("  %s  %.1f KB" % (dest.relative_to(ROOT), len(data) / 1024))

    if not args.check:
        print("\n合計 %.1f KB" % (total / 1024))
        print("★ www/index.html の @font-face が上のファイルを指していることを確認すること")


if __name__ == "__main__":
    main()
