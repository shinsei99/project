"""pcg-search.com のカード画像から eシリーズを補う。

なぜここを使うのか（2026-08-14に発見）:
  カーナベル（ka-nabell.com）のカードリストが画像をここから読んでおり、
  **URLがセット記号＋番号だけで決まる**ので探索が要らない。

      https://pcg-search.com/img/e/e2085.png   ← E2 の085番

  画質もこれまでで最良。**593×834・透かし無し・余白なし**。

      pcg-search   593×834   透かし無し           ← これ
      スニダン       430×610   透かし無し（背景除去。切り抜きが要る）
      learn-book   356×500   透かし無し（載っていない番号がある）
      フルアヘッド     287×400   中央に「COPY」の透かし

  **eシリーズの全番号が揃っている**（E1 は 001〜128、キラ枠の 097〜128 も含む）。
  2枚組のキラ版と通常版も**別画像**（e1068 と e1100 は md5 が違う）。

⚠️ 取得は1秒1件に抑える。画像の著作権は ©Pokémon/Nintendo/Creatures/GAME FREAK
   に帰属し、取得物は手元での参照に限る（data/ は gitignore・公開配布しない）。

使い方:
    python pcgsearch.py --dry-run   # 対象を数えるだけ
    python pcgsearch.py             # 画像が無い行だけ取得する
    python pcgsearch.py --all       # eシリーズ全部を取り直す（借り物の絵を本物に差し替える）
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import time
import urllib.request

DB = "data/cards.db"
IMG_DIR = "data/pcgsearch"
URL = "https://pcg-search.com/img/e/e{n}{no:03d}.png"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
WAIT = 1.0

SETS = {"E1": "1", "E2": "2", "E3": "3", "E4": "4", "E5": "5"}


def setup(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS pcgsearch (
      dex_key  TEXT PRIMARY KEY,
      set_code TEXT,
      card_no  INTEGER,
      url      TEXT,
      local    TEXT,
      status   TEXT
    );
    """)
    con.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--all", action="store_true",
                    help="画像がある行も取り直す（借り物の絵を本物に差し替える）")
    a = ap.parse_args()

    con = sqlite3.connect(DB)
    setup(con)

    cond = "" if a.all else \
        " AND img IS NULL AND img_off IS NULL AND img_web IS NULL"
    total = dl = 0
    for set_code, n in SETS.items():
        rows = con.execute(
            f"""SELECT key, card_no, name FROM dex
                WHERE set_code = ? AND card_no IS NOT NULL{cond}
                ORDER BY card_no""", (set_code,)).fetchall()
        if not rows:
            continue
        print(f"{set_code}: 対象 {len(rows)}枚", flush=True)
        for key, no, name in rows:
            total += 1
            url = URL.format(n=n, no=no)
            path = os.path.join(IMG_DIR, set_code, f"{key.replace('/', '_')}.png")
            if not os.path.exists(path) and not a.dry_run:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                try:
                    req = urllib.request.Request(url, headers=UA)
                    with urllib.request.urlopen(req, timeout=60) as r:
                        raw = r.read()
                except Exception as e:
                    print(f"  {set_code}-{no:03d} {name[:14]} 取得失敗: {e}")
                    con.execute("""INSERT OR REPLACE INTO pcgsearch
                                   (dex_key,set_code,card_no,url,local,status)
                                   VALUES (?,?,?,?,?,?)""",
                                (key, set_code, no, url, None, "error"))
                    time.sleep(WAIT)
                    continue
                with open(path, "wb") as f:
                    f.write(raw)
                time.sleep(WAIT)
            if a.dry_run:
                continue
            dl += 1
            con.execute("""INSERT OR REPLACE INTO pcgsearch
                           (dex_key,set_code,card_no,url,local,status)
                           VALUES (?,?,?,?,?,?)""",
                        (key, set_code, no, url, path, "ok"))
        con.commit()

    print(f"\n対象 {total}枚 / 取得 {dl}枚"
          + ("（--dry-run なので取得していない）" if a.dry_run else ""))
    print("このあと python build_dex.py で図鑑に反映する")


if __name__ == "__main__":
    main()
