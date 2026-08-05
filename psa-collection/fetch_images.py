#!/usr/bin/env python3
"""カード画像をPSA公開APIからまとめて取得する（画面を開かずに実行できる版）。

無料枠は1日100件。上限に達したら自動で止まるので、毎日実行すれば続きから貯まる。

    python3 fetch_images.py                 # 保有中(Active)の未取得分を取れるだけ
    python3 fetch_images.py --all           # 売却済も含めて全件
    python3 fetch_images.py --limit 20      # 20件だけ
    python3 fetch_images.py --token XXXX    # トークンを指定（省略時は data/psa_api.json）
    python3 fetch_images.py --status        # 取得状況だけ表示
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from psa_images import DAILY_LIMIT, ImageStore, fetch_many

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
CSV_PATH = DATA_DIR / "collection.csv"
TOKEN_PATH = DATA_DIR / "psa_api.json"


def main() -> int:
    ap = argparse.ArgumentParser(description="PSAカード画像の一括取得")
    ap.add_argument("--token", help="PSA APIトークン（省略時は data/psa_api.json）")
    ap.add_argument("--all", action="store_true", help="売却済も含めて全件を対象にする")
    ap.add_argument("--limit", type=int, help="今回取得する最大件数")
    ap.add_argument("--status", action="store_true", help="取得状況だけ表示して終了")
    args = ap.parse_args()

    if not CSV_PATH.exists():
        print(f"CSVがありません: {CSV_PATH}", file=sys.stderr)
        return 1

    df = pd.read_csv(CSV_PATH, dtype=str)
    store = ImageStore(DATA_DIR)
    cached = store.cached_certs()

    target = df if args.all else df[df["Item Status"] == "Active"]
    certs = [str(c) for c in target["Cert Number"]]
    todo = [c for c in certs if c not in cached]

    print(f"対象 {len(certs):,}枚 / 取得済み {len(certs) - len(todo):,}枚 / 未取得 {len(todo):,}枚")
    print(f"本日の残り取得可能数: {store.remaining_today()} / {DAILY_LIMIT} 件")
    if args.status:
        failed = store.failed_certs()
        if failed:
            print(f"取得できなかったもの: {len(failed)}件")
            for cert, reason in list(failed.items())[:10]:
                print(f"  {cert}: {reason}")
        return 0

    token = args.token
    if not token and TOKEN_PATH.exists():
        token = json.loads(TOKEN_PATH.read_text(encoding="utf-8")).get("token", "")
    if not token:
        print(
            "トークンがありません。--token で渡すか、アプリのサイドバーで保存してください。\n"
            "発行元: https://www.psacard.com/publicapi （PSAアカウントでログイン）",
            file=sys.stderr,
        )
        return 1
    # 指定されたトークンは次回以降のために保存しておく
    if args.token:
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(json.dumps({"token": token}), encoding="utf-8")

    if not todo:
        print("すべて取得済みです。")
        return 0
    if store.remaining_today() <= 0:
        print("本日の上限に達しています。明日また実行してください。")
        return 0

    if args.limit:
        todo = todo[: args.limit]

    def progress(i, total, cert):
        print(f"\r  {i}/{total} 取得中… (証明書 {cert})", end="", flush=True)

    result = fetch_many(todo, token, store, progress=progress)
    print()

    print(f"完了: {result['ok']}枚 取得 / {result['ng']}枚 失敗")
    if result["stopped"]:
        print(result["stopped"])
    for msg in result["messages"][:10]:
        print(f"  {msg}")

    remaining = len([c for c in certs if c not in store.cached_certs()])
    if remaining:
        days = -(-remaining // DAILY_LIMIT)
        print(f"残り {remaining:,}枚（あと約{days}日ぶん）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
