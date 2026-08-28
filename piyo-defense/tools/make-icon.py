#!/usr/bin/env python3
"""ひよこ防衛軍のアプリアイコン（1024）と起動画面（2732）を書き出す。

なぜブラウザを使うか:
  ひよこの絵は `js/render.js` の `drawChick()` が描いている。
  アイコンを別の道具で描き直すと、**ゲームの絵を直したときにアイコンだけ古くなる**。
  同じ関数をブラウザで走らせて撮れば、その食い違いが起きない。

★ App Store のアイコンは **アルファチャンネルを持てない**（透明があると弾かれる）。
  ブラウザが書き出す PNG は RGBA なので、最後に PIL で RGB に落としている。
  角丸も付けない（iOS が自動でマスクする）。

なぜ Chrome の `--screenshot` を使わないか:
  `--headless=new --screenshot` は、このMacでは戻ってこないことがあった（2026-08-28に実測）。
  共通 Visual Agent と同じ **Playwright** で開くほうが確実なので、そちらに寄せている。

必要なもの:
  Playwright が入った Python。`VA_PYTHON` → `agent-platform/.venv` → `.va-venv` の順に探す
  （`va.sh` と同じ探し方）。見つからなければ、そのPythonで叩き直すよう案内して終わる。

書き出し先:
  ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-512@2x.png   ← 実際に使われる1枚
  ios/App/App/Assets.xcassets/Splash.imageset/splash-2732x2732*.png   ← 起動画面（3枚とも同じ絵）
  icon-1024.png                                                       ← 手元確認用の控え

使い方:
    python3 tools/make-icon.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "tools" / "make-icon.html"

ICON_DESTS = [
    ROOT / "ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-512@2x.png",
    ROOT / "icon-1024.png",
]
SPLASH_DESTS = [
    ROOT / "ios/App/App/Assets.xcassets/Splash.imageset/splash-2732x2732.png",
    ROOT / "ios/App/App/Assets.xcassets/Splash.imageset/splash-2732x2732-1.png",
    ROOT / "ios/App/App/Assets.xcassets/Splash.imageset/splash-2732x2732-2.png",
]


def find_python() -> str:
    """Playwright が入った Python を探す（va.sh と同じ順番）。"""
    cands = [os.environ.get("VA_PYTHON"),
             str(Path.home() / "agent-platform/.venv/bin/python3"),
             str(Path.home() / ".va-venv/bin/python3")]
    for c in cands:
        if c and Path(c).exists():
            r = subprocess.run([c, "-c", "import playwright, PIL"], capture_output=True)
            if r.returncode == 0:
                return c
    return ""


SHOOT = r'''
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
from PIL import Image

page_url, mode, size, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), Path(sys.argv[4])

with sync_playwright() as p:
    try:
        b = p.chromium.launch(channel="chrome")      # 共通 Visual Agent と同じ Chrome
    except Exception:
        b = p.chromium.launch()                       # 無ければ同梱 Chromium
    pg = b.new_page(viewport={"width": size, "height": size}, device_scale_factor=1)
    pg.goto(page_url + "?mode=" + mode)
    pg.wait_for_function("window.__ready === true", timeout=30000)
    pg.locator("#c").screenshot(path=str(out), scale="device")
    b.close()

img = Image.open(out)
if img.size != (size, size):
    sys.exit("寸法が違う: %s（期待 %dx%d）" % (img.size, size, size))
# ★ アルファを落とす。App Store は透明を含むアイコンを受け付けない
img.convert("RGB").save(out, "PNG")
print("  撮った: %s %s" % (mode, img.size))
'''


def main() -> None:
    py = find_python()
    if not py:
        sys.exit("Playwright の入った Python が見つからない。\n"
                 "  VA_PYTHON=/path/to/python3 python3 tools/make-icon.py\n"
                 "のように渡すか、agent-platform/.venv を用意すること。")

    with tempfile.TemporaryDirectory() as tmp:
        tmpd = Path(tmp)
        runner = tmpd / "shoot.py"
        runner.write_text(SHOOT, encoding="utf-8")
        url = "file://" + str(PAGE)

        for mode, size, dests in (("icon", 1024, ICON_DESTS), ("splash", 2732, SPLASH_DESTS)):
            out = tmpd / (mode + ".png")
            r = subprocess.run([py, str(runner), url, mode, str(size), str(out)],
                               capture_output=True, text=True, timeout=180)
            if r.returncode != 0 or not out.exists():
                sys.exit("撮影に失敗した（%s）:\n%s\n%s" % (mode, r.stdout[-1500:], r.stderr[-1500:]))
            print(r.stdout.rstrip())
            for d in dests:
                d.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(out, d)
                print("  %-70s %6.1f KB" % (d.relative_to(ROOT), d.stat().st_size / 1024))

    print("\n★ Assets は Xcode が直接読むので `npx cap sync` は不要。ビルドし直せば端末に反映される。")


if __name__ == "__main__":
    main()
