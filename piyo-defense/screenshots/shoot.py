#!/usr/bin/env python3
"""App Store 用のスクリーンショットを撮る。

なぜシミュレータを使わないか:
  このゲームは 390×844 の canvas 1枚を画面に合わせて拡大しているだけなので、
  **ブラウザを端末と同じ論理サイズ×倍率で開けば、実機と同じ絵になる**。
  シミュレータ経由（にゃんこアイスのやり方）より速く、Simulator.app が
  ウインドウを開かない問題（2026-08-28 時点で未解決）にも引っかからない。

  ※「実機で撮ったものでなければならない」という決まりは無い。寸法さえ合っていればよい。

Apple が受け付ける寸法（2026-08 時点）:
  iPhone 6.5型 : 1284 × 2778   ← 論理 428×926 × 3
  iPad 12.9型  : 2048 × 2732   ← 論理 1024×1366 × 2
  ※シミュレータの素の解像度（1206×2622 など）は弾かれる。ここでは最初から正しい寸法で撮る。

撮る5枚:
  title / battle / tower / boss / bestiary

使い方:
    python3 screenshots/shoot.py              # 両方の端末で5枚ずつ
    python3 screenshots/shoot.py --device ipad
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "screenshots" / "upload"

DEVICES = {
    # 名前: (論理幅, 論理高さ, 倍率) → 書き出し寸法
    "iphone": (428, 926, 3),    # 1284 × 2778
    "ipad": (1024, 1366, 2),    # 2048 × 2732
}

# (名前, 状態を作る秒数のあとに待つミリ秒)
SHOTS = [("title", 400), ("battle", 2200), ("tower", 2600), ("boss", 2600), ("bestiary", 400)]

# ★ 内部オブジェクト（弾など）を手で作って配列に入れてはいけない。
#   足りないフィールドがあると update() が例外を投げ、**requestAnimationFrame の輪が切れて
#   描画がその場で止まる**（画面は直前のタイトルのまま固まる。2026-08-28 に実際に踏んだ）。
#   状態だけ作って、あとは数秒ゲームを走らせれば、弾も爆発も自然に出る。
SETUP = {
    # SaveManager に setter は無いので localStorage を直接置く（キーは js/save.js の _k）
    "title": """
        localStorage.setItem('piyo_hs', '48200');
        localStorage.setItem('piyo_bs', '12');
        localStorage.setItem('piyo_coins_v2', '860');
        gs.state = 'title';
    """,
    "battle": """
        initGame(); stage = 4; wave = 3; gs.state = 'battle'; stageIntroTimer = 0;
        score = 12480; level = 7; xp = 12; runCoins = 34;
        for (var i = 0; i < 7; i++) spawnEnemy(['normal','fast','ranged','fast','normal','ranged','normal'][i]);
        enemies.forEach(function(e, i) { e.y = 90 + i * 78; e.x = 60 + ((i * 97) % 270); });
    """,
    "tower": """
        initGame(); stage = 8; wave = 2; gs.state = 'battle'; stageIntroTimer = 0;
        score = 41250; level = 14; xp = 20; runCoins = 121;
        gs.evoGauge = 68;
        TOWER_SLOTS[0].type = 'sniper';  TOWER_SLOTS[0].level = 3;
        TOWER_SLOTS[0].maxHp = 70; TOWER_SLOTS[0].hp = 70;
        TOWER_SLOTS[1].type = 'rapid';   TOWER_SLOTS[1].level = 2;
        TOWER_SLOTS[1].maxHp = 60; TOWER_SLOTS[1].hp = 52;
        for (var i = 0; i < 5; i++) spawnEnemy(['armored','regen','armored','tank','regen'][i]);
        enemies.forEach(function(e, i) { e.y = 120 + i * 92; e.x = 70 + ((i * 121) % 250); });
    """,
    "boss": """
        initGame(); stage = 10; wave = 5; gs.state = 'battle'; stageIntroTimer = 0;
        score = 68400; level = 18; xp = 4; runCoins = 240;
        gs.isEvolved = true; gs.evoTimer = 900; gs.evoGauge = 100;
        spawnEnemy('boss_s10');
        enemies[0].hp = Math.round(enemies[0].maxHp * 0.62);
        for (var i = 0; i < 3; i++) spawnEnemy('shielded');
        enemies.slice(1).forEach(function(e, i) { e.y = 340 + i * 88; e.x = 70 + i * 120; });
    """,
    # 図鑑は「集める楽しさ」を見せたいので、半分ほど埋まった状態にする
    "bestiary": """
        var b = {};
        BESTIARY_TYPES.slice(0, 12).forEach(function(t, i) { b[t] = 7 + i * 9; });
        localStorage.setItem('piyo_bestiary_v2', JSON.stringify(b));
        gs.state = 'bestiary';
    """,
}

SHOOT = r'''
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

url, out_dir, w, h, scale, plan = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), json.loads(sys.argv[6])
out_dir.mkdir(parents=True, exist_ok=True)

# 走らせている間に地球HPが減って負けてしまわないように押さえる。
# あわせて実績ポップアップを消す（撮影のたびに出ると絵が毎回変わる）。
PIN = """
() => {
  window.__pin = setInterval(function () {
    if (typeof gs !== 'undefined' && gs.maxEarthHP) gs.earthHP = gs.maxEarthHP;
    if (typeof achievePopup !== 'undefined') { achievePopup = null; achieveQueue = []; }
  }, 30);
}
"""

with sync_playwright() as p:
    try:
        b = p.chromium.launch(channel="chrome")
    except Exception:
        b = p.chromium.launch()
    for idx, (name, setup, settle) in enumerate(plan, start=1):
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=scale)
        pg = ctx.new_page()
        pg.goto(url)
        pg.wait_for_function("typeof gs !== 'undefined' && document.fonts.status === 'loaded'", timeout=30000)
        pg.evaluate("() => { " + setup + " }")
        pg.evaluate(PIN)
        pg.wait_for_timeout(settle)
        # 描画が止まっていないか（rAFの輪が生きているか）を必ず確かめる。
        # 止まったまま撮ると、直前の画面が写ったスクショが混ざる。
        alive = pg.evaluate("() => new Promise(r => { var a = frame; requestAnimationFrame(() => r(frame !== a)); })")
        if not alive:
            sys.exit("描画が止まっている（%s）。update() が例外を投げていないか確認すること" % name)
        dest = out_dir / ("%d_%s.png" % (idx, name))
        pg.screenshot(path=str(dest), scale="device")
        state = pg.evaluate("() => gs.state")
        print("  %-16s state=%s" % (dest.name, state))
        ctx.close()
    b.close()
'''


def find_python() -> str:
    cands = [os.environ.get("VA_PYTHON"),
             str(Path.home() / "agent-platform/.venv/bin/python3"),
             str(Path.home() / ".va-venv/bin/python3")]
    for c in cands:
        if c and Path(c).exists():
            if subprocess.run([c, "-c", "import playwright"], capture_output=True).returncode == 0:
                return c
    return ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", choices=list(DEVICES) + ["both"], default="both")
    ap.add_argument("--url", default="http://127.0.0.1:8899/",
                    help="ゲームを配っているURL（python3 -m http.server で立てておく）")
    args = ap.parse_args()

    py = find_python()
    if not py:
        sys.exit("Playwright の入った Python が見つからない（VA_PYTHON で渡せる）")

    import json as _json
    plan = _json.dumps([[name, SETUP[name], settle] for name, settle in SHOTS])
    devices = list(DEVICES) if args.device == "both" else [args.device]

    with tempfile.TemporaryDirectory() as tmp:
        runner = Path(tmp) / "shoot.py"
        runner.write_text(SHOOT, encoding="utf-8")
        for dev in devices:
            w, h, sc = DEVICES[dev]
            print("■ %s  %d×%d（論理 %d×%d ×%d）" % (dev, w*sc, h*sc, w, h, sc))
            r = subprocess.run([py, str(runner), args.url, str(OUT / dev), str(w), str(h), str(sc), plan],
                               capture_output=True, text=True, timeout=300)
            print(r.stdout.rstrip())
            if r.returncode != 0:
                sys.exit("撮影に失敗:\n" + r.stderr[-2000:])

    print("\n書き出し先: %s" % OUT)
    print("投入は push-screenshots.py で行う（寸法はここで合わせてあるので sips は不要）")


if __name__ == "__main__":
    main()
