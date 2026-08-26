#!/usr/bin/env python3
"""note に何本出ていて、あと何本残っているかを出す。

公開済みの判定は **note の公開API × 原稿のタイトル** で突き合わせる
（`drafts/.note_posted.json` は投稿した端末にしか無いため、それだけでは足りない）。
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTE_DIR = ROOT / "drafts" / "note"
ORDER = ROOT / "drafts" / "zenn_order.txt"
USER = "shinsei99"

sys.path.insert(0, str(NOTE_DIR))


def live_titles() -> set[str]:
    out, page = set(), 1
    while page <= 10:
        url = f"https://note.com/api/v2/creators/{USER}/contents?kind=note&page={page}"
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                d = json.load(r)["data"]
        except Exception as e:
            print(f"  （note の公開状況を取れなかった: {e}）")
            return out
        out |= {c["name"] for c in d.get("contents", [])}
        if d.get("isLastPage"):
            break
        page += 1
    return out


def main() -> None:
    import md2html
    titles = live_titles()
    order = []
    if ORDER.exists():
        order = [x.strip() for x in ORDER.read_text(encoding="utf-8").splitlines()
                 if x.strip() and not x.startswith("#")]

    rows = []
    for f in sorted(NOTE_DIR.glob("*.md")):
        try:
            title, _ = md2html.convert(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows.append((f.stem, title, title in titles))

    done = [r for r in rows if r[2]]
    todo = [r for r in rows if not r[2]]
    print(f"  原稿 {len(rows)} 本 … 公開済み {len(done)} / 未投稿 {len(todo)}")

    if todo:
        queue = [n for n in order if any(n == r[0] for r in todo)]
        queue += [r[0] for r in todo if r[0] not in order]
        print(f"  次に出るもの: {queue[0] if queue else '—'}")
        print(f"  残りの順番: {' → '.join(queue[:5])}" + (" …" if len(queue) > 5 else ""))
    else:
        print("  ✅ 全部出た")


if __name__ == "__main__":
    main()
