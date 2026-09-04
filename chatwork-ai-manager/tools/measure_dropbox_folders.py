#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""フォルダ木から実在する物件を洗い出し、物件マスタと突き合わせる。読むだけ。"""
import sqlite3, re, unicodedata, collections, os

DB = "/Users/apple/chatwork-ai-manager/data/app.db"
ROOT = "/Users/apple/Library/CloudStorage/Dropbox-大京商事　株式会社/共有フォルダ/（★必読★）新共有フォルダ/"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

def norm(s):
    if not s: return ""
    s = unicodedata.normalize("NFKC", s).lower()
    s = re.sub(r"[（(\[][^）)\]]{0,20}[）)\]]", "", s)
    s = re.sub(r"[\s　・･,，.。\-ー－_/\\'\"]", "", s)
    for a, b in (("ⅰ","1"),("ⅱ","2"),("ⅲ","3"),("ii","2"),("iii","3")):
        s = s.replace(a, b)
    # 末尾の一般語を落として比較しやすくする
    return s

def stem(s):
    """比較用に末尾の種別語を落とす: ワタヤライラックビル -> ワタヤライラック"""
    n = norm(s)
    for suf in ("ビル", "bldg", "マンション", "駐車場", "モータープール", "駐輪場", "コーポ", "ハイツ"):
        if n.endswith(suf) and len(n) > len(suf) + 2:
            n = n[: -len(suf)]
    return n

docs = list(con.execute(
    "SELECT filepath FROM knowledge_documents WHERE active=1 AND filepath LIKE ?", (ROOT + "%",)))

# ---- 1. 物件・管理/管理物件/{種別}/{物件名}/ を洗い出す ----
folder_props = collections.Counter()
kind_of = {}
for d in docs:
    rel = d["filepath"][len(ROOT):]
    p = rel.split("/")
    if len(p) >= 4 and p[0] == "物件・管理" and p[1] == "管理物件":
        kind, name = p[2], p[3]
        if "." in name:      # 直下のファイル（物件フォルダではない）
            continue
        folder_props[(kind, name)] += 1
        kind_of[name] = kind

print("=" * 70)
print("【A】フォルダ木に実在する物件フォルダ")
print("=" * 70)
by_kind = collections.Counter(k for (k, n) in folder_props)
for k, v in by_kind.most_common():
    print(f"  {k:<10} {v:>4}フォルダ")
print(f"  合計 {len(folder_props)} 物件フォルダ / 収容 {sum(folder_props.values())} 文書")

# ---- 2. 物件マスタと突き合わせ ----
master = {}
for r in con.execute("SELECT name, category, classification FROM properties WHERE active=1"):
    master[r["name"]] = (r["category"], r["classification"])
shinsei = {}
for r in con.execute("SELECT name, aliases FROM shinsei_properties WHERE active=1"):
    shinsei[r["name"]] = r["aliases"] or ""

m_index = {}
for nm in master:
    m_index.setdefault(stem(nm), []).append(nm)
for nm, al in shinsei.items():
    m_index.setdefault(stem(nm), []).append(nm + "[新誠]")
    for a in re.split(r"[\n,、]", al):
        if a.strip():
            m_index.setdefault(stem(a.strip()), []).append(nm + "[新誠]")

exact, fuzzy, missing = [], [], []
for (kind, name), n in folder_props.most_common():
    s = stem(name)
    if s in m_index:
        exact.append((name, m_index[s][0], n))
        continue
    cand = [mk for mk in m_index if mk and (mk in s or s in mk) and min(len(mk), len(s)) >= 3]
    if cand:
        best = max(cand, key=len)
        fuzzy.append((name, m_index[best][0], n))
    else:
        missing.append((kind, name, n))

print("\n" + "=" * 70)
print("【B】物件マスタとの突き合わせ（フォルダ側を基準に）")
print("=" * 70)
tot = len(folder_props)
print(f"  そのまま一致          {len(exact):>4} / {tot}  ({len(exact)/tot*100:.0f}%)")
print(f"  表記ゆれで拾える      {len(fuzzy):>4} / {tot}  ({len(fuzzy)/tot*100:.0f}%)  ← 別名表を作れば当たる")
print(f"  マスタに存在しない    {len(missing):>4} / {tot}  ({len(missing)/tot*100:.0f}%)  ← 台帳の穴")

print("\n  ◆表記ゆれ（別名表に入れる候補）")
for f, m, n in sorted(fuzzy, key=lambda x: -x[2])[:25]:
    print(f"    {f:<34} → {m:<26} {n:>4}件")

print("\n  ◆マスタに無い物件フォルダ（文書数の多い順）")
for k, f, n in sorted(missing, key=lambda x: -x[2])[:35]:
    print(f"    [{k:<6}] {f:<38} {n:>4}件")
print(f"    … 計{len(missing)}件、のべ {sum(n for _,_,n in missing)} 文書がマスタ未登録の物件にぶら下がっている")

# ---- 3. マスタにあるがフォルダが無い物件 ----
folder_stems = {stem(n) for (k, n) in folder_props}
orphan = [nm for nm in master if stem(nm) not in folder_stems and
          not any(stem(nm) in fs or fs in stem(nm) for fs in folder_stems if len(fs) >= 3)]
print(f"\n  ◆逆にマスタにあるがフォルダが見当たらない: {len(orphan)}件")
print("    " + "、".join(orphan[:20]))

# ---- 4. 物件フォルダの中の深さ ----
print("\n" + "=" * 70)
print("【C】物件フォルダの中はどれくらい深いか")
print("=" * 70)
inner = collections.Counter()
sub1 = collections.Counter()
for d in docs:
    rel = d["filepath"][len(ROOT):]
    p = rel.split("/")
    if len(p) >= 5 and p[0] == "物件・管理" and p[1] == "管理物件":
        inner[len(p) - 4] += 1          # 物件フォルダから下の階層数
        sub1[p[4]] += 1                 # 物件直下のフォルダ名
for k in sorted(inner):
    print(f"  物件フォルダから{k}階層下 {'█'*int(inner[k]/60):<32} {inner[k]:>5}")
print("\n  物件フォルダ直下によく出る名前 上位25（＝共通の棚の候補）:")
for k, v in sub1.most_common(25):
    print(f"    {k:<30} {v:>5}")
