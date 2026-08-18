#!/usr/bin/env python3
"""Visual Agent — Claude Code 自身がブラウザを見て、操作して、UIを検証するための道具。

**なぜ要るのか**: Claude は画像を読めるが、ブラウザを開いて押して確かめることは
自分ではできない。ここが埋まると「直した → 実際に画面で確かめた」までを1人で回せる。

使い方（`./va.sh <コマンド>`）:

    起動・終了
      start [--headed] [--width 1440] [--height 900]   ブラウザを立ち上げて常駐させる
      stop                                             終わる（プロファイルは残る）
      status                                           生きているか・いま何を開いているか

    見る
      goto <url>            ページを開く（遷移もこれ）
      shot [名前] [--full]  スクリーンショット（--full はページ全体）
      dom [セレクタ]         DOMの構造（要素数・見出し・リンクの要約。全文は --raw）
      a11y                  アクセシビリティツリー（スクリーンリーダーが読む形）
      text                  ページの見えているテキスト
      console [--errors]    Console のログ（起動時からぜんぶ拾っている）
      network [--failed]    通信の記録（ステータス・所要ミリ秒）

    触る
      click <セレクタ|"text=文字">     クリック（ボタン・リンク・メニュー・モーダル）
      fill <セレクタ> <文字>           フォーム入力
      upload <セレクタ> <ファイル>      ファイル選択（input[type=file] に直接渡す）
      press <キー>                    Enter / Escape（モーダルを閉じる）/ Tab など
      scroll <down|up|top|bottom> [回数]
      wait <秒>

    検証
      responsive <url>      375 / 768 / 1440 幅で撮って横はみ出しを測る
      check                 UI崩れ・UX問題を機械的に検出（下記）

`check` が見るもの（測れるものだけを見る。主観は入れない）:
  - 横スクロールの発生（`scrollWidth > clientWidth`）と、はみ出している要素の特定
  - 画面外へ出ている要素（右端・下端をまたぐもの）
  - 読み込めていない画像（`naturalWidth == 0`）と alt 無し画像
  - 文字が重なっている箇所（同じ座標に別のテキストが乗っている）
  - 小さすぎる文字（12px未満）、小さすぎるタップ領域（幅か高さが24px未満のボタン/リンク）
  - Console のエラーと、失敗した通信（4xx / 5xx / 接続失敗）
  - 空のリンク（`href="#"` や中身が空のボタン）

**限界（確かめた事実・2026-08-17）**:
- 使うのは `agent-platform/.venv` の Playwright + Chromium（重複導入を避けるため借りている）。
- 常駐は CDP（`127.0.0.1:9223`）越しに繋ぐ方式。**Console と Network は常駐プロセスが
  起動時から拾い続ける**ので、後から `console` で読んでも取りこぼさない。
- **パスワードの入力はしない。** ログインが要る画面は、人が入るか、
  すでにログイン済みの実ブラウザ（Chrome拡張）側で扱う。`fill` は一般のフォーム用。
- ここで開くのは**専用プロファイル**（`.see/profile`）で、普段のChromeとは別物。
  だから普段のログイン状態は無い。あるものを使いたいときは Chrome拡張のほう。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / ".see"
PROFILE = OUT / "profile"
CONSOLE_LOG = OUT / "console.jsonl"
NETWORK_LOG = OUT / "network.jsonl"
STATE = OUT / "va-state.json"
STOP = OUT / "va-stop"
CDP_PORT = 9223
VENV_PY = ROOT / "agent-platform" / ".venv" / "bin" / "python"


def _py() -> str:
    if not VENV_PY.exists():
        sys.exit("Playwright が無い。agent-platform/.venv を作るか "
                 "pip install playwright && playwright install chromium")
    return str(VENV_PY)


def _stamp(name: str) -> Path:
    OUT.mkdir(exist_ok=True)
    safe = re.sub(r"[^\w.-]", "_", name)[:40]
    return OUT / f"{datetime.now().strftime('%m%d-%H%M%S')}-{safe}.png"


# ============================================================================
# 常駐プロセス（start が中でこれを呼ぶ）
#   ブラウザを開き、Console と Network を拾い続けるだけの番人。
#   操作は別プロセスから CDP で繋いで行う。
# ============================================================================

DAEMON = r'''
import json, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

profile, console_log, network_log, stop_file, port, headed, w, h = sys.argv[1:9]
Path(console_log).write_text("")
Path(network_log).write_text("")

def append(path, obj):
    with open(path, "a") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        profile,
        headless=(headed != "1"),
        viewport={"width": int(w), "height": int(h)},
        device_scale_factor=2,
        args=[f"--remote-debugging-port={port}"],
    )
    started = {}

    def hook(page):
        page.on("console", lambda m: append(console_log, {
            "t": time.strftime("%H:%M:%S"), "type": m.type,
            "text": m.text[:2000], "url": page.url}))
        page.on("pageerror", lambda e: append(console_log, {
            "t": time.strftime("%H:%M:%S"), "type": "pageerror",
            "text": str(e)[:2000], "url": page.url}))
        page.on("request", lambda r: started.__setitem__(r, time.time()))

        def done(res):
            t0 = None
            for req, ts in list(started.items()):
                if req is res.request:
                    t0 = ts
                    started.pop(req, None)
                    break
            append(network_log, {"t": time.strftime("%H:%M:%S"), "status": res.status,
                                 "method": res.request.method, "url": res.url[:300],
                                 "ms": int((time.time() - t0) * 1000) if t0 else None,
                                 "type": res.request.resource_type})
        page.on("response", done)
        page.on("requestfailed", lambda r: append(network_log, {
            "t": time.strftime("%H:%M:%S"), "status": "failed", "method": r.method,
            "url": r.url[:300], "error": (r.failure or "")[:200],
            "type": r.resource_type}))

    for pg in ctx.pages:
        hook(pg)
    ctx.on("page", hook)

    if not ctx.pages:
        hook(ctx.new_page())

    Path(stop_file).unlink(missing_ok=True)
    # ★ time.sleep で待つと Playwright(sync) のイベントが配送されず、console/network を
    #   1件も拾えない（2026-08-17に実測）。**Playwright の待ちで回す**のが正解。
    while not Path(stop_file).exists():
        try:
            (ctx.pages[0] if ctx.pages else ctx.new_page()).wait_for_timeout(300)
        except Exception:
            time.sleep(0.3)          # 遷移中などで待てないときだけ素の sleep
    ctx.close()
'''


def cmd_start(headed: bool, width: int, height: int) -> int:
    if _alive():
        print("すでに起動している（./va.sh status で確認）")
        return 0
    OUT.mkdir(exist_ok=True)
    PROFILE.mkdir(exist_ok=True)
    STOP.unlink(missing_ok=True)
    log = open(OUT / "va-daemon.log", "w")
    subprocess.Popen([_py(), "-c", DAEMON, str(PROFILE), str(CONSOLE_LOG), str(NETWORK_LOG),
                      str(STOP), str(CDP_PORT), "1" if headed else "0", str(width), str(height)],
                     stdout=log, stderr=log, start_new_session=True)
    for _ in range(50):                       # 最大20秒待つ
        time.sleep(0.4)
        if _alive():
            STATE.write_text(json.dumps({"headed": headed, "w": width, "h": height}))
            print(f"起動した（{'画面あり' if headed else 'headless'} {width}x{height}・CDP {CDP_PORT}）")
            return 0
    print((OUT / "va-daemon.log").read_text()[-1500:], file=sys.stderr)
    return 1


def _alive() -> bool:
    import urllib.request
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=1).read()
        return True
    except Exception:
        return False


def cmd_stop() -> int:
    if not _alive():
        print("動いていない")
        return 0
    STOP.touch()
    for _ in range(25):
        time.sleep(0.4)
        if not _alive():
            print("終了した")
            return 0
    print("終わらないので kill する", file=sys.stderr)
    subprocess.run(["pkill", "-f", f"remote-debugging-port={CDP_PORT}"])
    return 0


# ============================================================================
# 操作（CDPで繋いで1回だけ動かす）
# ============================================================================

ACT = r'''
import json, sys
from playwright.sync_api import sync_playwright

port, action = sys.argv[1], sys.argv[2]
args = sys.argv[3:]

def target(page, sel):
    """"text=..." はテキスト一致、それ以外はCSS/Playwrightセレクタとして扱う。"""
    return page.locator(sel).first

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
    ctx = b.contexts[0]
    page = ctx.pages[-1] if ctx.pages else ctx.new_page()

    if action == "goto":
        page.goto(args[0], wait_until="networkidle", timeout=60000)
        print(json.dumps({"url": page.url, "title": page.title()}, ensure_ascii=False))

    elif action == "shot":
        page.wait_for_timeout(400)
        page.screenshot(path=args[0], full_page=(args[1] == "1"))
        print(json.dumps({"url": page.url, "title": page.title()}, ensure_ascii=False))

    elif action == "click":
        el = target(page, args[0])
        el.scroll_into_view_if_needed(timeout=5000)
        box = el.bounding_box()
        el.click(timeout=10000)
        page.wait_for_timeout(600)
        print(json.dumps({"clicked": args[0], "box": box, "url": page.url}, ensure_ascii=False))

    elif action == "upload":
        # ファイル選択（<input type=file>）。ダイアログを開かずに直接渡す。
        # ★多くのUIは input を隠している（class="hidden"）。隠れたままだと
        #   set_input_files が待ち続けてタイムアウトするので、**一時的に見える状態に戻す**。
        page.eval_on_selector(args[0], """el => {
            el.classList.remove('hidden');
            el.removeAttribute('hidden');
            el.style.display = 'block';
            el.style.visibility = 'visible';
            el.style.opacity = '1';
            el.style.position = 'fixed';
            el.style.left = '0px';
            el.style.top = '0px';
            el.style.width = '200px';
            el.style.height = '30px';
        }""")
        page.set_input_files(args[0], args[1], timeout=20000)
        page.wait_for_timeout(500)
        print(json.dumps({"uploaded": args[1], "to": args[0]}, ensure_ascii=False))

    elif action == "fill":
        target(page, args[0]).fill(args[1], timeout=10000)
        print(json.dumps({"filled": args[0]}, ensure_ascii=False))

    elif action == "press":
        page.keyboard.press(args[0])
        page.wait_for_timeout(400)
        print(json.dumps({"pressed": args[0], "url": page.url}, ensure_ascii=False))

    elif action == "scroll":
        how, n = args[0], int(args[1])
        if how == "top":
            page.evaluate("window.scrollTo(0,0)")
        elif how == "bottom":
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        else:
            page.mouse.wheel(0, (500 if how == "down" else -500) * n)
        page.wait_for_timeout(400)
        print(json.dumps({"scrollY": page.evaluate("window.scrollY")}))

    elif action == "size":
        page.set_viewport_size({"width": int(args[0]), "height": int(args[1])})
        page.wait_for_timeout(500)
        print(json.dumps({"viewport": page.viewport_size}))

    elif action == "text":
        print(page.inner_text("body")[:8000])

    elif action == "a11y":
        snap = page.accessibility.snapshot()
        print(json.dumps(snap, ensure_ascii=False)[:20000])

    elif action == "dom":
        sel = args[0] if args else "body"
        info = page.evaluate("""(sel) => {
          const root = document.querySelector(sel) || document.body;
          const pick = (list, f) => Array.from(list).slice(0, 40).map(f);
          return {
            url: location.href, title: document.title,
            elements: root.querySelectorAll('*').length,
            headings: pick(root.querySelectorAll('h1,h2,h3'),
                           e => e.tagName + ': ' + e.innerText.trim().slice(0, 80)),
            links: pick(root.querySelectorAll('a'),
                        a => (a.innerText.trim().slice(0, 40) || '(文字なし)') + ' -> ' + a.getAttribute('href')),
            buttons: pick(root.querySelectorAll('button,[role=button],input[type=submit]'),
                          b => (b.innerText || b.value || '(文字なし)').trim().slice(0, 40)),
            inputs: pick(root.querySelectorAll('input,textarea,select'),
                         i => i.tagName.toLowerCase() + '[' + (i.type||'') + '] name=' + (i.name||'') +
                              ' placeholder=' + (i.placeholder||'')),
          };
        }""", sel)
        print(json.dumps(info, ensure_ascii=False, indent=2))

    elif action == "eval":
        # 原因を1つに絞り込むための物差し。計測に使う（副作用のある操作には使わない）
        print(json.dumps(page.evaluate(args[0]), ensure_ascii=False, indent=2)[:20000])

    elif action == "state":
        print(json.dumps({"url": page.url, "title": page.title(),
                          "viewport": page.viewport_size, "pages": len(ctx.pages)},
                         ensure_ascii=False))

    elif action == "check":
        # 測れるものだけを見る。主観（きれい/見づらい）はここでは出さない。
        report = page.evaluate("""() => {
          const vw = document.documentElement.clientWidth;
          const vh = document.documentElement.clientHeight;
          const out = {viewport:{w:vw,h:vh}, horizontal_scroll:null, overflow:[], offscreen:[],
                       broken_images:[], images_without_alt:0, overlapping_text:[],
                       tiny_text:[], small_targets:[], empty_links:[]};
          const de = document.documentElement;
          if (de.scrollWidth > de.clientWidth + 1)
            out.horizontal_scroll = {scrollWidth: de.scrollWidth, clientWidth: de.clientWidth};
          const label = e => {
            const id = e.id ? '#'+e.id : '';
            const cls = (typeof e.className === 'string' && e.className) ?
                        '.'+e.className.trim().split(/\s+/).slice(0,2).join('.') : '';
            return e.tagName.toLowerCase()+id+cls;
          };
          const all = Array.from(document.querySelectorAll('body *'));
          for (const e of all) {
            const r = e.getBoundingClientRect();
            if (r.width === 0 || r.height === 0) continue;
            const st = getComputedStyle(e);
            if (st.visibility === 'hidden' || st.display === 'none' || st.position === 'fixed') continue;
            if (r.right > vw + 2 && r.width <= vw && out.overflow.length < 15)
              out.overflow.push({el: label(e), right: Math.round(r.right), over: Math.round(r.right - vw)});
            if (r.left < -2 && out.offscreen.length < 15)
              out.offscreen.push({el: label(e), left: Math.round(r.left)});
            const fs = parseFloat(st.fontSize);
            const txt = (e.childNodes.length && Array.from(e.childNodes)
                          .some(n => n.nodeType === 3 && n.textContent.trim()));
            if (txt && fs && fs < 12 && out.tiny_text.length < 15)
              out.tiny_text.push({el: label(e), fontSize: st.fontSize,
                                  text: e.innerText.trim().slice(0,40)});
          }
          for (const img of document.querySelectorAll('img')) {
            if (img.complete && img.naturalWidth === 0 && out.broken_images.length < 15)
              out.broken_images.push({src: (img.currentSrc||img.src||'').slice(0,150)});
            if (!img.getAttribute('alt')) out.images_without_alt++;
          }
          for (const b of document.querySelectorAll('a,button,[role=button],input[type=submit]')) {
            const r = b.getBoundingClientRect();
            if (r.width === 0 || r.height === 0) continue;
            if ((r.width < 24 || r.height < 24) && out.small_targets.length < 15)
              out.small_targets.push({el: label(b), w: Math.round(r.width), h: Math.round(r.height),
                                      text: (b.innerText||'').trim().slice(0,30)});
            const href = b.getAttribute && b.getAttribute('href');
            const empty = (!(b.innerText||'').trim() && !b.querySelector('img,svg,[aria-label]') &&
                           !b.getAttribute('aria-label'));
            if ((href === '#' || href === '' || empty) && out.empty_links.length < 15)
              out.empty_links.push({el: label(b), href: href});
          }
          // 文字の重なり: 見出し・段落・リンクの矩形が互いに深く重なっていないか
          const texts = Array.from(document.querySelectorAll('h1,h2,h3,h4,p,a,span,li,button'))
            .filter(e => (e.innerText||'').trim().length > 1)
            .map(e => ({e, r: e.getBoundingClientRect()}))
            .filter(o => o.r.width > 8 && o.r.height > 8).slice(0, 400);
          for (let i = 0; i < texts.length; i++) {
            for (let j = i+1; j < texts.length; j++) {
              const a = texts[i], b = texts[j];
              if (a.e.contains(b.e) || b.e.contains(a.e)) continue;
              const ov = Math.max(0, Math.min(a.r.right,b.r.right) - Math.max(a.r.left,b.r.left)) *
                         Math.max(0, Math.min(a.r.bottom,b.r.bottom) - Math.max(a.r.top,b.r.top));
              const small = Math.min(a.r.width*a.r.height, b.r.width*b.r.height);
              if (small > 0 && ov / small > 0.5 && out.overlapping_text.length < 10)
                out.overlapping_text.push({a: label(a.e), b: label(b.e),
                                           overlap: Math.round(ov/small*100)+'%'});
            }
          }
          return out;
        }""")
        report["url"] = page.url
        print(json.dumps(report, ensure_ascii=False, indent=2))

    else:
        print(json.dumps({"error": "unknown action " + action}))
'''


def _act(action: str, *args: str, quiet: bool = False) -> int:
    if not _alive():
        print("ブラウザが起動していない。まず ./va.sh start", file=sys.stderr)
        return 1
    r = subprocess.run([_py(), "-c", ACT, str(CDP_PORT), action, *[str(a) for a in args]],
                       capture_output=True, text=True)
    if r.stdout and not quiet:
        print(r.stdout.rstrip())
    if r.returncode != 0:
        print(r.stderr.strip()[-1500:], file=sys.stderr)
    return r.returncode


def _tail_log(path: Path, *, only_bad: bool, kind: str, n: int = 40) -> int:
    if not path.exists():
        print("記録がまだ無い（start してから goto すると溜まる）")
        return 0
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    if only_bad:
        if kind == "console":
            rows = [r for r in rows if r.get("type") in ("error", "pageerror", "warning")]
        else:
            rows = [r for r in rows
                    if r.get("status") == "failed" or (isinstance(r.get("status"), int)
                                                       and r["status"] >= 400)]
    print(f"{len(rows)} 件（末尾 {min(n, len(rows))} 件を表示）")
    for r in rows[-n:]:
        if kind == "console":
            print(f"  [{r['t']}] {r['type']:9} {r['text'][:160]}")
        else:
            ms = f"{r['ms']}ms" if r.get("ms") is not None else "-"
            print(f"  [{r['t']}] {str(r['status']):6} {r['method']:4} {ms:>7}  "
                  f"{r.get('type','')[:8]:8} {r['url'][:110]}")
    return 0


def cmd_responsive(url: str | None) -> int:
    """携帯・タブレット・PCの3幅で撮って、横はみ出しの有無を測る。"""
    sizes = [(390, 844, "mobile"), (768, 1024, "tablet"), (1440, 900, "desktop")]
    saved = json.loads(STATE.read_text()) if STATE.exists() else {"w": 1440, "h": 900}
    for w, h, name in sizes:
        _act("size", w, h, quiet=True)
        if url:
            _act("goto", url, quiet=True)      # 幅で出し分けるサイトがあるので撮り直す
        out = _stamp(f"{name}-{w}")
        print(f"\n── {name} {w}x{h} ──")
        _act("shot", str(out), "1", quiet=True)
        if out.exists():
            print(f"  画像: {out}  ({out.stat().st_size/1024:.0f} KB)")
        r = subprocess.run([_py(), "-c", ACT, str(CDP_PORT), "check"],
                           capture_output=True, text=True)
        try:
            rep = json.loads(r.stdout)
            hs = rep.get("horizontal_scroll")
            ov, tg = len(rep.get("overflow", [])), len(rep.get("small_targets", []))
            cap = lambda n: f"{n}件{'（上限。もっとある）' if n >= 15 else ''}"
            print(f"  横スクロール: {'⚠️ ' + json.dumps(hs) if hs else 'なし'}"
                  f" / はみ出し要素 {cap(ov)} / 小さいタップ領域 {cap(tg)}"
                  f" / 読めない画像 {len(rep.get('broken_images', []))}件"
                  f" / 文字の重なり {len(rep.get('overlapping_text', []))}件")
        except Exception:
            print("  check に失敗", file=sys.stderr)
    _act("size", saved.get("w", 1440), saved.get("h", 900))
    print(f"\n撮った画像は {OUT} にある（Claude はこれを Read して目で見る）")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in {"-h", "--help", "help"}:
        print(__doc__)
        return 0
    cmd, rest = argv[1], argv[2:]
    flags = {a for a in rest if a.startswith("--")}
    pos = [a for a in rest if not a.startswith("--")]

    def opt(name: str, default: int) -> int:
        for a in rest:
            if a.startswith(f"--{name}="):
                return int(a.split("=", 1)[1])
        if f"--{name}" in rest:
            i = rest.index(f"--{name}")
            if i + 1 < len(rest):
                return int(rest[i + 1])
        return default

    if cmd == "start":
        return cmd_start("--headed" in flags, opt("width", 1440), opt("height", 900))
    if cmd == "stop":
        return cmd_stop()
    if cmd == "status":
        print("起動中" if _alive() else "停止中")
        return _act("state") if _alive() else 0
    if cmd == "goto" and pos:
        # `localhost:8532` のような省略形だけ http:// を足す。
        # data: / file: / about: などスキームが付いているものはそのまま渡す
        url = pos[0] if re.match(r"^[a-z][a-z0-9+.-]*:", pos[0]) else "http://" + pos[0]
        return _act("goto", url)
    if cmd == "shot":
        name = pos[0] if pos else "shot"
        out = _stamp(name)
        rc = _act("shot", str(out), "1" if "--full" in flags else "0")
        if out.exists():
            print(f"{out}  ({out.stat().st_size/1024:.0f} KB)")
        return rc
    if cmd == "click" and pos:
        return _act("click", pos[0])
    if cmd == "upload" and len(pos) >= 2:
        return _act("upload", pos[0], str(Path(pos[1]).expanduser().resolve()))
    if cmd == "fill" and len(pos) >= 2:
        return _act("fill", pos[0], " ".join(pos[1:]))
    if cmd == "press" and pos:
        return _act("press", pos[0])
    if cmd == "scroll":
        how = pos[0] if pos else "down"
        return _act("scroll", how, pos[1] if len(pos) > 1 else "3")
    if cmd == "size" and len(pos) >= 2:
        return _act("size", pos[0], pos[1])
    if cmd in {"text", "a11y", "check"}:
        return _act(cmd)
    if cmd == "eval" and pos:
        return _act("eval", " ".join(pos))
    if cmd == "dom":
        return _act("dom", pos[0] if pos else "body")
    if cmd == "wait" and pos:
        time.sleep(float(pos[0]))
        return 0
    if cmd == "console":
        return _tail_log(CONSOLE_LOG, only_bad="--errors" in flags, kind="console")
    if cmd == "network":
        return _tail_log(NETWORK_LOG, only_bad="--failed" in flags, kind="network")
    if cmd == "responsive":
        return cmd_responsive(pos[0] if pos else None)
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
