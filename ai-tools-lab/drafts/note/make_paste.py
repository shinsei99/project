#!/usr/bin/env python3
"""note の投稿画面へ貼るテキストを、このフォルダの原稿(.md)から作る。

**note はMarkdownが効かない。** 貼り付けた `##` や `**` はそのまま文字として出る。
そこで記法を落とし、見出し・引用・リンクは「貼ったあとに画面側で指定する」前提の
一覧を先頭に付ける。

    python3 make_paste.py            # 全部つくる → paste/*.txt

Zenn 側（drafts/zenn/paste/）と同じ考え方だが、あちらはMarkdownがそのまま効くので
frontmatter を剥がすだけ。note はここまでやらないと貼れない。
"""
from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "paste"


def strip_inline(text: str) -> str:
    """太字・リンクなどの記法を落として、読める日本語だけにする"""
    # [表示文字](URL) → 表示文字 URL （noteのリンク機能で貼り直す前提）
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 \2", text)
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # 記法を落とすと「〜します。 空を〜」のように全角の間に半角スペースが残る。日本語では余分なので詰める。
    # 対象は仮名・漢字・全角記号だけ（絵文字まで含めると「👉 制作記録」の空きまで詰まる）
    ja = r"　-ヿ一-鿿＀-￯"
    text = re.sub(rf"(?<=[{ja}]) (?=[{ja}])", "", text)
    return text


def convert(md: str) -> tuple[str, list[str], list[str], str]:
    """本文 → (タイトル, 見出し一覧, 引用一覧, 貼り付け本文)

    **原稿の折り返しは1行に繋ぐ。** noteは貼り付けた改行をそのまま行送りにするので、
    原稿の見た目のまま貼ると、スマホで不自然な位置に改行が入る。
    """
    title = ""
    headings: list[str] = []
    quotes: list[str] = []
    body: list[str] = []
    para: list[str] = []  # 折り返しを繋ぐための一時置き場

    def flush() -> None:
        if para:
            body.append("".join(para))  # 日本語なので隙間を入れずに連結する
            para.clear()

    for line in md.splitlines():
        if line.startswith("# ") and not title:
            flush()
            title = strip_inline(line[2:].strip())
            continue
        if line.startswith("## "):
            flush()
            h = strip_inline(line[3:].strip())
            headings.append(h)
            body.append("")
            body.append(h)
            continue
        if line.startswith("> "):
            flush()
            q = strip_inline(line[2:].strip())
            quotes.append(q)
            body.append(q)
            continue
        if line.startswith("- "):
            flush()
            body.append("・" + strip_inline(line[2:].strip()))
            continue
        if line.startswith("👉"):
            # 誘導リンクは前の文と繋げず、必ず独立した行にする
            flush()
            body.append(strip_inline(line).strip())
            continue
        if line.strip() == "---":
            flush()
            body.append("")
            continue
        if not line.strip():
            flush()
            body.append("")
            continue
        para.append(strip_inline(line).strip())
    flush()

    # 連続する空行を1つに詰める（記法を落とすと空きが増えるため）
    packed: list[str] = []
    for ln in body:
        if not ln.strip() and packed and not packed[-1].strip():
            continue
        packed.append(ln.rstrip())
    return title, headings, quotes, "\n".join(packed).strip() + "\n"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for src in sorted(HERE.glob("*.md")):
        title, headings, quotes, body = convert(src.read_text(encoding="utf-8"))
        head = [
            "── noteの投稿画面で指定する ──────────────",
            f"タイトル: {title}",
            "",
            "見出しにする行（貼り付け後、その行を選んで「見出し」を押す）:",
            *[f"  ・{h}" for h in headings],
        ]
        if quotes:
            head += [
                "",
                "引用にする行（同じく、選んで「引用」を押す）:",
                *[f"  ・{q}" for q in quotes],
            ]
        head += [
            "",
            "リンク: 本文末尾のURLは、直前の文字を選んで note のリンク機能で貼り直す",
            "──────────────────────────────────",
            "▼ ここから下をすべて本文欄に貼り付け",
            "",
        ]
        dest = OUT / (src.stem + ".txt")
        dest.write_text("\n".join(head) + "\n" + body, encoding="utf-8")
        print(f"{dest.relative_to(HERE.parent.parent)}  （見出し {len(headings)}／引用 {len(quotes)}）")


if __name__ == "__main__":
    main()
