"""
レアリティが空のまま保存されたカードを取り直す。

巡回の途中でパーサを何度も直したため、初期に取ったカードには本来あった
レアリティが入っていない。実測では ID 5万未満（1996〜2003年あたり）に
3,799枚あり、取り直すと PROMO や ● ◆ ★ が入る。

保存済みのデータからは復元できない（元のタイトルを持っていないため）。
ページを開き直す必要がある。

⚠️ 2件/秒に抑えている（crawl_myca_cards の設定に従う）。

使い方:
    python refetch_missing_rarity.py            # レアリティが空の全カード
    python refetch_missing_rarity.py 50000      # ID上限を指定
"""

from __future__ import annotations

import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from crawl_myca_cards import WORKERS, fetch_one, write


def main():
    limit_id = int(sys.argv[1]) if len(sys.argv) > 1 else None
    con = sqlite3.connect("data/cards.db", timeout=300)
    con.execute("PRAGMA busy_timeout = 300000")

    sql = ("SELECT card_id FROM myca_card WHERE status='ok' AND rarity IS NULL"
           + (" AND card_id < ?" if limit_id else "")
           + " ORDER BY card_id")
    todo = [r[0] for r in con.execute(sql, (limit_id,) if limit_id else ())]
    print(f"対象 {len(todo):,}枚（2件/秒で約{len(todo)*0.5/60:.0f}分）", flush=True)
    if not todo:
        print("ありません。")
        return

    t0, got, buf = time.time(), 0, []
    ex = ThreadPoolExecutor(max_workers=WORKERS)
    for n, row in enumerate(ex.map(fetch_one, todo), 1):
        buf.append(row)
        got += bool(row[5])            # レアリティが入ったか
        if len(buf) >= 25:
            write(con, "INSERT OR REPLACE INTO myca_card VALUES ("
                  + ",".join("?" * 13) + ")", buf)
            buf = []
            el = time.time() - t0
            print(f"\r  {n:,}/{len(todo):,}  レアリティ判明{got:,}  "
                  f"{el/60:.0f}分経過 / 残り約{(len(todo)-n)/(n/el)/60:.0f}分   ",
                  end="", flush=True)
    ex.shutdown()
    if buf:
        write(con, "INSERT OR REPLACE INTO myca_card VALUES ("
              + ",".join("?" * 13) + ")", buf)

    left = con.execute("SELECT COUNT(*) FROM myca_card "
                       "WHERE status='ok' AND rarity IS NULL").fetchone()[0]
    print(f"\n完了: {got:,}枚のレアリティが判明 / 空のまま残り {left:,}枚"
          f" / {(time.time()-t0)/60:.0f}分", flush=True)
    con.close()


if __name__ == "__main__":
    main()
