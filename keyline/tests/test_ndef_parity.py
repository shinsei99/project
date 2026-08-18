"""ndef.py（サーバー）と tagapp/www/ndef.js（アプリ）が同じ形式で書くことを確かめる。

★これが崩れると、アプリで書いたタグをサーバーが読めない（またはその逆）。
  タグは物理的に書き直しになるため、気づくのが遅いほど痛い。
  どちらかを直したら必ずこのテストを通すこと。

実行:  cd ~/keyline && /usr/bin/python3 tests/test_ndef_parity.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

import ndef  # noqa: E402

URL = "http://192.168.1.105:8534/t/qb767czs8kc2ry43"

# 物件名, 鍵の名称, 鍵番号, ボックス, 位置, タグ種別
CASES = [
    ("大阪京橋ビル", "1階エントランスキー", "10001,10002", "BOX-01", "03", "NTAG213"),
    ("大阪京橋ビル", "機械室キー", "10003 ×3", "BOX-01", "04", "NTAG213"),
    ("大阪京橋ビル別館", "地下1階機械室入口キー", "10001,10002,10003", "BOX-01", "12", "NTAG213"),
    # 溢れるケース。名前だけ縮み、鍵番号とボックスが残ることを見る
    ("角屋(横堤)モータープール管理棟", "1階事務所エントランス自動ドア", "77001,77002,77003", "BOX-02", "01", "NTAG213"),
    ("大阪京橋ビル別館第2駐車場管理棟", "地下1階機械室および電気室入口共通キー",
     "77001,77002,77003", "BOX-02", "01", "NTAG213"),
    # ボックス未設定（'-03' にならないこと）
    (None, "3階倉庫", "30012 ×2", None, "30", "NTAG213"),
    # 物件名なし・鍵番号なし
    (None, "予備キー", None, "BOX-03", "01", "NTAG213"),
    # 容量の大きいタグなら縮まない
    ("角屋(横堤)モータープール管理棟", "1階事務所エントランス自動ドア", "77001,77002,77003", "BOX-02", "01", "NTAG215"),
]

JS_RUNNER = """
import * as N from './ndef.mjs';
const cases = JSON.parse(process.argv[2]);
console.log(JSON.stringify(cases.map(c => {
  const p = N.plan({property: c[0], name: c[1], numbers: c[2],
                    boxCode: c[3], boxPosition: c[4], url: process.argv[3]}, c[5]);
  return {text: p.text, bytes: p.bytes, truncated: p.truncated, fits: p.fits};
})));
"""


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("node が見つかりません。JS側を検証できないので中止します。")
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="keyline-parity-"))
    try:
        # tagapp/package.json は type:commonjs なので、そのままでは import できない。
        # .mjs に写して素の ESM として読ませる。
        shutil.copy(APP_DIR / "tagapp" / "www" / "ndef.js", tmp / "ndef.mjs")
        (tmp / "run.mjs").write_text(JS_RUNNER)
        proc = subprocess.run(
            [node, str(tmp / "run.mjs"), json.dumps(CASES), URL],
            capture_output=True, text=True, cwd=str(tmp), timeout=60)
        if proc.returncode != 0:
            print("JS側の実行に失敗しました:\n" + proc.stderr[-800:])
            return 1
        js = json.loads(proc.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    fails = 0
    print(f"\n  {'鍵の名称':<22}{'タグ':<10}{'Python':>11}{'JS':>11}")
    print("  " + "-" * 58)
    for c, j in zip(CASES, js):
        p = ndef.plan(URL, c[0], c[1], c[2], c[3], c[4], tag=c[5])
        same = (p["text"] == j["text"] and p["bytes"] == j["bytes"]
                and p["truncated"] == j["truncated"] and p["fits"] == j["fits"])
        mark = "✅" if same else "❌"
        cut = lambda x: "切詰" if x else "  "
        print(f"  {(c[1] or '')[:15]:<17}{c[5]:<11}"
              f"{p['bytes']:>5}B {cut(p['truncated'])}{j['bytes']:>6}B {cut(j['truncated'])}  {mark}")
        if not same:
            fails += 1
            print(f"      python: {p['text']!r}")
            print(f"      js    : {j['text']!r}")

        # 溢れたときでも、現場で使う情報（鍵番号・ボックス）は必ず残っていること
        if p["truncated"] and c[2]:
            first = c[2].split(",")[0].split(" ")[0]
            if first not in p["text"]:
                print(f"      ❌ 切り詰めで鍵番号が消えた: {p['text']!r}")
                fails += 1

    print()
    if fails:
        print(f"  ❌ {fails}件の食い違い。片方だけ直っていないか確認してください")
    else:
        print("  ✅ 全ケースで一致。アプリが書いたタグをサーバーが正しく読める")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
