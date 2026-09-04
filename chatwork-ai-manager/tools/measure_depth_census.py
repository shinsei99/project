#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""実物のフォルダを全部歩いて深さを数える。読むだけ。"""
import os, collections

ROOT = "/Users/apple/Library/CloudStorage/Dropbox-大京商事　株式会社/共有フォルダ/（★必読★）新共有フォルダ"
SKIP = {".DS_Store", "Icon\r", "desktop.ini"}

files = []          # (深さ=新共有フォルダ直下を1とするフォルダ数, 相対パス)
dirs  = []
for cur, dnames, fnames in os.walk(ROOT):
    rel = os.path.relpath(cur, ROOT)
    d = 0 if rel == "." else len(rel.split(os.sep))
    dirs.append((d, rel))
    for f in fnames:
        if f in SKIP or f.startswith("._"):
            continue
        files.append((d, (rel + "/" + f) if rel != "." else f))

print("=" * 74)
print("【1】実物の深さ（新共有フォルダ直下のフォルダを1階層と数える）")
print("=" * 74)
print(f"  ファイル {len(files):,}件 / フォルダ {len(dirs)-1:,}個\n")
c = collections.Counter(d for d, _ in files)
tot = len(files)
cum = 0
print(f"  {'階層':>4} {'ファイル数':>9} {'割合':>7}  {'ここまで累計':>9}")
for d in sorted(c):
    cum += c[d]
    bar = "█" * int(c[d] / 200)
    print(f"  {d:>4} {c[d]:>9,} {c[d]/tot*100:>6.1f}%  {cum/tot*100:>8.1f}%  {bar}")

for limit in (4, 5, 6):
    over = sum(v for k, v in c.items() if k > limit)
    print(f"\n  ★{limit}階層に収めるなら → はみ出すのは {over:,}件 ({over/tot*100:.1f}%)")

# ---- 2. どこが深いのか ----
print("\n" + "=" * 74)
print("【2】5階層を超えているファイルはどのトップフォルダにあるか")
print("=" * 74)
deep = collections.Counter()
deep_l2 = collections.Counter()
for d, p in files:
    if d > 5:
        parts = p.split("/")
        deep[parts[0]] += 1
        deep_l2["/".join(parts[:2])] += 1
for k, v in deep.most_common():
    print(f"  {k:<28} {v:>6,}")
print("\n  内訳（2階層目まで）上位15:")
for k, v in deep_l2.most_common(15):
    print(f"    {k:<52} {v:>6,}")

# ---- 3. 中身が1つしかない中間フォルダ（＝消しても情報が減らない階層） ----
print("\n" + "=" * 74)
print("【3】子が1つしかない中間フォルダ ＝ 潰せば無料で1階層減る")
print("=" * 74)
child = collections.defaultdict(list)
for d, rel in dirs:
    if rel == ".":
        continue
    parent = os.path.dirname(rel)
    child[parent if parent else "."].append(rel)
filecount = collections.Counter()
for d, p in files:
    parent = os.path.dirname(p)
    filecount[parent] += 1

single = []
for parent, kids in child.items():
    if len(kids) == 1 and filecount.get(parent, 0) == 0:
        # 子フォルダ1つだけ・直下にファイル無し → この階層は情報を持っていない
        n = sum(1 for d, p in files if p.startswith(kids[0] + "/"))
        single.append((parent, kids[0], n))
single.sort(key=lambda x: -x[2])
print(f"  該当 {len(single)}個（潰せる中間フォルダ）")
for parent, kid, n in single[:20]:
    print(f"    {parent}/  → 中身は {os.path.basename(kid)}/ だけ（配下{n}件）")

# ---- 4. 目標の形が5階層に収まるか ----
print("\n" + "=" * 74)
print("【4】計画で想定した形は何階層になるか")
print("=" * 74)
print("  物件・管理 / 管理物件 / ビル / 大京ビル / 03_請求・入金 / file.pdf")
print("      1         2        3       4          5              ← ちょうど5階層")
print("  ※ ただし『管理物件』が潰せるかで1階層変わる。下の実測を見ること")
for k in sorted(child.get("物件・管理", [])):
    n = sum(1 for d, p in files if p.startswith(k + "/"))
    print(f"    物件・管理/{os.path.basename(k):<24} 配下 {n:>5,}件")
