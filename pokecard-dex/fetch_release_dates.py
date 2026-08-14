"""
発売日が判っていないパックの発売日を、マイカのカードページから取る。

マイカのカードページには、埋め込みJSONに release_date が入っている。
公式サイトに商品ページが無い古いパックでもここから判る（ポケモンジム第1弾
ハナダシティジム カスミ = 1998-04-26）。

全カードを取り直す必要はない。**パックごとに1枚だけ**開けば、そのパックの
発売日が判る。実測で発売日不明が73セットだったので、73回のアクセスで済む。

⚠️ 1秒1件に抑える。

使い方:
    python fetch_release_dates.py          # 発売日が不明なパックだけ
    python fetch_release_dates.py --all    # 全パック（取り直し）
"""

from __future__ import annotations

import sqlite3
import sys
import time

from crawl_myca_cards import BASE, RELEASE, get, write


def main():
    do_all = "--all" in sys.argv
    con = sqlite3.connect("data/cards.db", timeout=300)
    con.execute("PRAGMA busy_timeout = 300000")

    cols = {r[1] for r in con.execute("PRAGMA table_info(myca_card)")}
    if "release" not in cols:
        con.execute("ALTER TABLE myca_card ADD COLUMN release TEXT")
        con.commit()

    # パックごとに代表の1枚を選ぶ。発売日が既に判っているパックは飛ばす
    sql = """
        SELECT pack_name, MIN(card_id) FROM myca_card
        WHERE status='ok' AND pack_name IS NOT NULL
        GROUP BY pack_name
    """
    packs = con.execute(sql).fetchall()
    if not do_all:
        known = {r[0] for r in con.execute(
            """SELECT pack_name FROM myca_card
               WHERE status='ok' AND release IS NOT NULL AND pack_name IS NOT NULL
               GROUP BY pack_name""")}
        packs = [p for p in packs if p[0] not in known]

    print(f"対象 {len(packs)}パック（1パック1枚だけ開く・"
          f"1秒1件で約{len(packs)/60:.0f}分）", flush=True)
    if not packs:
        print("すべて判明しています。")
        return

    t0, ok = time.time(), 0
    for n, (pack, cid) in enumerate(packs, 1):
        html = get(f"{BASE}/{cid}")
        rel = RELEASE.search(html) if html else None
        if rel:
            # 同じパックの全カードに同じ発売日を入れる
            write(con, "UPDATE myca_card SET release=? WHERE pack_name=?",
                  (rel.group(1), pack))
            ok += 1
        if n % 10 == 0 or n == len(packs):
            el = time.time() - t0
            print(f"\r  {n}/{len(packs)}  判明{ok}  {el/60:.0f}分経過", end="", flush=True)

    print(f"\n完了: {ok}/{len(packs)}パックの発売日が判明 / {(time.time()-t0)/60:.0f}分",
          flush=True)
    con.close()


if __name__ == "__main__":
    main()
