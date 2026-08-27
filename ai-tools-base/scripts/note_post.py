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


def _context(p, headless: bool = False, offscreen: bool = True):
    """★headless では note のエディタが描画されない（2026-08-27 実測）。

    `headless=True` だと `editor.note.com/new` で止まり、body が空のまま
    `.ProseMirror` が現れない。画面ありなら記事キーが発行されて正常に開く。
    なので**画面ありで動かし、ウィンドウを画面の外に置いて**邪魔にならないようにする。
    """
    args = ["--disable-blink-features=AutomationControlled"]
    if offscreen and not headless:
        args += ["--window-position=-3000,-3000", "--window-size=1280,900"]
    return p.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE),
        headless=headless,
        channel="chrome",                 # 実物の Chrome を使う（検知されにくい）
        viewport={"width": 1280, "height": 900},
        locale="ja-JP",
        timezone_id="Asia/Tokyo",
        args=args,
    )


def logged_in(page) -> bool:
    """**エディタが実際に開けるか**で判定する。
    トップページの文字列で判定していたときは、headless で描画されていないのに
    OK と出てしまった（2026-08-27）。"""
    page.goto("https://note.com/notes/new", wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_selector(".ProseMirror", timeout=30000)
    except Exception:
        return False
    return "/edit" in page.url


def do_login(wait_sec: int = 600) -> None:
    """画面を出して人にログインしてもらう。

    ★**人が操作している画面には、こちらから一切触らない。**
    以前はループの中で `page.goto()` を呼んで確認していたが、ログインの途中で
    画面を奪ってしまい、入力できなかった（2026-08-27）。
    確認は**別タブ**を一瞬開いて行い、そのタブはすぐ閉じる。
    """
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        ctx = _context(p, headless=False, offscreen=False)   # 人が操作するので画面内に出す
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://note.com/login", wait_until="domcontentloaded")
        print(f"開いた画面で note にログインしてください（最大 {wait_sec // 60} 分待ちます）。")
        print("こちらからは、その画面に触りません。ログインできたら自動で終わります。")

        deadline = time.time() + wait_sec
        while time.time() < deadline:
            time.sleep(5)
            try:
                # 人の画面は触らない。別タブで確かめて、すぐ閉じる
                probe = ctx.new_page()
                try:
                    probe.goto("https://note.com/notes/new",
                               wait_until="domcontentloaded", timeout=30000)
                    ok = probe.locator(".ProseMirror").count() > 0
                    if not ok:
                        probe.wait_for_timeout(3000)
                        ok = probe.locator(".ProseMirror").count() > 0
                finally:
                    probe.close()
            except Exception:
                continue
            if ok:
                print("ログインを確認しました。プロファイル:", PROFILE)
                print("次: scripts/note_post.py --check （headless でも入れるかの確認）")
                ctx.close()
                return
        print("時間切れ。もう一度 --login を実行してください")
        ctx.close()


def do_check() -> None:
    from playwright.sync_api import sync_playwright
    if not PROFILE.exists():
        print("プロファイルが無い。先に --login を実行すること")
        sys.exit(1)
    with sync_playwright() as p:
        ctx = _context(p)                                     # 画面あり・画面外
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        ok = logged_in(page)
        print("ログイン状態:", "OK（エディタを開けている）" if ok else "NG（エディタが開けない。--login をやり直す）")
        ctx.close()
        sys.exit(0 if ok else 1)


def post(name: str, headless: bool = False, dry: bool = False) -> str | None:
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


def _zenn_live() -> set:
    """Zennで実際に公開済みの slug を取る（公開APIなのでログイン不要）。

    取れなかったときは空集合を返し、呼び出し側は従来どおり順番で出す
    （Zennの一時的な不調でnoteまで止めない）。
    """
    import json as _json
    import urllib.request as _u
    url = "https://zenn.dev/api/articles?username=shinsei99&order=latest"
    try:
        with _u.urlopen(url, timeout=10) as r:
            return {a["slug"] for a in _json.load(r).get("articles", [])}
    except Exception as e:
        print("  （Zennの公開状況を取れなかった: %s）" % e)
        return set()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("name", nargs="?")
    ap.add_argument("--login", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--next", action="store_true", dest="nxt")
    ap.add_argument("--dry", action="store_true", help="下書きまでで止める")
    ap.add_argument("--visible", action="store_true", help="ウィンドウを画面内に出す（既定は画面外）")
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
        # order にあるものを先に、無いものはファイル名順で後ろに（週次で足した記事が
        # order に載っていないと、note だけ永久に出ないことになる）
        rest = [x for x in order if x not in done and (NOTE_DIR / f"{x}.md").exists()]
        extra = sorted(f.stem for f in NOTE_DIR.glob("*.md")
                       if f.stem not in done and f.stem not in order)
        rest += extra
        if not rest:
            print("出すものが無い")
            return

        # ★Zennで公開済みのものだけ出す（2026-08-28）。
        #   note は zenn_order.txt の順番だけを見ていたため、**Zennが止まっていても
        #   note だけ進んでしまう**。2026-08-27にZennのデプロイが
        #   ファイル名エラーで全部止まった際、Zenn 11本／note 12本とズレた。
        #   ここでZennの公開APIと突き合わせれば、Zennが詰まればnoteも待つ＝構造的にズレない。
        #   ※Zennに載せない記事（note専用）は order にも無く extra 側で拾われるので、
        #     Zennに存在しない＝待たせる、にはしない（下の allow_solo）。
        live = _zenn_live()
        if live:
            order_set = set(order)
            ready = [x for x in rest if (x in live) or (x not in order_set)]
            waiting = [x for x in rest if x not in ready]
            if waiting and not ready:
                print("Zennでまだ公開されていないので今夜は見送る: %s" % waiting[0])
                print("  （Zennのデプロイが通っているか確認すること）")
                return
            if waiting:
                print("Zenn未公開のため後回し: %s" % " / ".join(waiting[:3]))
            rest = ready
        else:
            print("  （Zennの公開状況を確認できなかったので、順番どおり出す）")

        name = rest[0]
    if not name:
        ap.error("原稿名 か --next が要る")

    url = post(name, headless=False, dry=a.dry)
    if url:
        _remember(name, url)


if __name__ == "__main__":
    main()
