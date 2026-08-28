#!/usr/bin/env python3
"""カラー・グラビティの書体を取ってきて、使う文字だけに絞って同梱する。

なぜ要るか:
  ゲームの印象は書体でほぼ決まる。OS標準の sans-serif だと、見出しが
  Helvetica、日本語がヒラギノになり「宇宙もの」の見た目にならない。
  かといって日本語フォントは丸ごとだと 2〜5MB あり、GitHub Pages で配るには重すぎる。

なぜサーバ側サブセットか:
  Google Fonts の css2 API は `text=` を付けると **その文字だけを含むフォント** を返す。
  fonttools を入れなくてよく、ダウンロードした時点で既に小さい。

使う書体（どちらも SIL Open Font License 1.1 ＝ 商用可・埋め込み可・再配布可）:
  Orbitron              … 見出し・数字。角ばった等幅寄りのSF書体
  Zen Kaku Gothic New   … 日本語。角ゴシックで Orbitron と線の太さが合う

  ※ にゃんこアイスは Zen Maru Gothic（丸ゴシック）を使っている。あちらは
    「かわいいアイス屋」なので丸、こちらは「宇宙・機械」なので角。狙って変えている。

★ index.html の文字を書き換えたら、必ずこれを流し直すこと。
  流し忘れると、増やした文字が □（豆腐）になる。

使い方:
    python3 tools/fetch-font.py          # assets/fonts/ に .woff2 を書き出す
    python3 tools/fetch-font.py --check  # 取得せず、いま何文字使っているかだけ見る
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

# (Google Fonts 上の名前, 書き出すファイル名の頭, ウェイト, 日本語を含めるか)
FAMILIES = [
    ("Orbitron", "Orbitron", ["700", "900"], False),
    ("Zen Kaku Gothic New", "ZenKakuGothicNew", ["500", "700"], True),
]
CSS_URL = "https://fonts.googleapis.com/css2?family={fam}:wght@{w}&text={text}"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 常に入れる土台。ここに無い文字は index.html から拾う。
# かなを全部入れておくのは、あとで文言を少し変えたくらいでは豆腐にならないようにするため
# （全かなを足しても数十KBにしかならない）。
ASCII = "".join(chr(c) for c in range(0x20, 0x7F))
BASE_JP = (
    "".join(chr(c) for c in range(0x3041, 0x3097))            # ひらがな
    + "".join(chr(c) for c in range(0x30A1, 0x30FB))          # カタカナ
    + "ー、。・「」！？…‥〜（）［］【】"
    + "±×÷→←↑↓★☆♪✕✓○●◎△▲□■"
)


def screen_text() -> str:
    """**画面に出る文字だけ**を index.html から取り出す。

    ソース全体をなめてはいけない。日本語のコメントを大量に書いているので、
    そのまま拾うと漢字が何百字にもなってフォントが倍近く膨らむ。
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
    """フォントに要る文字。ラテン専用の書体に日本語を頼むと 404 になるので分ける。"""
    if not SRC.exists():
        sys.exit("見つからない: %s" % SRC)
    keep = set(ASCII)
    if with_jp:
        keep |= set(BASE_JP)
        for ch in screen_text():
            code = ord(ch)
            if code < 0x80:
                continue                      # ASCII は済み
            if 0x3000 <= code <= 0x30FF:      # 約物・かな
                keep.add(ch)
            elif 0x4E00 <= code <= 0x9FFF:    # 漢字
                keep.add(ch)
            elif 0xFF00 <= code <= 0xFFEF:    # 全角英数・記号
                keep.add(ch)
            elif 0x2000 <= code <= 0x27BF:    # 各種記号・矢印
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

    jp = used_chars(True)
    kanji = [c for c in jp if 0x4E00 <= ord(c) <= 0x9FFF]
    print("日本語 %d字（うち漢字 %d字）" % (len(jp), len(kanji)))
    print("漢字: %s" % "".join(kanji))
    if args.check:
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    for fam, stem, weights, with_jp in FAMILIES:
        quoted = urllib.parse.quote("".join(used_chars(with_jp)))
        for weight in weights:
            css = fetch(CSS_URL.format(fam=fam.replace(" ", "+"), w=weight, text=quoted)).decode()
            m = re.search(r"src:\s*url\((https://[^)]+)\)", css)
            if not m:
                sys.exit("CSSからフォントURLを取り出せなかった（%s %s）" % (fam, weight))
            data = fetch(m.group(1))
            dest = OUT_DIR / ("%s-%s.woff2" % (stem, weight))
            dest.write_bytes(data)
            total += len(data)
            print("  %s  %.1f KB" % (dest.relative_to(ROOT), len(data) / 1024))

    print("\n合計 %.1f KB" % (total / 1024))
    print("★ index.html の @font-face が上のファイル名を指していることを確認すること")


if __name__ == "__main__":
    main()
