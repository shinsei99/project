#!/usr/bin/env python3
"""Zenn の記事に「毎日22:30」の公開予約を振る。

    ./publish.sh zenn-schedule              いまの予約状況と、振る予定を表示（書き換えない）
    ./publish.sh zenn-schedule --write      実際に published_at を書き込む
    ./publish.sh zenn-schedule 2026-09-01   開始日を指定する（既定は「明日」）

★Zenn の公開日時は**一度設定すると変更できない**（公式ガイドに明記）。
   なので、この道具は次を必ず守る:
   - すでに `published_at` がある記事には**触らない**
   - すでに公開済み（Zenn の API に出ている）記事には**触らない**
   - 既定はドライラン。`--write` を付けたときだけ書き込む
   - 書き込むのはローカルのファイルだけ。**push はしない**（外へ出すのは人の操作）
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import urllib.request
from pathlib import Path

ARTICLES = Path(__file__).resolve().parent.parent.parent / "articles"
TIME_OF_DAY = "22:30"
ZENN_USER = "shinsei99"


def published_slugs() -> set[str]:
    """すでに Zenn に出ているもの（触ってはいけない）。取れなければ空で返す。"""
    url = f"https://zenn.dev/api/articles?username={ZENN_USER}&order=latest"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return {a["slug"] for a in json.load(r).get("articles", [])}
    except Exception as e:            # ネットが無いときは「不明」として全部を保護する
        print(f"  （Zenn の公開状況を取れなかった: {e}）")
        return set()


def front_matter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def main() -> None:
    write = "--write" in sys.argv
    start = None
    for a in sys.argv[1:]:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", a):
            start = dt.date.fromisoformat(a)
    if start is None:
        start = dt.date.today() + dt.timedelta(days=1)

    live = published_slugs()
    todo, held = [], []
    for f in sorted(ARTICLES.glob("*.md")):
        fm = front_matter(f.read_text(encoding="utf-8"))
        if f.stem in live:
            held.append((f.stem, "公開済み"))
        elif "published_at" in fm:
            held.append((f.stem, f"予約済み {fm['published_at']}"))
        elif fm.get("published") != "true":
            todo.append((f, fm, "published: false → true にして予約"))
        else:
            todo.append((f, fm, "予約を振る"))

    print("── 触らないもの ────────────────────────────")
    for s, why in held:
        print(f"  － {s}（{why}）")
    if not held:
        print("  （なし）")

    print(f"── 振る予定（{TIME_OF_DAY}・1日1本・開始 {start}）──")
    if not todo:
        print("  予約を振れる記事がない。先に articles/ へ原稿を置くこと")
        return
    for i, (f, fm, why) in enumerate(todo):
        day = start + dt.timedelta(days=i)
        print(f"  {day} {TIME_OF_DAY}  {f.stem}  … {why}")

    if not write:
        print("\n  ドライラン。書き込むなら --write を付ける")
        print("  ★公開日時は一度きりで変更できない。上の日付をよく見てから実行すること")
        return

    for i, (f, fm, _) in enumerate(todo):
        day = start + dt.timedelta(days=i)
        text = f.read_text(encoding="utf-8")
        head, body = text.split("---\n", 2)[1], text.split("---\n", 2)[2]
        head = re.sub(r"^published:.*$", "published: true", head, flags=re.M)
        head = head.rstrip("\n") + f"\npublished_at: {day} {TIME_OF_DAY}\n"
        f.write_text(f"---\n{head}---\n{body}", encoding="utf-8")
        print(f"  書いた: {f.stem} → {day} {TIME_OF_DAY}")
    print("\n  push はしていない。内容を確かめてから ./publish.sh zenn")


if __name__ == "__main__":
    main()
