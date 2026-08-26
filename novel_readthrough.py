#!/usr/bin/env python3
"""小説続編『不動産屋、つくってます。』の通し読みファイルを作る。

  ./novel_readthrough.py 20        # 第1話〜第20話 → 通し読み_01-20話.txt
  ./novel_readthrough.py 10 15 20  # 3本まとめて作り直す
  ./novel_readthrough.py           # 既にある通し読みファイルを全部作り直す

原稿は git 管理外（GoogleDrive）。本文には手を入れず、各話 .txt をそのまま連結する。
話の先頭にある「（第一部　…）」は原稿側に入っているので、生成側では足さない
（足すと二重になる。2026-08-25 に実際にやらかした）。
"""
import glob
import os
import re
import sys

DIR = os.path.expanduser(
    "~/Library/CloudStorage/GoogleDrive-daikyocorp.s@gmail.com/"
    "マイドライブ/新誠プロパティ/新誠不動産/続編_カクヨム用"
)
SEP = "═" * 40
HEAD = "『不動産屋、つくってます。』〜街の不動産屋が、その仕事に名前をつけるまで〜\nSHINSEI"
NOTE = "※原稿は未投稿。カクヨム投稿時は本ファイルではなく各話の .txt を使うこと。"


def episodes():
    """[(話数, 表示タイトル, パス, 本文, 字数), ...] を話数順で返す。"""
    out = []
    for path in sorted(glob.glob(os.path.join(DIR, "[0-3][0-9]_*.txt"))):
        name = os.path.basename(path)[:-4]
        parts = name.split("_", 2)
        if len(parts) != 3 or parts[0] == "00":   # 00_作品情報.txt など本編でないもの
            continue
        num, chapter, title = parts
        body = open(path, encoding="utf-8").read()
        out.append((int(num), f"第{int(num)}話　{chapter}「{title}」", path, body, len(body)))
    return out


def build(upto, eps):
    picked = [e for e in eps if e[0] <= upto]
    total = sum(e[4] for e in picked)
    lines = [HEAD, "", f"通し読み用（第1話〜第{upto}話）", "", "【目次】", ""]
    lines += [f"　{t}　{n:,}字" for _, t, _, _, n in picked]
    lines += ["", f"　合計 {total:,}字（全{len(eps)}話中の第1話〜第{upto}話）", "", NOTE, "", ""]
    text = "\n".join(lines)
    for _, title, _, body, _ in picked:
        text += f"\n{SEP}\n{title}\n{SEP}\n\n{body.strip()}\n\n"
    return text.rstrip("\n") + "\n", total


def main():
    eps = episodes()
    if not eps:
        sys.exit(f"原稿が見つからない: {DIR}")
    targets = [int(a) for a in sys.argv[1:]]
    if not targets:
        targets = sorted(
            int(re.search(r"01-(\d+)話", f).group(1))
            for f in glob.glob(os.path.join(DIR, "通し読み_01-*話.txt"))
        )
    for upto in targets:
        text, total = build(upto, eps)
        out = os.path.join(DIR, f"通し読み_01-{upto:02d}話.txt")
        open(out, "w", encoding="utf-8").write(text)
        print(f"{os.path.basename(out)}  第1話〜第{upto}話  {total:,}字")
    print(f"（全{len(eps)}話の合計 {sum(e[4] for e in eps):,}字）")


if __name__ == "__main__":
    main()
