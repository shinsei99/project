#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""移動記録のJSONを読んで、移動を元に戻す。--go で実行。"""
import os, sys, json, shutil, unicodedata
N = lambda s: unicodedata.normalize("NFC", s)
GO = "--go" in sys.argv
recs = [a for a in sys.argv[1:] if not a.startswith("--")]
if not recs: print("記録JSONを指定してください"); sys.exit(1)
for rp in recs:
    rec = json.load(open(os.path.expanduser(rp)))
    ROOT = rec["root"]; mv = rec["moved"]
    print(f"=== {os.path.basename(rp)}  {len(mv)}件 ===")
    ng = 0
    for m in mv:
        t = os.path.join(ROOT, N(m["to"])); f = os.path.join(ROOT, N(m["from"]))
        if not os.path.exists(t): print(f"  ★移動先に無い: {m['to']}"); ng += 1
        elif os.path.exists(f):   print(f"  ★元に既にある: {m['from']}"); ng += 1
    if ng: print(f"  問題 {ng}件。中止。"); sys.exit(1)
    print("  点検OK")
    if not GO: print("  ※下見のみ。--go で実行"); continue
    for m in mv:
        t = os.path.join(ROOT, N(m["to"])); f = os.path.join(ROOT, N(m["from"]))
        os.makedirs(os.path.dirname(f), exist_ok=True)
        shutil.move(t, f)
    # 空になったフォルダを片付ける
    rm = 0
    base = os.path.join(ROOT, "/".join(N(mv[0]["to"]).split("/")[:4]))
    for _ in range(8):
        for cur, dn, fn in os.walk(base, topdown=False):
            if cur == base: continue
            real = [x for x in fn if x != ".DS_Store" and not x.startswith("._")]
            if real or dn: continue
            ds = os.path.join(cur, ".DS_Store")
            if os.path.exists(ds): os.remove(ds)
            try: os.rmdir(cur); rm += 1
            except OSError: pass
    print(f"  戻した {len(mv)}件 / 空フォルダ片付け {rm}個")
