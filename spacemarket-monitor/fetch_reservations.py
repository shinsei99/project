#!/usr/bin/env python3
"""予約明細を全期間ぶん取り直す（読み取り専用）。

    GET https://mp-gateway.spacemarket.com/rest/1/owners/<slug>/search/reservations
        ?page=N&per_page=100

  絞り込みパラメータを何も付けないと**全期間・全ステータス**が返る（2026-09-01 実測）。
  1件目に `count`（総件数）が入っているので、それと突き合わせて取りこぼしを検知する。

★なぜこのスクリプトを足したか（2026-09-03）
  `local/reservations_all.json` は 2026-09-01 に会話の中で手作業で取ったもので、
  **取り直す手段がリポジトリに無かった**。分析（`trend_check.py`）の入力なのに
  更新できないと、次の担当が同じ手作業をやり直すことになる。

出力: local/reservations_all.json（gitignore。個人名・売上が入る）
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sm  # noqa: E402

PER_PAGE = 100
MAX_PAGES = 100  # 暴走止め（1万件ぶん）。実績は893件なので十分な余裕がある


def fetch_all(ctx, slug: str, headers: dict) -> list:
    rows: list = []
    total = None
    for page in range(1, MAX_PAGES + 1):
        url = (
            f"{sm.GATEWAY}/owners/{slug}/search/reservations"
            f"?page={page}&per_page={PER_PAGE}"
        )
        batch = sm.api_get(ctx, url, headers)
        if not batch:
            break
        if total is None:
            total = batch[0].get("count")
        rows.extend(batch)
        print(f"  {page}ページ目: {len(batch)}件（累計 {len(rows)}）")
        if len(batch) < PER_PAGE:
            break
        time.sleep(sm.POLITE_WAIT_SEC)  # 相手のサーバーに負荷をかけない
    else:
        print(f"★{MAX_PAGES}ページで打ち切った。取りこぼしの可能性がある", file=sys.stderr)

    if total is not None and len(rows) != total:
        print(
            f"★取得 {len(rows)}件 だが API は総件数 {total}件 と言っている。"
            "取りこぼしがないか確かめること",
            file=sys.stderr,
        )
    return rows


def main() -> int:
    ctx = sm.open_context(headless=True)
    sm.require_login(ctx)
    slug, headers = sm.api_session(ctx)
    try:
        rows = fetch_all(ctx, slug, headers)
    finally:
        sm.close_context(ctx)

    if not rows:
        print("1件も取れなかった（管理画面の作りが変わった可能性）", file=sys.stderr)
        return 1

    dates = sorted((r.get("started_at") or "")[:10] for r in rows if r.get("started_at"))
    path = sm.save_json(sm.ROOT / "local" / "reservations_all.json", rows)
    print(f"\n{len(rows)}件を保存: {path}")
    print(f"利用日の範囲: {dates[0]} 〜 {dates[-1]}")
    print("次: ./run.sh trend で診断レポートを作る")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
