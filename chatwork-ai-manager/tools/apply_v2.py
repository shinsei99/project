#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""整理計画v2を実行する。物件フォルダの直下だけを動かす。フォルダはバラさない。
   使い方: apply_v2.py "大京本社ビル"        … 下見
           apply_v2.py "大京本社ビル" --go   … 実行"""
import os, sys, json, shutil, datetime, unicodedata, subprocess, collections
N = lambda s: unicodedata.normalize("NFC", s)
ROOT = "/Users/apple/Library/CloudStorage/Dropbox-大京商事　株式会社/共有フォルダ"
REC  = os.path.expanduser("~/chatwork-ai-manager/local/")
GO = "--go" in sys.argv
props = [a for a in sys.argv[1:] if not a.startswith("--")]
if not props: print("物件名を指定してください"); sys.exit(1)

# 計画を plan_v2 から JSON で受け取る
here = os.path.dirname(os.path.abspath(__file__))
res = subprocess.run(["/usr/bin/python3", os.path.join(here, "plan_v2.py"), "--json"] + props,
                     capture_output=True, text=True)
if res.returncode != 0:
    print(res.stderr[-2000:]); sys.exit(1)
plan = json.loads(res.stdout)
MP = "物件・管理/管理物件"

SHELF = ("契約","解約・精算","修繕・点検","図面・写真","お知らせ","入居者","解約済")

print("=" * 74)
print(("【実行】" if GO else "【下見】") + f"  {'、'.join(props)}")
print("=" * 74)
mv = []
for r in plan:
    sh = r["行き先"]
    if sh == "（動かさない）": continue
    src = os.path.join(ROOT, N(r["現在のパス"]))
    item = r["名前"]
    if sh == "解約済" and item.startswith("解約済"):
        dst = os.path.join(ROOT, MP, r["種別"], r["物件"], "解約済")
    elif sh == "入居者" and item.startswith("賃借人資料"):
        dst = os.path.join(ROOT, MP, r["種別"], r["物件"], "入居者")
    else:
        dst = os.path.join(ROOT, MP, r["種別"], r["物件"], sh, item)
    mv.append((src, dst, sh, item))
stay = [r for r in plan if r["行き先"] == "（動かさない）"]

ng = []
for s, d, sh, item in mv:
    if not os.path.exists(s): ng.append(("元が無い", item))
    elif os.path.exists(d) and not os.path.basename(d) in ("解約済","入居者"): ng.append(("先に同名", item))
if ng:
    print(f"\n★点検で問題 {len(ng)}件。中止。")
    for k, p in ng[:10]: print(f"   [{k}] {p}")
    sys.exit(1)
print(f"  移動する {len(mv)}項目（点検OK） / 動かさない {len(stay)}項目\n")
for r in stay: print(f"    そのまま: [{r['決め手']}] {r['名前'][:50]}")
print()
for sh, n in collections.Counter(x[2] for x in mv).most_common():
    print(f"    {sh:<12}{n:>3}項目")
if not GO:
    print("\n  ※下見のみ。--go で実行"); sys.exit(0)

log = []
for s, d, sh, item in mv:
    os.makedirs(os.path.dirname(d), exist_ok=True)
    shutil.move(s, d)
    log.append({"from": N(os.path.relpath(s, ROOT)), "to": N(os.path.relpath(d, ROOT))})
os.makedirs(REC, exist_ok=True)
rec = os.path.join(REC, f"移動記録_v2_{'_'.join(props)[:36]}_{datetime.date.today():%Y%m%d}.json")
json.dump({"date": str(datetime.date.today()), "root": ROOT, "props": props, "moved": log},
          open(rec, "w"), ensure_ascii=False, indent=2)
print(f"\n  移動 {len(log)}項目")
print(f"  対応表: {rec}")
