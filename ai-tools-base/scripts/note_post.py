#!/usr/bin/env python3
"""note へ記事を1本投稿する（Playwright・ログイン済みプロファイルを使う）。

    ./scripts/note_post.py --login              初回だけ。画面を出して人がログインする
    ./scripts/note_post.py --check              ログインが生きているかだけ確かめる
    ./scripts/note_post.py <名前>               drafts/note/<名前>.md を投稿する
    ./scripts/note_post.py --next               まだ出していない原稿を1本だけ投稿する

## なぜ Playwright なのか

`claude -p`（非対話）からは **claude-in-chrome の拡張が使えない**（2026-08-27 実測。
「接続されているブラウザ系MCPは playwright のみ」と返る）。常駐から自動投稿するには
自前で動かすしかない。

## なぜプロファイルを持ち込むのか

`--isolated`（毎回まっさら）だと note のログイン画面を越えられない。**一度ログインした
プロファイルを使い回せば、ログインの操作自体が要らない**。初回だけ人が `--login` で入る。

## note の癖（拡張でやっていたときと同じ）

- **Markdown は効かない**。`drafts/note/md2html.py` で HTML にして貼る
- 貼り付けは **ClipboardEvent を ProseMirror へ dispatch**（OSのクリップボードは載らない）
- タイトルは React の state を動かすため **native setter + input イベント**
- **表は扱えない**（原稿側で箇条書きにしてある）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTE_DIR = ROOT / "drafts" / "note"
PROFILE = Path.home() / ".note-profile"
STATE = ROOT / "drafts" / ".note_posted.json"
TAGS = ["不動産", "AI", "業務効率化", "ClaudeCode", "個人開発"]

sys.path.insert(0, str(NOTE_DIR))


def _html(name: str) -> tuple[str, str]:
    import md2html
    md = (NOTE_DIR / f"{name}.md").read_text(encoding="utf-8")
    return md2html.convert(md)


def _posted() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


def _remember(name: str, url: str) -> None:
    d = _posted()
    d[name] = url
    STATE.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _context(p, headless: bool):
    return p.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE),
        headless=headless,
        channel="chrome",                 # 実物の Chrome を使う（検知されにくい）
        viewport={"width": 1280, "height": 900},
        locale="ja-JP",
        timezone_id="Asia/Tokyo",
        args=["--disable-blink-features=AutomationControlled"],
    )


def logged_in(page) -> bool:
    page.goto("https://note.com/", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2500)
    # ログイン中は「投稿」ボタンが出る。未ログインなら「ログイン」が出る
    html = page.content()
    return ("ログイン" not in html[:200000]) or ("/notes/new" in html)


def do_login(wait_sec: int = 300) -> None:
    """画面を出して人にログインしてもらう。**Enter待ちにはしない**
    （`!` 付きの一発実行や、他のセッションからでも走らせられるように）。
    ログインできたことを自分で見つけて終わる。"""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        ctx = _context(p, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://note.com/login", wait_until="domcontentloaded")
        print(f"開いた画面で note にログインしてください（最大 {wait_sec} 秒待ちます）。")
        deadline = time.time() + wait_sec
        while time.time() < deadline:
            page.wait_for_timeout(3000)
            url = page.url
            if "note.com/login" not in url:
                # ログイン後はどこかへ飛ぶ。エディタを開けるかで確かめる
                page.goto("https://note.com/notes/new", wait_until="domcontentloaded")
                try:
                    page.wait_for_selector('.ProseMirror', timeout=15000)
                    print("ログインできました。プロファイル:", PROFILE)
                    print("次: ./scripts/note_post.py --check （headless でも入れるかの確認）")
                    ctx.close()
                    return
                except Exception:
                    page.goto("https://note.com/login", wait_until="domcontentloaded")
        print("時間切れ。もう一度 --login を実行してください")
        ctx.close()


def do_check() -> None:
    from playwright.sync_api import sync_playwright
    if not PROFILE.exists():
        print("プロファイルが無い。先に --login を実行すること")
        sys.exit(1)
    with sync_playwright() as p:
        ctx = _context(p, headless=True)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        ok = logged_in(page)
        print("ログイン状態:", "OK（headless でも入れている）" if ok else "NG（--login をやり直す）")
        ctx.close()
        sys.exit(0 if ok else 1)


def post(name: str, headless: bool = True, dry: bool = False) -> str | None:
    from playwright.sync_api import sync_playwright
    title, html = _html(name)
    print(f"[note] {name} … {title}")

    with sync_playwright() as p:
        ctx = _context(p, headless=headless)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        page.goto("https://note.com/notes/new", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector(".ProseMirror", timeout=30000)
        page.wait_for_timeout(1500)
        key = re.search(r"/notes/([^/]+)/edit", page.url)
        if not key:
            print("  エディタを開けなかった（ログインが切れている可能性）:", page.url)
            ctx.close()
            return None
        note_key = key.group(1)

        page.evaluate(
            """([title, html]) => {
                const ta = document.querySelector('textarea[placeholder="記事タイトル"]');
                const setter = Object.getOwnPropertyDescriptor(
                    window.HTMLTextAreaElement.prototype, 'value').set;
                setter.call(ta, title);
                ta.dispatchEvent(new Event('input', { bubbles: true }));
                const pm = document.querySelector('.ProseMirror');
                pm.focus();
                const dt = new DataTransfer();
                dt.setData('text/html', html);
                dt.setData('text/plain', html.replace(/<[^>]+>/g, ''));
                pm.dispatchEvent(new ClipboardEvent('paste',
                    { clipboardData: dt, bubbles: true, cancelable: true }));
            }""",
            [title, html],
        )
        page.wait_for_timeout(1200)
        n = page.evaluate("document.querySelector('.ProseMirror').innerText.length")
        print(f"  本文 {n} 文字")
        if n < 200:
            print("  本文が入っていない。中止")
            ctx.close()
            return None

        page.get_by_role("button", name="下書き保存").click()
        page.wait_for_timeout(2500)

        if dry:
            print(f"  下書きまで（未公開）: https://note.com/shinsei99/n/{note_key}")
            ctx.close()
            return None

        page.get_by_role("button", name="公開に進む").click()
        page.wait_for_url("**/publish/", timeout=30000)
        page.wait_for_timeout(1500)

        box = page.get_by_placeholder("ハッシュタグを追加する")
        for t in TAGS:
            box.fill(t)
            page.keyboard.press("Enter")
            page.wait_for_timeout(400)

        page.get_by_role("button", name="投稿する").click()
        page.wait_for_timeout(5000)

        url = f"https://note.com/shinsei99/n/{note_key}"
        print("  公開:", url)
        ctx.close()
        return url


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("name", nargs="?")
    ap.add_argument("--login", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--next", action="store_true", dest="nxt")
    ap.add_argument("--dry", action="store_true", help="下書きまでで止める")
    ap.add_argument("--headed", action="store_true", help="画面を出す")
    a = ap.parse_args()

    if a.login:
        return do_login()
    if a.check:
        return do_check()

    name = a.name
    if a.nxt:
        done = set(_posted())
        order = (ROOT / "drafts" / "zenn_order.txt").read_text(encoding="utf-8").splitlines()
        order = [x.strip() for x in order if x.strip() and not x.startswith("#")]
        rest = [x for x in order if x not in done and (NOTE_DIR / f"{x}.md").exists()]
        if not rest:
            print("出すものが無い")
            return
        name = rest[0]
    if not name:
        ap.error("原稿名 か --next が要る")

    url = post(name, headless=not a.headed, dry=a.dry)
    if url:
        _remember(name, url)


if __name__ == "__main__":
    main()
