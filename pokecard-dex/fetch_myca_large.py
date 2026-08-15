"""
マイカの高解像度カード画像（400px）を取得する。

同じCDNで拡張子を変えるだけで解像度が変わることが判った。

    .../card/M6/M6_113.gif →  180x251 /  50KB
    .../card/M6/M6_113.jpg →  400x559 / 227KB   ← こちらを使う

公式サイトの画像（360x503）より大きく、しかも1998年の旧裏面カードにも
存在する（公式は2019年10月のTAG TEAM GX以降しか無い）。実測で
「カスミのメノクラゲLV.12」がワザの効果文まで読める品質で取れた。

保存は JPEG 品質88・長辺400のまま。1枚あたり約60KB（元は227KBだが
再エンコードで縮む）。2万枚で約1.2GB。

⚠️ カード画像の著作権は ©Pokémon/Nintendo/Creatures/GAME FREAK に帰属する。
   取得物は手元での参照に限り、公開・配布しない（data/ は gitignore）。

使い方:
    python fetch_myca_large.py           # 未取得のものを全部
    python fetch_myca_large.py M6        # セットを指定
"""

from __future__ import annotations

import io
import os
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from PIL import Image

CDN = "https://static.mycalinks.io/app/item/image/card"
DB = "data/cards.db"
IMG_DIR = "data/myca_large"

QUALITY = 88
REQ_PER_SEC = 3.0        # CDN相手だが上限は設ける
WORKERS = 3

S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "https://myca.dmm.com/",
})

_lock = threading.Lock()
_last = [0.0]


def throttle():
    with _lock:
        w = 1.0 / REQ_PER_SEC - (time.time() - _last[0])
        if w > 0:
            time.sleep(w)
        _last[0] = time.time()


def dest(img_set: str, img_file: str) -> str:
    return os.path.join(IMG_DIR, img_set, f"{img_file}.jpg")


def fetch_one(job):
    img_set, img_file = job
    dst = dest(img_set, img_file)
    if os.path.exists(dst):
        return dst
    throttle()
    try:
        r = S.get(f"{CDN}/{img_set}/{img_file}.jpg", timeout=60)
        if r.status_code != 200:
            return None
        im = Image.open(io.BytesIO(r.content)).convert("RGB")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        im.save(dst, quality=QUALITY, optimize=True)
        return dst
    except Exception:
        return None


def jobs(con, only=None):
    """一覧から取れた分（myca）と、カード単体ページから取れた分（myca_card）の両方。"""
    out = set()
    sql = "SELECT DISTINCT img_set, img_file FROM myca WHERE img_file IS NOT NULL"
    args: tuple = ()
    if only:
        sql += " AND img_set = ?"
        args = (only,)
    out |= {(r[0], r[1]) for r in con.execute(sql, args)}

    if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                   "AND name='myca_card'").fetchone():
        sql2 = ("SELECT DISTINCT img_set, img_file FROM myca_card "
                "WHERE status='ok' AND img_file IS NOT NULL")
        if only:
            sql2 += " AND img_set = ?"
        out |= {(r[0], r[1]) for r in con.execute(sql2, args)}
    return sorted(out)


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    con = sqlite3.connect(DB, timeout=300)
    con.execute("PRAGMA busy_timeout = 300000")

    all_jobs = jobs(con, only)
    todo = [j for j in all_jobs if not os.path.exists(dest(*j))]
    print(f"対象 {len(todo):,}枚（全{len(all_jobs):,}枚のうち未取得分・"
          f"見込み約{len(todo)/REQ_PER_SEC/60:.0f}分）", flush=True)
    if not todo:
        print("すべて取得済みです。")
        return

    t0, ok, ng = time.time(), 0, 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for n, dst in enumerate(ex.map(fetch_one, todo), 1):
            ok += dst is not None
            ng += dst is None
            if n % 50 == 0:
                el = time.time() - t0
                print(f"\r  {n:,}/{len(todo):,}  取得{ok:,} 失敗{ng:,}  "
                      f"{el/60:.0f}分経過 / 残り約{(len(todo)-n)/(n/el)/60:.0f}分   ",
                      end="", flush=True)

    mb = sum(os.path.getsize(os.path.join(d, f))
             for d, _, fs in os.walk(IMG_DIR) for f in fs) / 1024 / 1024
    print(f"\n完了: 取得{ok:,} / 失敗{ng:,} / 手元に {mb:,.0f}MB "
          f"/ {(time.time()-t0)/60:.0f}分", flush=True)
    con.close()


if __name__ == "__main__":
    main()
