#!/usr/bin/env python3
"""Claude Code の「目」— 見たいものをPNGにして、そのパスを返す道具。

Claude（Claude Code）は**画像ファイルを直接読める**が、画面やWebページを
自分で撮ることはできない。そこを埋めるのがこれ。撮ったPNGのパスを Claude に
渡せば（Read するだけで）中身を見て判断できる。

使い方:
    ./see.sh url http://127.0.0.1:3004        # Webページ・アプリの画面
    ./see.sh url https://example.com --full   # ページ全体（縦に長いものはこれ）
    ./see.sh app 8532                         # 127.0.0.1:<port> の省略形
    ./see.sh screen                           # Mac の画面ぜんぶ
    ./see.sh file 資料.pptx                    # pptx/pdf/docx/画像 の見た目

出力先は `.see/` （リポジトリ直下・gitignore）。同じ名前で上書きせず時刻を付ける。

前提と限界（確かめた事実）:
- Webページは **agent-platform/.venv の Playwright + Chromium** を使う（2026-08-17 確認）。
  agent-platform が無いPCでは `pip install playwright && playwright install chromium` が要る。
- `screen` は macOS の `screencapture`。**「画面収録」の許可**をターミナルに与えていないと
  真っ黒なPNGになる（システム設定 > プライバシーとセキュリティ > 画面収録）。
- `file` は macOS の QuickLook（`qlmanage`）で描く。**1ページ目だけ**。
  pptx の全ページを見たいときは PowerPoint/Keynote でPDFにしてから `file` に渡す。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / ".see"
# Webページ用の Chromium は agent-platform の .venv に入っている（重複導入を避ける）
VENV_PY = ROOT / "agent-platform" / ".venv" / "bin" / "python"


def _stamp(name: str, ext: str = "png") -> Path:
    OUT.mkdir(exist_ok=True)
    return OUT / f"{datetime.now().strftime('%m%d-%H%M%S')}-{name}.{ext}"


def _done(path: Path) -> int:
    """撮れたかを実測して報告する（0バイトや真っ黒を黙って返さない）。"""
    if not path.exists():
        print(f"失敗: {path} が作られなかった", file=sys.stderr)
        return 1
    size = path.stat().st_size
    print(f"{path}  ({size / 1024:.0f} KB)")
    if size < 3 * 1024:
        print("  ⚠️ ファイルが小さい。中身が空か真っ黒の可能性がある", file=sys.stderr)
    return 0


# ---- Webページ・アプリの画面 ------------------------------------------------

_SHOT = r'''
import sys
from playwright.sync_api import sync_playwright

url, out, full, width, height, wait = sys.argv[1:7]
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": int(width), "height": int(height)},
                    device_scale_factor=2)          # 文字が読める解像度で撮る
    pg.goto(url, wait_until="networkidle", timeout=60000)
    pg.wait_for_timeout(int(wait))                  # アニメ・遅延描画の待ち
    pg.screenshot(path=out, full_page=(full == "1"))
    print(pg.title())
    b.close()
'''


def shot_url(url: str, *, full: bool, width: int, height: int, wait: int) -> int:
    if not VENV_PY.exists():
        print("Playwright が無い。agent-platform/.venv を作るか、"
              "pip install playwright && playwright install chromium", file=sys.stderr)
        return 1
    if "://" not in url:
        url = "http://" + url
    out = _stamp(url.split("://", 1)[1].replace("/", "_").replace(":", "-")[:40])
    r = subprocess.run([str(VENV_PY), "-c", _SHOT, url, str(out),
                        "1" if full else "0", str(width), str(height), str(wait)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr.strip()[-1500:], file=sys.stderr)
        return 1
    title = r.stdout.strip()
    if title:
        print(f"title: {title}")
    return _done(out)


# ---- Mac の画面 --------------------------------------------------------------

def shot_screen() -> int:
    out = _stamp("screen")
    # -x シャッター音なし。ウインドウ指定の対話は挟まない（自動実行のため）
    r = subprocess.run(["/usr/sbin/screencapture", "-x", str(out)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr.strip(), file=sys.stderr)
        return 1
    print("※真っ黒なら「画面収録」の許可が無い（システム設定 > プライバシーとセキュリティ）")
    return _done(out)


# ---- ファイル（pptx / pdf / docx / 画像）------------------------------------

def shot_file(target: str, size: int = 2000) -> int:
    src = Path(target).expanduser()
    if not src.exists():
        print(f"無い: {src}", file=sys.stderr)
        return 1
    if src.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        print(f"{src}  (画像なのでそのまま読める)")
        return 0
    if not shutil.which("qlmanage"):
        print("qlmanage が無い（macOS以外？）", file=sys.stderr)
        return 1
    OUT.mkdir(exist_ok=True)
    r = subprocess.run(["qlmanage", "-t", "-s", str(size), "-o", str(OUT), str(src)],
                       capture_output=True, text=True)
    made = OUT / (src.name + ".png")
    if not made.exists():
        print((r.stdout + r.stderr).strip()[-800:], file=sys.stderr)
        print("QuickLook が描けなかった。pdf に変換してから渡す", file=sys.stderr)
        return 1
    out = _stamp(src.stem)
    made.replace(out)
    print("※QuickLook は1ページ目だけ。全ページ見るならPDF化してから渡す")
    return _done(out)


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in {"-h", "--help", "help"}:
        print(__doc__)
        return 0
    cmd, rest = argv[1], argv[2:]
    full = "--full" in rest
    rest = [a for a in rest if a != "--full"]
    width = int(os.environ.get("SEE_WIDTH", 1440))
    height = int(os.environ.get("SEE_HEIGHT", 900))
    wait = int(os.environ.get("SEE_WAIT", 800))

    if cmd == "url" and rest:
        return shot_url(rest[0], full=full, width=width, height=height, wait=wait)
    if cmd == "app" and rest:
        return shot_url(f"http://127.0.0.1:{rest[0]}", full=full,
                        width=width, height=height, wait=wait)
    if cmd == "screen":
        return shot_screen()
    if cmd == "file" and rest:
        return shot_file(rest[0])
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
