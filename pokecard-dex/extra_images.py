"""どの経路にも無く、**手で1枚ずつ確かめて拾った**画像をまとめて入れる。

セット単位で自動化できるものは専用スクリプトがある
（`learnbook.py` / `pcgsearch.py` / `snkrdunk.py` / `cardrush.py`）。
ここはその網から漏れた「1枚もの」用。**必ず実物の画像を目で見て、
カード名と印字番号が dex の行と一致することを確認してから書くこと。**

⚠️ 晴れる屋2の画像には**うっすら「HARERUYA」の透かしが入る**。
   他に取得元が無いので許容した（2026-08-14）。

使い方:
    python extra_images.py --dry-run
    python extra_images.py
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import time
import urllib.request

DB = "data/cards.db"
IMG_DIR = "data/extra"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
WAIT = 1.0

# (dex_key, 期待するカード名, 取得元, 画像URL)
# 名前は「取り違えていないか」の照合用。dex 側と一致しなければ採らない。
WANT = [
    # プレミアムトレーナーボックスMEGA の基本水エネルギー。
    # マイカは他の7色（草炎雷超闘悪鋼）を持っているのに水だけ欠けていた。
    # カードラッシュの商品名は「基本水エネルギー(MEGAデザイン)」で番号は無いが、
    # 実物の左下に "WAT" の印字があり、他色（MA_GRA 等）と同じ MEGA デザイン。
    ("MA/MAAT", "基本水エネルギー", "cardrush",
     "https://www.cardrush-pokemon.jp/data/cardrushpokemon/product/CR_MA_046.jpg"),

    # XY-P「デッキ構築ゼミ」のスーパーボール。公式の XY-P に無く、
    # 他の3枚（サナ・ポケモンいれかえ・ポケモンキャッチャー）だけ公式で埋まっていた。
    # 晴れる屋2 福岡店の商品名が
    # 「スーパーボール:デッキ構築ゼミ(PROMO){グッズ}〈XY-P〉[XY-P]」で商品と一致。
    ("mc/181725", "スーパーボール", "hareruya2",
     "https://fukuoka.hareruya2.com/cdn/shop/files/"
     "k4q4qyeVDA89Sa5cOfCNPJ8OHCCo7Gqn2pdjKd6y.webp"),

    # M-P 079 ふしぎなアメ。カードラッシュの M-P 一覧は 077→080 で飛んでおり
    # ここだけ無かった。晴れる屋2の商品名が「ふしぎなアメ(PROMO)〈079/M-P〉」、
    # 実物にも「079/M-P」の印字あり。
    ("mc/370230", "ふしぎなアメ", "hareruya2",
     "https://www.hareruya2.com/cdn/shop/files/promo079m-pm-p-3439156.webp"),
]


def setup(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS extra_images (
      dex_key TEXT PRIMARY KEY,
      source  TEXT,
      url     TEXT,
      local   TEXT,
      status  TEXT
    );
    """)
    con.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    con = sqlite3.connect(DB, timeout=300)
    setup(con)
    n = 0
    for key, want_name, source, url in WANT:
        row = con.execute("SELECT name FROM dex WHERE key = ?", (key,)).fetchone()
        if not row:
            print(f"{key} dex に行が無い")
            continue
        if row[0] != want_name:
            print(f"{key} 名前が違う: dex={row[0]!r} 期待={want_name!r}")
            continue
        print(f"{key} {row[0]} ← {source}")
        if a.dry_run:
            continue
        ext = ".webp" if url.endswith(".webp") else ".jpg"
        path = os.path.join(IMG_DIR, f"{key.replace('/', '_')}{ext}")
        if not os.path.exists(path):
            os.makedirs(IMG_DIR, exist_ok=True)
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
            if ext == ".webp":          # 図鑑側で扱いやすいよう JPEG に直す
                from io import BytesIO

                from PIL import Image
                path = path[:-5] + ".jpg"
                Image.open(BytesIO(raw)).convert("RGB").save(path, quality=92)
            else:
                with open(path, "wb") as f:
                    f.write(raw)
            time.sleep(WAIT)
        n += 1
        con.execute("""INSERT OR REPLACE INTO extra_images
                       (dex_key, source, url, local, status) VALUES (?,?,?,?,?)""",
                    (key, source, url, path, "ok"))
        con.commit()
    print(f"\n取得 {n}枚" + ("（--dry-run なので取得していない）" if a.dry_run else ""))
    print("このあと python build_dex.py で図鑑に反映する")


if __name__ == "__main__":
    main()
