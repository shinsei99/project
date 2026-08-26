#!/usr/bin/env python3
"""Zenn のPV（ダッシュボード限定）を取る。

    ./scripts/zenn_stats.py --login    初回だけ。画面を出して人がログインする
    ./scripts/zenn_stats.py            記事ごとのPVを出す

**Zenn の公開APIには PV が無い**（いいね数とコメント数だけ）。ダッシュボードでしか見られないので、
note と同じやり方（ログイン済みプロファイル＋画面あり・画面外）で読みにいく。
プロファイルは note と共用（`~/.note-profile`）。
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

PROFILE = Path.home() / ".note-profile"


def _ctx(p, headless=False, offscreen=True):
    args = ["--disable-blink-features=AutomationControlled"]
    if offscreen and not headless:
        args += ["--window-position=-3000,-3000", "--window-size=1280,900"]
    return p.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE), headless=headless, channel="chrome",
        viewport={"width": 1280, "height": 900}, locale="ja-JP",
        timezone_id="Asia/Tokyo", args=args)


def do_login(wait_sec: int = 600) -> None:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        ctx = _ctx(p, offscreen=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://zenn.dev/enter", wait_until="domcontentloaded")
        print(f"開いた画面で Zenn にログインしてください（最大 {wait_sec // 60} 分）。")
        print("こちらからは、その画面に触りません。")
        deadline = time.time() + wait_sec
        while time.time() < deadline:
            time.sleep(5)
            try:
                probe = ctx.new_page()
                try:
                    probe.goto("https://zenn.dev/dashboard",
                               wait_until="domcontentloaded", timeout=30000)
                    probe.wait_for_timeout(2500)
                    ok = "/enter" not in probe.url
                finally:
                    probe.close()
            except Exception:
                continue
            if ok:
                print("ログインを確認しました。次: scripts/zenn_stats.py")
                ctx.close()
                return
        print("時間切れ。もう一度 --login を")
        ctx.close()


def main() -> None:
    if "--login" in sys.argv:
        return do_login()
    from playwright.sync_api import sync_playwright
    if not PROFILE.exists():
        print("  （Zenn 未ログイン。scripts/zenn_stats.py --login で1回入る）")
        return
    with sync_playwright() as p:
        ctx = _ctx(p)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        # ★統計は /dashboard/stats（/dashboard/analytics は404）。反映は翌日。
        page.goto("https://zenn.dev/dashboard/stats", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)
        if "/enter" in page.url:
            print("  （Zenn 未ログイン。scripts/zenn_stats.py --login で1回入る）")
            ctx.close()
            return

        txt = page.inner_text("body")
        m = re.search(r"表示回数.*?直近1か月の集計結果\s*([\d,]+)\s*回", txt, re.S)
        if m:
            print(f"  表示回数（直近1か月）: {m.group(1)} 回")
        m2 = re.search(r"執筆文字数.*?直近1年の集計結果\s*([\d,]+)字", txt, re.S)
        if m2:
            print(f"  執筆文字数（直近1年）: {m2.group(1)} 字")

        # 「もっと読み込む」を押せるだけ押してから、記事ごとの回数を拾う
        for _ in range(6):
            try:
                btn = page.get_by_role("button", name="もっと読み込む")
                if btn.count() == 0:
                    break
                btn.first.click()
                page.wait_for_timeout(1200)
            except Exception:
                break

        rows = re.findall(r"(.+?)\s*\n\s*(\d{4}年\d{1,2}月\d{1,2}日)に公開\s*\n\s*([\d,]+)\s*\n?\s*回",
                          page.inner_text("body"))
        if rows:
            print("  記事ごと（表示回数の多い順）:")
            for title, day, n in sorted(rows, key=lambda r: -int(r[2].replace(",", "")))[:15]:
                print(f"    {n:>6} 回  {title.strip()[:44]}")
        ctx.close()


if __name__ == "__main__":
    main()
