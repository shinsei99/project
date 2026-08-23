"""
カード画像を公式サイトから取ってきて data/img に置く。

公式の画像は **PNG・1枚200〜300KB**（実測。フルサイズで縦横 1000px 前後）。
4,962枚で約1.1GB になる。一覧にそのまま並べるとブラウザへ数十MB送ることに
なるので、**180px の JPEG サムネイル**（1枚15KB前後）を別に作って一覧はそちらを使う。

  data/img/<key>.png        原寸

**公式の画像には「SAMPLE」の透かしが焼き込まれている**（絵の中央に大きく）。
図鑑の主画像には透かしの無いマイカ画像（`fetch_myca_images.py`）を使い、
公式画像は**マイカに無いカードを埋めるため**に使う。一覧用サムネイルは
両方を見て良いほうから作るので `make_thumbs.py` が別に担当する。

途中で止めても続きから走る（あるファイルは取りに行かない）。

**このスクリプトはDBに書かない。** どの画像を持っているかは
「data/img にファイルがあるか」が正で、それを図鑑へ移すのは build_dex.py の仕事。
以前は1枚ごとに cards.img を UPDATE していたが、200枚ごとにしか commit しない＝
**書き込みロックを2分近く握りっぱなし**になり、裏で build_dex.py を流すと
"database is locked" で落ちた（2026-08-23）。読むだけにすればぶつかりようがない。

使い方:
    python fetch_images.py              # 未取得のぶんだけ
    python fetch_images.py --force      # 取り直す
"""

from __future__ import annotations

import os
import sqlite3
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "data", "cards.db")
IMG = os.path.join(HERE, "data", "img")
WORKERS = 8          # 公式サイトへの同時接続。実測 4本で約1.1枚/秒、8本で約2.2枚/秒。
                     # これ以上は増やさない（相手のサイトに迷惑をかけない）
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
      "Referer": "https://www.onepiece-cardgame.com/cardlist/"}


def get_one(job) -> tuple[str, str | None, str | None]:
    key, url, force = job
    dest = os.path.join(IMG, key + ".png")
    rel = os.path.join("data", "img", key + ".png")
    if os.path.exists(dest) and os.path.getsize(dest) > 0 and not force:
        return key, rel, None
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read()
        if len(body) < 1000:                 # ダミー画像・エラーページ避け
            return key, None, f"小さすぎる({len(body)}B)"
        tmp = dest + ".part"
        with open(tmp, "wb") as f:
            f.write(body)
        os.replace(tmp, dest)                # 途中で落ちた欠けたPNGを残さない
        time.sleep(0.15)
        return key, rel, None
    except Exception as e:
        return key, None, str(e)


def main() -> None:
    force = "--force" in sys.argv
    os.makedirs(IMG, exist_ok=True)

    # build_dex.py を裏で流していてもぶつからないよう待つ（DBは WAL）
    cx = sqlite3.connect(DB, timeout=120)
    rows = cx.execute("SELECT key, img_url FROM cards "
                      "WHERE img_url IS NOT NULL ORDER BY key").fetchall()
    print(f"対象 {len(rows)}枚")

    if True:
        jobs = [(k, u, force) for k, u in rows]
        done = ng = 0
        with ThreadPoolExecutor(WORKERS) as ex:
            for key, rel, err in ex.map(get_one, jobs):
                if rel:
                    done += 1
                else:
                    ng += 1
                    print(f"  !! {key}: {err}")
                if (done + ng) % 200 == 0:
                    print(f"  {done + ng}/{len(rows)}  取得{done} 失敗{ng}", flush=True)
        print(f"画像 取得{done} 失敗{ng}")

    print(f"data/img にあるファイル {len(os.listdir(IMG))}個")
    print("→ 図鑑に反映するには make_thumbs.py → build_dex.py を流す")


if __name__ == "__main__":
    main()
