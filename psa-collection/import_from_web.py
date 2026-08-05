#!/usr/bin/env python3
"""画像URLの一覧を読んで、カード画像をローカルに保存する。

CloudFrontの画像URLは**認証不要**なので、URLさえ分かっていれば誰のPCからでも落とせる。
つまり別PCへの引き継ぎは、数百MBの画像ではなく `data/image_urls.json`（数百KB）
だけ渡せば済む。

    python3 import_from_web.py                    # data/image_urls.json から（引き継ぎ時はこれ）
    python3 import_from_web.py /tmp/items.jsonl   # harvest_collectors.js の結果から（初回収集時）

URLの収集はログイン済みブラウザで `harvest_collectors.js` を流し込んで行う。
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from psa_images import ImageStore

DATA_DIR = Path(__file__).parent / "data"


def main() -> int:
    store = ImageStore(DATA_DIR)

    if len(sys.argv) > 1:
        # harvest_collectors.js の結果（1行1枚のJSONL）から
        src = Path(sys.argv[1])
        if not src.exists():
            print(f"入力がありません: {src}", file=sys.stderr)
            return 1
        rows = [json.loads(line) for line in src.read_text().splitlines() if line.strip()]
        rows = [r for r in rows if r.get("url")]
        # URLは先に全部控える（DLに失敗してもブラウザ直リンク表示にフォールバックできる）
        for r in rows:
            store.set_urls(str(r["cert"]), front=r["url"])
    else:
        # 引き継ぎ時: すでに控えてある data/image_urls.json から
        urls = store._urls()
        if not urls:
            print(
                "data/image_urls.json がありません。\n"
                "初回はログイン済みブラウザで harvest_collectors.js を実行し、\n"
                "その結果のJSONLを引数に渡してください（README参照）。",
                file=sys.stderr,
            )
            return 1
        rows = [
            {"cert": cert, "url": e.get("front")}
            for cert, e in urls.items() if e.get("front")
        ]
        print(f"data/image_urls.json から {len(rows):,}枚ぶんのURLを読みました")

    todo = [r for r in rows if not store.has(str(r["cert"]))]
    print(f"対象 {len(rows):,}枚 / 未取得 {len(todo):,}枚 をダウンロードします")

    ok, ng = 0, []

    def fetch(r):
        cert = str(r["cert"])
        try:
            resp = requests.get(r["url"], timeout=30)
            if resp.status_code == 200 and resp.content:
                store.save_bytes(cert, resp.content)
                return cert, True, len(resp.content)
            return cert, False, f"HTTP {resp.status_code}"
        except requests.RequestException as e:
            return cert, False, str(e)

    with ThreadPoolExecutor(max_workers=8) as pool:
        for i, (cert, good, info) in enumerate(pool.map(fetch, todo), 1):
            if good:
                ok += 1
            else:
                ng.append(f"{cert}: {info}")
            if i % 25 == 0 or i == len(todo):
                print(f"\r  {i}/{len(todo)} …", end="", flush=True)
    print()

    total_mb = sum(p.stat().st_size for p in store.dir.glob("*.jpg")) / 1024 / 1024
    print(f"完了: {ok}枚 保存 / {len(ng)}枚 失敗")
    print(f"保存先: {store.dir}（合計 {total_mb:.0f} MB、{len(store.cached_certs()):,}枚）")
    for m in ng[:10]:
        print(f"  {m}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
