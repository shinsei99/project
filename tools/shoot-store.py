#!/usr/bin/env python3
"""App Store 用のスクリーンショットを、ブラウザから**寸法ちょうど**で撮る。

なぜシミュレータを使わないか:
  各アプリの `screenshots/shoot.sh` は「1枚につきアプリを1回ビルドし直して撮る」作り。
  正確だが、6本×2機種×6枚＝72回のビルドになり現実的でない。
  中身は Capacitor で同じ HTML を包んだものなので、**ブラウザで同じ寸法で撮れば絵は同じ**。
  Apple はステータスバーの写り込みを求めていない（無くてよい）。

寸法（`reference_appstore_screenshot_sizes` の実測にもとづく）:
  iPhone  1284×2778   … 428×926   の3倍
  iPad    2048×2732   … 1024×1366 の2倍
  ★新しめのシミュレータの解像度（1206×2622 など）は審査で弾かれる。上の2つに合わせる。

使い方:
    python3 tools/shoot-store.py                 # 全部（iPhone + iPad）
    python3 tools/shoot-store.py --only escape   # 1本だけ
    python3 tools/shoot-store.py --device iphone # 機種を絞る

出力: <アプリ>/screenshots/store/<機種>/NN-<名前>.png
"""
from __future__ import annotations

import argparse
import http.server
import os
import socketserver
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = 8557

# 機種ごとの「CSS上の大きさ」と「倍率」。掛けたものが提出する画素数になる
DEVICES = {
    "iphone": {"w": 428, "h": 926, "scale": 3, "px": "1284×2778"},
    "ipad":   {"w": 1024, "h": 1366, "scale": 2, "px": "2048×2732"},
}

# 撮る対象。src は**各アプリ自身の www**（集合ゲームの切り替え帯が入らないほう）。
# steps は「その画面を作るための JS」。null なら開いたまま撮る。
GAMES = {
    "blocks": {
        "dir": "neon-blocks/www",
        "shots": [
            ("title", None),
            ("play",  "document.getElementById('btnNew')?.click()"),
            ("mid",   "document.getElementById('btnNew')?.click(); loadStage(29)"),
            ("big",   "document.getElementById('btnNew')?.click(); loadStage(82)"),
        ],
    },
    "cyborg": {
        "dir": "cyborg-defense/www",
        "shots": [
            ("title", None),
            ("play",  "document.getElementById('startBtn').click()"),
        ],
    },
    "piyo": {
        "dir": "piyo-defense/www",
        "shots": [
            ("title", None),
            ("play",  "TAP(195,520); await W(500); TAP(195,340)"),
            ("dex",   "gs.state='bestiary'"),
            ("shop",  "gs.state='settings'"),
        ],
    },
    "gravity": {
        "dir": "color-gravity/www",
        "shots": [
            ("title", None),
            ("play",  "document.querySelector('#ov-start')?.click()"),
        ],
    },
    "ice": {
        "dir": "nyanko-ice/www",
        "shots": [
            ("title", None),
            ("play",  "document.getElementById('playBtn').click()"),
        ],
    },
    "escape": {
        "dir": "neko-escape/www",
        "shots": [
            ("title", None),
            ("play",  "document.getElementById('playBtn').click(); await W(300); loadStage(16)"),
            ("late",  "document.getElementById('playBtn').click(); await W(300); loadStage(36)"),
            ("rule",  "document.getElementById('playBtn').click(); await W(300); document.querySelector('.legend').open=true"),
        ],
    },
}


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):  # 静かにする
        pass


def serve(directory: str, port: int):
    # ★閉じた直後のポートは TIME_WAIT で数十秒つかめない。
    #   allow_reuse_address は**生成前のクラス属性**で効かせる必要がある（後から立てても遅い）。
    handler = lambda *a, **k: Quiet(*a, directory=directory, **k)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", port), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


def find_python() -> str:
    for c in (os.environ.get("VA_PYTHON"),
              str(ROOT / "agent-platform/.venv/bin/python3"),
              str(ROOT / ".va-venv/bin/python3")):
        if c and Path(c).exists():
            r = subprocess.run([c, "-c", "import playwright"], capture_output=True)
            if r.returncode == 0:
                return c
    sys.exit("Playwright が入った python が見つからない（VA_PYTHON で指定できる）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="1本だけ（blocks/cyborg/piyo/gravity/ice/escape）")
    ap.add_argument("--device", choices=list(DEVICES), help="機種を絞る")
    args = ap.parse_args()

    py = find_python()
    if Path(sys.executable).resolve() != Path(py).resolve():
        os.execv(py, [py, __file__] + sys.argv[1:])   # Playwright入りのpythonで動かし直す

    from playwright.sync_api import sync_playwright

    games = {args.only: GAMES[args.only]} if args.only else GAMES
    devices = {args.device: DEVICES[args.device]} if args.device else DEVICES
    total = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", args=["--force-color-profile=srgb"])
        for gname, g in games.items():
            httpd = serve(str(ROOT / g["dir"]), PORT)
            try:
                for dname, d in devices.items():
                    out = ROOT / g["dir"].split("/")[0] / "screenshots" / "store" / dname
                    out.mkdir(parents=True, exist_ok=True)
                    ctx = browser.new_context(
                        viewport={"width": d["w"], "height": d["h"]},
                        device_scale_factor=d["scale"],
                        is_mobile=True, has_touch=True,
                    )
                    page = ctx.new_page()
                    for i, (name, setup) in enumerate(g["shots"], 1):
                        page.goto(f"http://127.0.0.1:{PORT}/index.html?shot={name}")
                        page.wait_for_timeout(900)          # 書体と最初の描画を待つ
                        if setup:
                            page.evaluate(
                                "async () => { const W = ms => new Promise(r=>setTimeout(r,ms));"
                                " const cv = document.querySelector('canvas');"
                                " const TAP = (x,y) => { if(!cv) return; const r = cv.getBoundingClientRect();"
                                "   const sx = r.width/(cv.width||r.width), sy = r.height/(cv.height||r.height);"
                                "   const cx = r.x + x*sx, cy = r.y + y*sy;"
                                "   ['pointerdown','pointerup','click'].forEach(t=>cv.dispatchEvent("
                                "     new PointerEvent(t,{clientX:cx,clientY:cy,bubbles:true,pointerId:1,isPrimary:true}))); };"
                                f" {setup}; }}"
                            )
                            page.wait_for_timeout(1400)     # 演出が落ち着くまで
                        f = out / f"{i:02d}-{name}.png"
                        page.screenshot(path=str(f))
                        total += 1
                        print(f"  {gname:8s} {dname:6s} {f.name}  ({d['px']})")
                    ctx.close()
            finally:
                httpd.shutdown()
                httpd.server_close()
        browser.close()

    print(f"\n撮った枚数: {total}")
    print("★提出前に必ず: 1枚ずつ目で見る（状態が作れていない画面が混じることがある）")


if __name__ == "__main__":
    main()
