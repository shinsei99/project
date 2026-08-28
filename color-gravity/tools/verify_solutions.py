#!/usr/bin/env python3
"""カラー・グラビティ — 全20面の「正解を見る」が本当にクリアに届くかを機械で確かめる。

なぜ要るか:
  各ステージの `sol`（正解の発射ベクトル）は、この物理で解いた実測値。
  重力定数・速度上限・当たり判定の半径を1つ変えただけで軌道がずれ、
  20面ぶんの「💡 正解を見る」が静かに的を外す。**画面を見ても気づけない**
  （それらしい軌道を描いて外れるだけなので、目視では「そういう面」に見える）。

  だから見た目をいじったあとは必ずこれを流す。落ちたら物理を触っている。

やり方:
  index.html の `物理ここから 〜 物理ここまで` の区間をそのまま抜き出して node で実行する。
  ゲーム本体と同じソースを動かすので、実装が二重にならない（写した式がずれる事故が起きない）。

使い方:
    python3 tools/verify_solutions.py          # 20面を全部
    python3 tools/verify_solutions.py 5 7      # 面番号を指定（1始まり）
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "www" / "index.html"
BEGIN = "/* ===================== 物理ここから"
END = "/* ===================== 物理ここまで ===================== */"

DRIVER = r"""
// 「正解を見る」と同じ手順で sol を飛ばし、どこで終わったかを返す
const out = [];
for (let i = 0; i < STAGES.length; i++) {
  const st = JSON.parse(JSON.stringify(STAGES[i]));
  const s = { x: st.cannon.x, y: st.cannon.y, vx: st.sol.vx, vy: st.sol.vy, color: new Set(st.start) };
  const tg = new Set();
  let ev = 'none', steps = 0;
  for (; steps < 1500; steps++) {
    ev = stepSim(s, st, tg);
    if (ev === 'win' || ev === 'crash' || ev === 'out' || ev === 'blackhole') break;
  }
  out.push({ n: i + 1, name: st.name, ev, steps, gates: st.gates.length, passed: tg.size,
             want: st.crystal.key, got: [...s.color].sort().join('') });
}
console.log(JSON.stringify(out));
"""


def physics_source() -> str:
    text = SRC.read_text(encoding="utf-8")
    a = text.find(BEGIN)
    b = text.find(END)
    if a < 0 or b < 0:
        sys.exit("ERROR: index.html に『物理ここから／ここまで』の目印が見つからない")
    return text[a:b]


def main() -> int:
    want = {int(a) for a in sys.argv[1:]} if len(sys.argv) > 1 else None
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(physics_source() + DRIVER)
        js = f.name
    try:
        r = subprocess.run(["node", js], capture_output=True, text=True)
    finally:
        Path(js).unlink(missing_ok=True)
    if r.returncode != 0:
        print(r.stderr.strip())
        return 2

    rows = json.loads(r.stdout)
    ng = 0
    for row in rows:
        if want and row["n"] not in want:
            continue
        ok = row["ev"] == "win"
        if not ok:
            ng += 1
        mark = "OK  " if ok else "NG  "
        note = "" if ok else f"  ← {row['ev']} / 色 {row['got'] or '無色'} (目標 {row['want']})"
        print(f"{mark}{row['n']:>2}. {row['name']:<22} {row['steps']:>4}歩"
              f"  ゲート {row['passed']}/{row['gates']}{note}")
    total = len(want) if want else len(rows)
    print(f"\n{'全' if not want else ''}{total}面中 {total - ng} 面が正解に到達"
          + ("" if ng == 0 else f"  ★{ng}面がクリアに届いていない＝物理を壊している"))
    return 1 if ng else 0


if __name__ == "__main__":
    raise SystemExit(main())
