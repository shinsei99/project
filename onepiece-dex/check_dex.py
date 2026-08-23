"""
図鑑の整合性を検査する。build_dex.py のあとに流す。

**「取れなかった」と「そもそも公式に無い」を混ぜない**ための道具。
ポケカ図鑑で、画像が無い376枚の内訳を突き止めるのに一番時間がかかった。
ワンピは公式1本なので、欠けたら公式側の不備＝そのまま記録して残す。

使い方:
    python check_dex.py            # まとめ
    python check_dex.py --series   # シリーズごとの枚数と画像
"""

from __future__ import annotations

import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "data", "cards.db")


def main() -> None:
    cx = sqlite3.connect(DB)
    cx.row_factory = sqlite3.Row
    q = lambda s, a=(): cx.execute(s, a).fetchall()
    one = lambda s, a=(): cx.execute(s, a).fetchone()[0]

    print("── 全体 ─────────────────────────────")
    n = one("SELECT COUNT(*) FROM dex")
    img = one("SELECT COUNT(*) FROM dex WHERE img IS NOT NULL")
    th = one("SELECT COUNT(*) FROM dex WHERE thumb IS NOT NULL")
    print(f"カード      {n:,}枚")
    print(f"画像        {img:,}枚（{100*img/max(1,n):.1f}%）")
    print(f"サムネイル  {th:,}枚")
    print(f"シリーズ    {one('SELECT COUNT(*) FROM dex_series')}件")
    print(f"特徴        {one('SELECT COUNT(DISTINCT feature) FROM dex_features')}種")

    print("\n── 種類 ─────────────────────────────")
    for r in q("SELECT category_ja, COUNT(*) n FROM dex GROUP BY 1 ORDER BY n DESC"):
        print(f"  {r[0] or '（なし）':10s} {r[1]:5,}枚")

    print("\n── レアリティ（弱い順）───────────────")
    for r in q("SELECT rarity, MAX(rarity_note), COUNT(*) n FROM dex "
               "GROUP BY 1 ORDER BY MIN(rarity_i)"):
        print(f"  {r[0] or '（なし）':8s} {r[1] or '':20s} {r[2]:5,}枚")

    print("\n── 色 ───────────────────────────────")
    for r in q("SELECT color, COUNT(*) n FROM dex GROUP BY 1 ORDER BY n DESC LIMIT 12"):
        print(f"  {r[0] or '（なし）':8s} {r[1]:5,}枚")

    print("\n── 気をつけるところ ──────────────────")
    bad = one("SELECT COUNT(*) FROM dex WHERE img IS NULL")
    print(f"画像が無い          {bad}枚"
          + ("（公式のカードリストに画像が載っていないもの）" if bad else "  ✅"))
    if bad:
        for r in q("SELECT key, name, rarity FROM dex WHERE img IS NULL LIMIT 20"):
            print(f"    {r[0]:16s} {r[1]}  {r[2] or ''}")
    for label, sql in [
        ("名前が空", "SELECT COUNT(*) FROM dex WHERE name IS NULL OR name=''"),
        ("レアリティが空", "SELECT COUNT(*) FROM dex WHERE rarity IS NULL"),
        ("種類が想定外",
         "SELECT COUNT(*) FROM dex WHERE category NOT IN "
         "('LEADER','CHARACTER','EVENT','STAGE','DON!!')"),
        ("色が空", "SELECT COUNT(*) FROM dex WHERE color IS NULL"),
        ("並び順が未定義のレアリティ", "SELECT COUNT(*) FROM dex WHERE rarity_i=99"),
        ("読めなかったHTML", "SELECT COUNT(*) FROM unparsed"),
        ("どのシリーズにも属さない",
         "SELECT COUNT(*) FROM dex WHERE key NOT IN (SELECT key FROM card_series)"),
    ]:
        v = one(sql)
        print(f"{label:20s} {v}件" + ("" if v else "  ✅"))
    r99 = q("SELECT DISTINCT rarity FROM dex WHERE rarity_i=99")
    if r99:
        print("  → build_dex.py の RARITY_ORDER に足す: "
              + "、".join(str(x[0]) for x in r99))

    if "--series" in sys.argv:
        print("\n── シリーズごと ──────────────────────")
        for r in q("SELECT * FROM dex_series ORDER BY (sort IS NULL), sort"):
            mark = "" if r["cards"] == r["images"] else \
                f"  ← 画像 {r['cards'] - r['images']}枚不足"
            print(f"  {r['code'] or r['series_id']:8s} {r['cards']:4d}枚"
                  f"（画像{r['images']:4d}）{mark}  {r['name'][:40]}")


if __name__ == "__main__":
    main()
