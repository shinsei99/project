#!/usr/bin/env python3
"""公開済みの Zenn / note のURLを、本体の制作記録（links）へ入れる。

    ./publish.sh links            何が入るかだけ出す（ドライラン）
    ./publish.sh links --write    実際に書き込む

**本体・Zenn・note の3点で1本**という決まりなので、`links` が埋まるまでが1本。
`npm run validate` はここが欠けていると転載⚠️を出す。

日次で回すようになって、これを手でやると毎日の作業になった（記事は毎晩1本出る）ので
機械にした。**入れるのは「実際に公開されたもの」だけ**:

- Zenn … 公開APIに出ているものだけ（**予約中はAPIに出ない**ので入らない。これが正しい。
          公開前にURLを載せると、詳細ページからリンク切れへ飛ぶ）
- note … `drafts/.note_posted.json`（投稿した実績。URLはnoteが採番したもの）

**slug が一致するものだけを見る。** 昔の記事は本体の slug と Zenn の slug が違う
（例: 本体 agent-platform ↔ Zenn gemini-api-traps）が、それらは既に手で入っている。
日次で書くものは3媒体とも同じ slug になる。
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
WORKS = ROOT / "content" / "works"
POSTED = ROOT / "drafts" / ".note_posted.json"
ZENN_USER = "shinsei99"


def zenn_live() -> set[str]:
    url = f"https://zenn.dev/api/articles?username={ZENN_USER}&order=latest"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return {a["slug"] for a in json.load(r).get("articles", [])}
    except Exception as e:
        print(f"  （Zenn の公開状況を取れなかった: {e}）")
        return set()


def main() -> None:
    write = "--write" in sys.argv
    live = zenn_live()
    posted = json.loads(POSTED.read_text(encoding="utf-8")) if POSTED.exists() else {}
    changed = 0

    for f in sorted(WORKS.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("visibility") != "public":
            continue
        slug = d["slug"]
        links = d.get("links") or []
        labels = {l.get("label") for l in links}
        add = []

        if slug in live and "Zenn" not in labels:
            add.append({
                "label": "Zenn",
                "url": f"https://zenn.dev/{ZENN_USER}/articles/{slug}",
                "note": "技術的な詳細（コード付き）",
            })
        if slug in posted and "note" not in labels:
            add.append({
                "label": "note",
                "url": posted[slug],
                "note": "技術用語なしの読み物",
            })
        if not add:
            continue

        changed += 1
        for a in add:
            print(f"  {'＋' if write else '（予定）'} {slug} … {a['label']} {a['url']}")
        if write:
            d["links"] = links + add
            f.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if not changed:
        print("  入れるものは無い（3媒体そろっている、または公開前）")
    elif not write:
        print(f"\n  {changed} 本ぶん。実際に入れるなら ./publish.sh links --write")


if __name__ == "__main__":
    main()
