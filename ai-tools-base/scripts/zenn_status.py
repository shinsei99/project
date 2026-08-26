#!/usr/bin/env python3
"""Zenn の記事が、公開済み・予約中・下書きのどれかを出す。

**予約中の記事は、Zenn の公開API（記事一覧）には出ない。** 公開日時が来るまでは
「未反映」と同じ見え方になるので、`published_at` を読んで区別する。
これを見ずに「上限に当たった」と判断すると、正常な予約を事故と読み違える
（2026-08-26 に実際に誤判定した）。
"""
from __future__ import annotations

import datetime as dt
import json
import re
import urllib.request
from pathlib import Path

ARTICLES = Path(__file__).resolve().parent.parent.parent / "articles"
ZENN_USER = "shinsei99"


def live() -> set[str]:
    url = f"https://zenn.dev/api/articles?username={ZENN_USER}&order=latest"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return {a["slug"] for a in json.load(r).get("articles", [])}
    except Exception as e:
        print(f"  （Zenn の公開状況を取れなかった: {e}）")
        return set()


def main() -> None:
    pub = live()
    now = dt.datetime.now()
    rows = []
    for f in sorted(ARTICLES.glob("*.md")):
        head = f.read_text(encoding="utf-8").split("---")[1]
        fm = dict(
            (m.group(1), m.group(2).strip())
            for m in re.finditer(r"^(\w+): (.+)$", head, re.M)
        )
        at = fm.get("published_at", "")
        when = None
        if at:
            try:
                when = dt.datetime.strptime(at, "%Y-%m-%d %H:%M")
            except ValueError:
                try:
                    when = dt.datetime.strptime(at, "%Y-%m-%d")
                except ValueError:
                    when = None
        if f.stem in pub:
            rows.append(("✅ 公開済み", f.stem, at))
        elif fm.get("published") != "true":
            rows.append(("－  下書き", f.stem, ""))
        elif when and when > now:
            rows.append(("⏳ 予約中  ", f.stem, at))
        elif when and when <= now:
            rows.append(("⚠️ 時刻を過ぎたのに未反映", f.stem, at))
        else:
            rows.append(("⚠️ 未反映（投稿数の上限かも）", f.stem, ""))

    for state, slug, at in sorted(rows, key=lambda r: (r[2] or "0", r[1])):
        print(f"  {state} {slug}" + (f"  {at}" if at else ""))

    n_pub = len([r for r in rows if r[0].startswith("✅")])
    n_res = len([r for r in rows if r[0].startswith("⏳")])
    n_bad = len([r for r in rows if r[0].startswith("⚠️")])
    print(f"  → 公開済み {n_pub} / 予約中 {n_res} / 要確認 {n_bad}")
    if n_res:
        nxt = min(r[2] for r in rows if r[0].startswith("⏳"))
        print(f"  次の公開: {nxt}")


if __name__ == "__main__":
    main()
