#!/usr/bin/env python3
"""各ゲームの本体を neon-blocks/www/games/ へ入れ直す。

なぜ要るのか:
  `www/games/<名前>/` に入っているのは**各アプリからの複製**。元（例: `nyanko-ice/www/`）を
  直したら、ここを入れ直さないと**同じゲームの中身が2つに割れる**（Web版とアプリ版で
  見た目が違う、という一番たちの悪いズレになる）。

  ★元を直す → これを流す、の順で運用する。逆（games/ 側を直す）はしないこと。

使い方:
    python3 tools/sync-games.py           # 差分があるものだけ入れ直す
    python3 tools/sync-games.py --check   # 入れ直さず、ズレているものを並べるだけ
"""
from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent      # neon-blocks/
REPO = ROOT.parent
GAMES = ROOT / "www" / "games"

# 送り先 ← 取り出し元（本体は www/index.html なので games/blocks は転送だけ＝対象外）
SRC = {
    "escape":  "neko-escape/www",
    "ice":     "nyanko-ice/www",
    "gravity": "color-gravity/www",
    "cyborg":  "cyborg-defense/www",
    "piyo":    "piyo-defense/www",
}
SKIP_FILES = {"support.html", "privacy.html"}      # 必須URLはアプリ側では要らない
# ★このスクリプトは**余分なファイルは消さない**（コピーするだけ）。
#   取り出し元で書体を入れ替えたときなど、古いファイルが集合側に残る。
#   2026-08-29 に ZenMaruGothic-*.woff2 が escape 側に残っていたのを手で外した。
#   消えていることの確認は `ls neon-blocks/www/games/<名前>/assets/fonts/` で見ること。
SWITCH_TAG = '<script src="../_switch.js"></script>'


def files_of(base: Path):
    for f in base.rglob("*"):
        if f.is_file() and f.name not in SKIP_FILES:
            yield f


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="入れ直さず差分だけ見る")
    args = ap.parse_args()

    diffs = 0
    for dst_name, src_rel in SRC.items():
        src, dst = REPO / src_rel, GAMES / dst_name
        if not src.exists():
            print("★取り出し元が無い: %s" % src); continue
        changed = []
        for f in files_of(src):
            rel = f.relative_to(src)
            target = dst / rel
            # index.html は「切り替え帯の1行」を足した状態が正なので、その分を除いて比べる
            if rel.name == "index.html" and target.exists():
                a = f.read_text(encoding="utf-8")
                b = target.read_text(encoding="utf-8").replace(SWITCH_TAG + "\n", "").replace(SWITCH_TAG, "")
                same = (a.strip() == b.strip())
            else:
                same = target.exists() and filecmp.cmp(f, target, shallow=False)
            if same:
                continue
            changed.append(str(rel))
            if not args.check:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(f, target)
                if rel.name == "index.html":
                    s = target.read_text(encoding="utf-8")
                    if SWITCH_TAG not in s:
                        s = (s.replace("</body>", SWITCH_TAG + "\n</body>", 1)
                             if "</body>" in s else s.rstrip() + "\n" + SWITCH_TAG + "\n")
                        target.write_text(s, encoding="utf-8")
        if changed:
            diffs += len(changed)
            print("%-8s %s %d件: %s" % (dst_name, "ズレている" if args.check else "入れ直した",
                                        len(changed), ", ".join(changed[:4])))
        else:
            print("%-8s 一致" % dst_name)

    if args.check and diffs:
        print("\n★ズレが %d 件。`python3 tools/sync-games.py` で入れ直す" % diffs)
        sys.exit(1)


if __name__ == "__main__":
    main()
