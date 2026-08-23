"""
一覧用のサムネイル（180px）を data/thumb に作る。ネットワークは使わない。

原寸（公式PNG）は1枚200〜300KB。169枚のパックをそのまま一覧に並べると40MBをブラウザへ
送ることになるので、一覧は180px（15KB前後）を使う。

    python make_thumbs.py          # 未作成のぶんだけ
    python make_thumbs.py --force  # 作り直す
"""

from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "data", "img")
DST = os.path.join(HERE, "data", "thumb")
WIDTH = 180
QUALITY = 82


def source_of(key: str) -> str | None:
    p = os.path.join(SRC, key + ".png")
    return p if os.path.exists(p) else None


def one(job):
    key, force = job
    src = source_of(key)
    if not src:
        return False
    dst = os.path.join(DST, key + ".jpg")
    # 元画像のほうが新しければ作り直す（取り直したときに効く）
    if not force and os.path.exists(dst) \
            and os.path.getmtime(dst) >= os.path.getmtime(src):
        return True
    try:
        im = Image.open(src).convert("RGB")
        h = max(1, round(im.height * WIDTH / im.width))
        im.resize((WIDTH, h), Image.LANCZOS).save(dst, "JPEG", quality=QUALITY,
                                                  optimize=True)
        return True
    except Exception as e:
        print(f"  失敗 {key}: {e}")
        return False


def main() -> None:
    force = "--force" in sys.argv
    os.makedirs(DST, exist_ok=True)
    keys = sorted(os.path.splitext(f)[0]
                  for f in os.listdir(SRC) if f.endswith(".png"))
    with ThreadPoolExecutor(8) as ex:
        ok = sum(ex.map(one, [(k, force) for k in keys]))
    print(f"サムネイル {ok}/{len(keys)}枚")


if __name__ == "__main__":
    main()
