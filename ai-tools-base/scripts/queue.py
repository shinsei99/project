#!/usr/bin/env python3
"""ネタ帳の在庫と、3媒体の進み具合を1画面で出す。

    ./publish.sh queue          在庫の残りと、次に書く候補
    ./publish.sh queue --all    在庫を全部並べる

**在庫の台帳は drafts/NETA.md 一本だけ。** ここに書き写して二つ持たない
（二つあると必ず食い違う、というのがこの媒体で何度も書いてきたことなので）。
書き終わったら NETA.md からその行を消す。消えた数が、進んだ数になる。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent      # ai-tools-base/
REPO = ROOT.parent                                  # リポジトリ直下（articles/ がある）

ITEM = re.compile(
    r"^\*\*(\d+)\.\*\*\s*([✅⚠️🔍]+)\s*〔([^〕]+)〕\*\*(.+?)\*\*(?:（(.+?)）)?\s*$", re.M
)
CHAP = re.compile(r"^# ([A-I]\..+)$", re.M)


def stock() -> list[dict]:
    """NETA.md の在庫を、章つきで拾う。"""
    text = (ROOT / "drafts" / "NETA.md").read_text(encoding="utf-8")
    marks = [(m.start(), m.group(1)) for m in CHAP.finditer(text)]
    out = []
    for m in ITEM.finditer(text):
        chapter = next((c for pos, c in reversed(marks) if pos < m.start()), "（章外）")
        out.append(
            {
                "no": int(m.group(1)),
                "ready": m.group(2),
                "kind": m.group(3),
                "title": m.group(4),
                "apps": (m.group(5) or "").replace("`", ""),
                "chapter": chapter,
            }
        )
    return out


def published() -> dict:
    """いま3媒体に出ているものを数える。"""
    works = []
    for f in sorted((ROOT / "content" / "works").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("visibility") == "public":
            labels = {l.get("label") for l in d.get("links", []) or []}
            works.append({"slug": d["slug"], "category": d.get("category"), "links": labels})
    zenn = sorted(p.stem for p in (REPO / "articles").glob("*.md"))
    zenn_draft = [
        p.stem for p in (REPO / "articles").glob("*.md")
        if "published: false" in p.read_text(encoding="utf-8")
    ]
    note = sorted(p.stem for p in (ROOT / "drafts" / "note").glob("*.md"))
    return {"works": works, "zenn": zenn, "zenn_draft": zenn_draft, "note": note}


def main() -> None:
    items = stock()
    pub = published()
    re_works = [w for w in pub["works"] if w["category"] == "realestate"]
    missing_zenn = [w["slug"] for w in re_works if "Zenn" not in w["links"]]
    missing_note = [w["slug"] for w in re_works if "note" not in w["links"]]

    print("── 出したもの ──────────────────────────────")
    print(f"  本体の制作記録   {len(pub['works'])} 本（うち不動産＝3媒体の対象 {len(re_works)}）")
    print(f"  Zenn の原稿      {len(pub['zenn'])} 本（未公開のまま置いてあるもの {len(pub['zenn_draft'])}）")
    print(f"  note の原稿      {len(pub['note'])} 本")
    if missing_zenn or missing_note:
        if missing_zenn:
            print(f"  ⚠️ Zenn がまだ: {', '.join(missing_zenn)}")
        if missing_note:
            print(f"  ⚠️ note がまだ: {', '.join(missing_note)}")
    else:
        print("  ✅ 出したぶんは3媒体そろっている")

    print("── ネタ帳の残り（drafts/NETA.md）──────────")
    both = [i for i in items if i["kind"] == "不動産"]
    print(f"  在庫 {len(items)} 本 … 3媒体に出せる〔不動産〕{len(both)} / 本体だけ {len(items) - len(both)}")
    by_chapter: dict[str, list[dict]] = {}
    for i in items:
        by_chapter.setdefault(i["chapter"], []).append(i)
    for c, xs in by_chapter.items():
        n_re = len([x for x in xs if x["kind"] == "不動産"])
        print(f"    {c[:38]:40} {len(xs):2} 本（不動産 {n_re}）")

    print("── 次に書く候補（すぐ書ける✅・不動産・章がばらけるように）──")
    seen: set[str] = set()
    for i in items:
        if i["kind"] != "不動産" or "✅" not in i["ready"] or i["chapter"] in seen:
            continue
        seen.add(i["chapter"])
        print(f"  {i['no']:>3}. {i['title']}")
        print(f"       {i['chapter'][:2]} / {i['apps'] or '—'}")
        if len(seen) >= 5:
            break

    if "--all" in sys.argv:
        print("── 在庫の全件 ──────────────────────────────")
        for i in items:
            print(f"  {i['no']:>3}. {i['ready']}〔{i['kind']}〕{i['title']}  … {i['apps'] or '—'}")


if __name__ == "__main__":
    main()
