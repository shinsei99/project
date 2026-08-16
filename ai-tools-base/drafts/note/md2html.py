#!/usr/bin/env python3
"""note の投稿画面へ **HTMLとして貼る**ためのクリップボードを作る。

`make_paste.py`（プレーンテキスト）より確実で速い。**noteのエディタは
クリップボードの text/html を読む**ので、h2 / blockquote / ul / a がそのまま
見出し・引用・箇条書き・リンクになる。1行ずつ画面で指定する必要がない。

    python3 md2html.py photo-inpainter        # クリップボードに載る（タイトルも表示）

macOS の AppleScript で «class HTML» としてクリップボードに入れている
（pbcopy はプレーンテキストしか置けない）。
"""
from __future__ import annotations

import html
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
JA = r"　-ヿ一-鿿＀-￯"


def inline(t: str) -> str:
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
               lambda m: f'<a href="{html.escape(m.group(2))}">{html.escape(m.group(1))}</a>', t)
    t = t.replace("**", "").replace("__", "")
    t = re.sub(r"`([^`]+)`", r"\1", t)
    # 記法を落とすと全角の間に半角スペースが残る（絵文字の後ろは残す）
    t = re.sub(rf"(?<=[{JA}]) (?=[{JA}])", "", t)
    return t


def convert(md: str) -> tuple[str, str]:
    title, out, para, lis = "", [], [], []

    def flush_p():
        if para:
            out.append("<p>" + "".join(para) + "</p>")
            para.clear()

    def flush_li():
        if lis:
            out.append("<ul>" + "".join(f"<li>{x}</li>" for x in lis) + "</ul>")
            lis.clear()

    for line in md.splitlines():
        if line.startswith("# ") and not title:
            flush_p(); flush_li()
            title = inline(line[2:].strip())
            continue
        if line.startswith("## "):
            flush_p(); flush_li()
            out.append(f"<h2>{inline(line[3:].strip())}</h2>")
            continue
        if line.startswith("> "):
            flush_p(); flush_li()
            out.append(f"<blockquote><p>{inline(line[2:].strip())}</p></blockquote>")
            continue
        if line.startswith("- "):
            flush_p()
            lis.append(inline(line[2:].strip()))
            continue
        if line.startswith("👉"):
            # 誘導リンクは前の文と繋げず独立した段落にする
            flush_p(); flush_li()
            out.append(f"<p>{inline(line.strip())}</p>")
            continue
        if not line.strip() or line.strip() == "---":
            flush_p(); flush_li()
            continue
        para.append(inline(line.strip()))
    flush_p(); flush_li()
    return title, "".join(out)


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("使い方: python3 md2html.py <原稿名（拡張子なし）>")
    src = HERE / f"{sys.argv[1]}.md"
    title, body = convert(src.read_text(encoding="utf-8"))
    raw = body.encode("utf-8")
    subprocess.run(["osascript", "-e", f"set the clipboard to «data HTML{raw.hex().upper()}»"], check=True)
    print(f"タイトル: {title}")
    print(f"HTML {len(raw)} バイトをクリップボードに載せました（本文欄で ⌘V）")


if __name__ == "__main__":
    main()
