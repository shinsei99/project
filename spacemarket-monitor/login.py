#!/usr/bin/env python3
"""ホスト管理画面に「人が」1回だけログインして、セッションを保存する。

★このスクリプトはパスワードを一切扱わない。
  画面を開くだけで、ID・パスワードの入力は人がキーボードで行う。
  ログインが済むと Cookie が local/profile に残り、以後 `host_check.py` /
  `host_dump.py` がそのセッションを使い回す（＝2回目からは無人で動く）。

  この作りにしている理由は2つ。
  1. 認証情報をリポジトリにも自動処理にも置かないため
  2. 2要素認証・CAPTCHA・普段と違う端末の確認メールが出ても、人が対処すれば済むため

使い方:
    ./spacemarket-monitor/run.sh login
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sm  # noqa: E402

WAIT_LIMIT_SEC = 15 * 60
POLL_SEC = 5


def main() -> int:
    ctx = sm.open_context(headless=False)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()

    if sm.logged_in(ctx):
        print("✅ すでにログイン済みです（local/profile のセッションが生きています）。")
        sm.close_context(ctx)
        return 0

    page.goto(sm.LOGIN_URL, wait_until="domcontentloaded", timeout=60_000)
    print(
        "\n──────────────────────────────────────────────\n"
        "Chrome が開きました。**この画面でご自身でログインしてください。**\n"
        f"  アカウント: info@shinsei-pm.co.jp\n"
        "  （パスワードはこのツールは持っていません。人が入力してください）\n"
        "\n"
        "ログインできたら、このまま放置で構いません。自動で検知して終了します。\n"
        f"（最大 {WAIT_LIMIT_SEC // 60} 分待ちます。中止は Ctrl+C）\n"
        "──────────────────────────────────────────────\n",
        flush=True,
    )

    probe = ctx.new_page()
    deadline = time.time() + WAIT_LIMIT_SEC
    try:
        while time.time() < deadline:
            time.sleep(POLL_SEC)
            try:
                resp = probe.goto(
                    sm.DASHBOARD + "/", wait_until="domcontentloaded", timeout=30_000
                )
            except Exception:
                continue
            if resp and resp.status == 200:
                print("✅ ログインを確認しました。セッションを local/profile に保存しました。")
                print("   次は:  ./spacemarket-monitor/run.sh dump   （管理画面の中身を取得）")
                sm.close_context(ctx)
                return 0
    except KeyboardInterrupt:
        print("\n中止しました。", file=sys.stderr)
        sm.close_context(ctx)
        return 130

    print(
        f"\n{WAIT_LIMIT_SEC // 60}分待ちましたが、ログインを確認できませんでした。\n"
        "  もう一度 ./spacemarket-monitor/run.sh login を実行してください。",
        file=sys.stderr,
    )
    sm.close_context(ctx)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
