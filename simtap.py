#!/usr/bin/env python3
"""iOSシミュレータを操作する道具（タップ・なぞる・文字入力・画面の位置合わせ）。

**なぜ要るか**: `xcrun simctl` にはタップが無い。画面を見て直したかどうかを確かめるには、
実際に押して撮る必要がある（CLAUDE.md「画面を見ずに直りましたと言わない」）。

使い方:
    ./simtap.py calib                 # 画面の位置と縮尺を測る（結果はキャッシュ）
    ./simtap.py tap <x> <y>           # デバイスの座標(pt)でタップ
    ./simtap.py drag <x> <y1> <y2>    # 縦になぞる（スクロール）
    ./simtap.py type "文字列"          # 日本語も入る（クリップボード経由）
    ./simtap.py key return|delete     # キーを送る

座標は**デバイスのpt**（iPhone 17 Pro Max なら 440×956）。撮った画像の見た目の座標に
`画面のpt幅 ÷ 画像の幅` を掛ければよい。

つまずき所（実測でわかったこと・2026-08-19）:
  - `osascript` の `click at` は -25204 で失敗する。Quartz のマウスイベントを使う
  - 日本語は `keystroke` だと「あああ」に化ける。`xcrun simctl pbcopy` → ⌘V で入れる
  - ウインドウは端末が大きいと**自動で縮小表示**される。倍率は画面の実測から出す（calib）
"""
import json
import os
import re
import subprocess
import sys
import time

VENV = os.path.expanduser("~/.sim-venv")
CACHE = os.path.expanduser("~/.sim-venv/calib.json")


def ensure_deps():
    """Quartz が無ければ、専用のvenvを作ってそちらで動かし直す。"""
    try:
        import Quartz  # noqa: F401
        import PIL  # noqa: F401
        return
    except ImportError:
        pass
    py = os.path.join(VENV, "bin", "python")
    if not os.path.exists(py):
        base = "/opt/homebrew/bin/python3.12"
        if not os.path.exists(base):
            base = sys.executable
        subprocess.run([base, "-m", "venv", VENV], check=True)
        subprocess.run([py, "-m", "pip", "-q", "install", "pyobjc-framework-Quartz", "pillow"], check=True)
    if os.path.realpath(sys.executable) != os.path.realpath(py):
        os.execv(py, [py, os.path.abspath(__file__)] + sys.argv[1:])
    raise SystemExit("Quartz を用意できませんでした")


ensure_deps()

import Quartz  # noqa: E402
from PIL import Image  # noqa: E402


def sh(*args) -> str:
    return subprocess.check_output(args).decode().strip()


def window_frame():
    """Simulator ウインドウの位置と大きさ（画面のpt）。"""
    out = sh("osascript", "-e", '''
    tell application "System Events" to tell process "Simulator"
      set p to position of window 1
      set s to size of window 1
      return ((item 1 of p) as string) & "," & ((item 2 of p) as string) & "," & ((item 1 of s) as string) & "," & ((item 2 of s) as string)
    end tell''')
    return [float(v) for v in out.split(",")]


def booted_device():
    """起動中のシミュレータ（名前, UDID, 画面のpt幅・高さ）。"""
    data = json.loads(sh("xcrun", "simctl", "list", "devices", "-j"))
    for runtime, devices in data["devices"].items():
        for d in devices:
            if d.get("state") == "Booted":
                return d["name"], d["udid"]
    raise SystemExit("起動中のシミュレータがありません（xcrun simctl boot <名前>）")


def device_size_pt(udid):
    """デバイス画面のpt。スクショの画素数 ÷ 拡大率（Retinaは2〜3倍）。"""
    png = "/tmp/_simtap_probe.png"
    subprocess.run(["xcrun", "simctl", "io", udid, "screenshot", png], check=True,
                   capture_output=True)
    w, h = Image.open(png).size
    os.remove(png)
    # 3x（iPhoneの多く）か 2x（iPad・一部iPhone）か。幅から見分ける
    scale = 3 if w >= 1170 and w % 3 == 0 and (w / 3) < 500 else 2
    return w / scale, h / scale


