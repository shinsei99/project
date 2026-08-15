"""
マイカのレアリティ絞り込みを巡回して、封入パック巡回で埋まらなかった
レアリティを補う。

封入パックの一覧ページ（crawl_myca.py）では、プロモのようにカードに番号が
印刷されていない商品はレアリティ欄が空のまま描画される。一方でマイカは
レアリティでの絞り込みを持っており、そちら（?rarity=PROMO）から辿ると
「このカードは PROMO」という対応が取れる。

  ・レアリティは23種（PROMO FUR MUR BWR UR HR SAR SR MA SSR CSR CHR AR
    K A S RRR RR R U C TR PR）＋旧裏面の記号
  ・1レアリティあたり totalPages までページを送る
  ・カードは画像パス（<img_set>/<img_file>）で myca の行と突き合わせる

⚠️ 公開サイトへのアクセスになるため 1秒1件に抑えている。

使い方:
    python fill_rarity_myca.py          # レアリティが空の行を埋める
    python fill_rarity_myca.py --all    # 空でない行も上書きする
    python fill_rarity_myca.py PROMO    # 1つだけ
"""

from __future__ import annotations

import re
import sqlite3
import sys
import time

from crawl_myca import BASE, IMG, NAME, TOTAL_PAGES, get, write

# 絞り込みメニューにあった選択肢。数の多いものを後に回しても意味は無いので
# 表示順のまま辿る。旧裏面の記号はURLに載せられないため対象外
#（記号は封入パック巡回で取れている）。
RARITIES = ["PROMO", "FUR", "MUR", "BWR", "UR", "HR", "SAR", "SR", "MA", "SSR",
            "CSR", "CHR", "AR", "K", "A", "S", "RRR", "RR", "R", "U", "C", "TR", "PR"]

DB = "data/cards.db"


def scan_rarity(rarity: str):
    """1レアリティを全ページ巡回して {(img_set, img_file)} を返す。"""
    found, page, total_pages = set(), 1, None
    while True:
        url = f"{BASE}?rarity={rarity}" + (f"&page={page}" if page > 1 else "")
        try:
            html = get(url)
        except Exception as e:
            print(f"\n  !! {rarity} page{page}: {e}", flush=True)
            break
        if total_pages is None:
            m = TOTAL_PAGES.search(html)
            total_pages = int(m.group(1)) if m else 1
        # このページに出ているカードの画像を全部拾う。名前の直前の画像が
        # そのカードのものなので、封入パック巡回と同じ手順で取る。
        for m in NAME.finditer(html):
            head = html[max(0, m.start() - 2500):m.start()]
            last = None
            for i in IMG.finditer(head):
                last = (i.group(1), i.group(2))
            if last:
                found.add(last)
        if page >= total_pages:
            break
        page += 1
    return found, total_pages or 0


def main():
    args = sys.argv[1:]
    overwrite = "--all" in args
    targets = [a for a in args if a in RARITIES] or RARITIES

    con = sqlite3.connect(DB, timeout=300)
    con.execute("PRAGMA busy_timeout = 300000")

    before = con.execute("SELECT COUNT(*) FROM myca WHERE rarity IS NULL").fetchone()[0]
    print(f"レアリティが空の行 {before:,}件 / 対象レアリティ {len(targets)}種", flush=True)

    t0, filled = time.time(), 0
    for n, r in enumerate(targets, 1):
        found, pages = scan_rarity(r)
        if not found:
            print(f"  {n}/{len(targets)}  {r:<6} 0件", flush=True)
            continue
        cond = "" if overwrite else " AND rarity IS NULL"
        data = [(r, s, f) for s, f in found]
        cur = con.cursor()
        for a in range(20):
            try:
                cur.executemany(
                    f"UPDATE myca SET rarity=? WHERE img_set=? AND img_file=?{cond}", data)
                con.commit()
                break
            except sqlite3.OperationalError as e:
                if "locked" not in str(e) or a == 19:
                    raise
                time.sleep(3)
        filled += cur.rowcount if cur.rowcount > 0 else 0
        print(f"  {n}/{len(targets)}  {r:<6} {len(found):>5}枚（{pages}ページ）"
              f" → 更新{max(0, cur.rowcount)}行　累計{filled:,}行"
              f" / {(time.time()-t0)/60:.0f}分", flush=True)

    after = con.execute("SELECT COUNT(*) FROM myca WHERE rarity IS NULL").fetchone()[0]
    print(f"\n完了: 空 {before:,} → {after:,}件 / {(time.time()-t0)/60:.0f}分", flush=True)
    con.close()


if __name__ == "__main__":
    main()
