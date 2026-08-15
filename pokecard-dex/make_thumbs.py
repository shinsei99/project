"""
一覧表示用のサムネイル（180px）を、取得済みの400px画像から作る。

400px版は1枚67KBあり、収録枚数の多いパック（MEGAドリームex 486枚、
スタートデッキ100 バトルコレクション 843枚）を一覧に並べると数十MBを
ブラウザへ送ることになって表示が重い。一覧は180px（1枚約18KB）で足りる。

ネットワークは使わない。data/myca_large の画像を縮小して
data/myca_thumbs に同じ構成で置くだけ。

使い方:
    python make_thumbs.py          # 未作成のぶんを作る
    python make_thumbs.py --force  # 作り直す
"""

from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

SRC = "data/myca_large"
DST = "data/myca_thumbs"
WIDTH = 180
QUALITY = 82


def one(job):
    src, dst = job
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        im = Image.open(src).convert("RGB")
        im.thumbnail((WIDTH, WIDTH * 2), Image.LANCZOS)
        im.save(dst, quality=QUALITY, optimize=True)
        return True
    except Exception:
        return False


def main():
    force = "--force" in sys.argv
    jobs = []
    for d, _, files in os.walk(SRC):
        for f in files:
            if not f.endswith(".jpg"):
                continue
            src = os.path.join(d, f)
            dst = src.replace(SRC, DST, 1)
            if force or not os.path.exists(dst):
                jobs.append((src, dst))

    print(f"作成する枚数 {len(jobs):,}", flush=True)
    if not jobs:
        print("すべて作成済みです。")
        return

    ok = 0
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as ex:
        for n, r in enumerate(ex.map(one, jobs), 1):
            ok += r
            if n % 500 == 0:
                print(f"\r  {n:,}/{len(jobs):,}", end="", flush=True)

    mb = sum(os.path.getsize(os.path.join(d, f))
             for d, _, fs in os.walk(DST) for f in fs) / 1024 / 1024
    print(f"\n完了: {ok:,}枚 / 手元に {mb:,.0f}MB", flush=True)


if __name__ == "__main__":
    main()