def calibrate(verbose=True):
    """ウインドウの中で**画面がどこに、どの倍率で**出ているかを測る。

    アプリの背景色（濃い紺）の広がりを見て画面の範囲を割り出す。
    ベゼルは真っ黒なので、色で区別できる。
    """
    name, udid = booted_device()
    dev_w, dev_h = device_size_pt(udid)
    wx, wy, ww, wh = window_frame()
    subprocess.run(["osascript", "-e", 'tell application "Simulator" to activate'], check=True)
    time.sleep(0.5)
    shot = "/tmp/_simtap_win.png"
    subprocess.run(["screencapture", "-x", "-R", f"{wx},{wy},{ww},{wh}", shot], check=True)
    img = Image.open(shot).convert("RGB")
    iw, ih = img.size
    px = img.load()
    ratio = iw / ww  # Retina のMacだと2倍で撮れる

    def dark_app(c):
        # アプリの背景（slate-950/900＝濃い紺）。**青みで見分ける**のが肝。
        # Simulatorのタイトルバーも壁紙も暗いので、明るさだけで見ると全部拾ってしまう
        r, g, b = c
        return 4 <= r <= 45 and (b - r) >= 12 and (b - g) >= 5

    # 画面の外側（ベゼル）は**無彩色の真っ黒**、アプリの背景は**青みのある黒**。
    # 中央から外へ向かって走査し、無彩色の黒が続いた所を画面の端とみなす。
    # 何本かの行・列で測って中央値を採る（本の表紙など明るい所に当たっても外れないように）
    def bezel(c):
        # ベゼルは**無彩色の暗いグレー**（実測 (19,19,19)。真っ黒ではない）。
        # アプリの背景 slate-950 は (3,8,22) で青みがある。そこで色味の差で見分ける
        r, g, b = c
        return r < 70 and abs(b - r) < 7 and abs(g - r) < 7

    def edge(fixed, axis, direction):
        """axis='x' なら横方向に走査して端のindexを返す。direction は -1（左）/+1（右）"""
        limit = (iw if axis == "x" else ih) - 1
        start = limit // 2
        run = 0
        i = start
        while 0 <= i <= limit:
            c = px[i, fixed] if axis == "x" else px[fixed, i]
            if bezel(c):
                run += 1
                if run >= 4 * ratio:
                    return i - direction * int(4 * ratio)
            else:
                run = 0
            i += direction
        return limit if direction > 0 else 0

    def median(vals):
        vals = sorted(vals)
        return vals[len(vals) // 2]

    ys = [int(ih * f) for f in (0.30, 0.40, 0.50, 0.60, 0.70)]
    lpx = median([edge(y, "x", -1) for y in ys])
    rpx = median([edge(y, "x", +1) for y in ys])
    # 縦を測る列は**画面の左右寄り**にとる。中央だと Dynamic Island（黒）を
    # 画面の外と誤認して、上端が島の下に来てしまう（2026-08-19に踏んだ）
    xs = [int(lpx + (rpx - lpx) * f) for f in (0.10, 0.16, 0.84, 0.90)]
    left, right = lpx / ratio, rpx / ratio
    top = median([edge(x, "y", -1) for x in xs]) / ratio
    bottom = median([edge(x, "y", +1) for x in xs]) / ratio
    if right - left < 50 or bottom - top < 50:
        raise SystemExit("画面の範囲を見つけられませんでした（Simulator が前面に出ていますか）")
    scale = (right - left) / dev_w
    calib = {
        "device": name, "udid": udid,
        "dev_w": dev_w, "dev_h": dev_h,
        "origin_x": left, "origin_y": top, "scale": scale,
        "window": [wx, wy, ww, wh],
    }
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump(calib, open(CACHE, "w"))
    if verbose:
        print(f"{name}: 画面 {dev_w:.0f}×{dev_h:.0f}pt / ウインドウ内 左上({left:.0f},{top:.0f}) 倍率 {scale:.3f}")
    return calib


def load_calib():
    try:
        c = json.load(open(CACHE))
    except Exception:
        return calibrate(verbose=False)
    if c.get("window") != list(window_frame()):
        return calibrate(verbose=False)  # 動かされていたら測り直す
    return c


def to_screen(x_pt, y_pt):
    c = load_calib()
    wx, wy, _, _ = c["window"]
    return (wx + c["origin_x"] + x_pt * c["scale"], wy + c["origin_y"] + y_pt * c["scale"])


def front():
    subprocess.run(["osascript", "-e", 'tell application "Simulator" to activate'], check=True)
    time.sleep(0.4)


def post(kind, pos):
    Quartz.CGEventPost(
        Quartz.kCGHIDEventTap,
        Quartz.CGEventCreateMouseEvent(None, kind, pos, Quartz.kCGMouseButtonLeft),
    )


def tap(x, y):
    pos = to_screen(x, y)
    front()
    post(Quartz.kCGEventMouseMoved, pos)
    time.sleep(0.1)
    post(Quartz.kCGEventLeftMouseDown, pos)
    time.sleep(0.08)
    post(Quartz.kCGEventLeftMouseUp, pos)
    print(f"tap ({x},{y}) -> {pos[0]:.0f},{pos[1]:.0f}")


def drag(x, y1, y2, steps=24):
    a, b = to_screen(x, y1), to_screen(x, y2)
    front()
    post(Quartz.kCGEventMouseMoved, a)
    time.sleep(0.15)
    post(Quartz.kCGEventLeftMouseDown, a)
    for i in range(1, steps + 1):
        post(Quartz.kCGEventLeftMouseDragged, (a[0], a[1] + (b[1] - a[1]) * i / steps))
        time.sleep(0.012)
    time.sleep(0.08)
    post(Quartz.kCGEventLeftMouseUp, b)
    print(f"drag x={x} {y1}->{y2}")


def type_text(text):
    """日本語もそのまま入る（キーストロークだと化けるのでクリップボード経由）。"""
    _, udid = booted_device()
    p = subprocess.Popen(["xcrun", "simctl", "pbcopy", udid], stdin=subprocess.PIPE)
    p.communicate(text.encode("utf-8"))
    front()
    subprocess.run(["osascript", "-e",
                    'tell application "System Events" to keystroke "v" using command down'], check=True)
    print(f"type {text!r}")


KEYS = {"return": 36, "delete": 51, "escape": 53, "tab": 48}


def key(name, times=1):
    front()
    code = KEYS.get(name)
    if code is None:
        raise SystemExit(f"知らないキーです: {name}（{'/'.join(KEYS)}）")
    subprocess.run(["osascript", "-e",
                    f'tell application "System Events" to repeat {times} times\nkey code {code}\ndelay 0.05\nend repeat'],
                   check=True)
    print(f"key {name} ×{times}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "calib":
        calibrate()
    elif cmd == "tap":
        tap(float(args[0]), float(args[1]))
    elif cmd == "drag":
        drag(float(args[0]), float(args[1]), float(args[2]))
    elif cmd == "type":
        type_text(args[0])
    elif cmd == "key":
        key(args[0], int(args[1]) if len(args) > 1 else 1)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
