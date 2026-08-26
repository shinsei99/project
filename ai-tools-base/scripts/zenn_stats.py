#!/usr/bin/env python3
"""Zenn のPV（ダッシュボード限定）を取る。

    ./scripts/zenn_stats.py --login    初回だけ。画面を出して人がログインする
    ./scripts/zenn_stats.py            記事ごとのPVを出す

**Zenn の公開APIには PV が無い**（いいね数とコメント数だけ）。ダッシュボードでしか見られないので、
note と同じやり方（ログイン済みプロファイル＋画面あり・画面外）で読みにいく。
プロファイルは note と共用（`~/.note-profile`）。
"""
from __future__ import annotations

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
        page.goto("https://zenn.dev/dashboard", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)
        if "/enter" in page.url:
            print("  （Zenn 未ログイン。scripts/zenn_stats.py --login で1回入る）")
            ctx.close()
            return
        rows = page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('a[href*="/articles/"]').forEach(a => {
                const row = a.closest('article, li, tr, div');
                if (!row) return;
                const t = (row.innerText || '').replace(/\\n+/g, ' | ').trim();
                if (t) out.push(t.slice(0, 160));
            });
            return out.slice(0, 40);
        }""")
        seen = set()
        for r in rows:
            if r in seen:
                continue
            seen.add(r)
            print("  " + r)
        ctx.close()


if __name__ == "__main__":
    main()
