#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dropbox共有フォルダの索引を「中身」から測る。読むだけ。何も書き換えない。"""
import sqlite3, re, unicodedata, json, os, collections

DB = "/Users/apple/chatwork-ai-manager/data/app.db"
DROPBOX_ROOT = "/Users/apple/Library/CloudStorage/Dropbox-大京商事　株式会社/共有フォルダ/"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

# ---------- 正規化（名寄せの誤爆を減らす） ----------
def norm(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.lower()
    # 括弧の中（オーナー名）を落とす
    s = re.sub(r"[（(\[][^）)\]]{0,20}[）)\]]", "", s)
    # 記号・空白を落とす
    s = re.sub(r"[\s　・･,，.。\-ー－_/\\'\"]", "", s)
    # ローマ数字→算用数字
    for a, b in (("ⅰ","1"),("ⅱ","2"),("ⅲ","3"),("ⅳ","4"),("ii","2"),("iii","3")):
        s = s.replace(a, b)
    return s

KATA2ROMA = {"さとう":"sato","サトウ":"sato"}

# ---------- 物件マスタ ----------
props = []
for r in con.execute("SELECT property_id,name,category,classification,folder FROM properties WHERE active=1"):
    names = {r["name"]}
    props.append({"id": r["property_id"], "name": r["name"], "cat": r["category"],
                  "cls": r["classification"], "company": "大京",
                  "keys": {norm(n) for n in names if norm(n)}})
for r in con.execute("SELECT property_id,name,aliases FROM shinsei_properties WHERE active=1"):
    names = {r["name"]}
    if r["aliases"]:
        names |= {a.strip() for a in re.split(r"[\n,、]", r["aliases"]) if a.strip()}
    props.append({"id": r["property_id"], "name": r["name"], "cat": "", "cls": "",
                  "company": "新誠", "keys": {norm(n) for n in names if norm(n)}})

# 短すぎるキーは誤爆源なので落とす（2文字以下）
for p in props:
    p["keys"] = {k for k in p["keys"] if len(k) >= 3}
key2prop = {}
for p in props:
    for k in p["keys"]:
        key2prop.setdefault(k, []).append(p)
ALL_KEYS = sorted(key2prop.keys(), key=len, reverse=True)
print(f"物件マスタ: {len(props)}件 / 照合キー {len(ALL_KEYS)}種（3文字以上）")

# ---------- 対象文書 ----------
docs = list(con.execute("""
    SELECT id, category, title, filename, filepath, mime, company, source_mtime, content_hash
    FROM knowledge_documents
    WHERE active=1 AND filepath LIKE ? """, (DROPBOX_ROOT + "%",)))
print(f"対象（Dropbox共有フォルダ）: {len(docs)}件\n")

# 本文（先頭3チャンク）をまとめて取る
head_text = {}
q = """SELECT doc_id, group_concat(text, ' ') FROM (
         SELECT doc_id, text FROM knowledge_chunks WHERE ord < 3 ORDER BY doc_id, ord
       ) GROUP BY doc_id"""
for did, t in con.execute(q):
    head_text[did] = t or ""

# ---------- 1. 物件名寄せ ----------
def match_prop(text):
    hits = []
    n = norm(text)
    if not n:
        return hits
    for k in ALL_KEYS:
        if k in n:
            hits.append(k)
    # 長いキーに含まれる短いキーは落とす（部分一致の入れ子）
    out = []
    for k in hits:
        if not any(k != o and k in o for o in hits):
            out.append(k)
    return out

res = collections.Counter()
by_top = collections.defaultdict(lambda: collections.Counter())
prop_docs = collections.Counter()
unmatched_samples = []
matched_rows = []

for d in docs:
    rel = d["filepath"][len(DROPBOX_ROOT):]
    parts = rel.split("/")
    top = parts[0] if parts else "?"
    depth = len(parts)
    # ①パス（フォルダ名）で当てる  ②本文で当てる
    by_path = match_prop(rel)
    by_body = match_prop(head_text.get(d["id"], "")[:4000]) if not by_path else []
    if by_path:
        how = "パス"
        keys = by_path
    elif by_body:
        how = "本文"
        keys = by_body
    else:
        how = "不一致"
        keys = []
    if len(keys) > 1:
        how += "(複数)"
    res[how] += 1
    by_top[top][how.split("(")[0]] += 1
    for k in keys:
        for p in key2prop[k]:
            prop_docs[p["name"]] += 1
    if not keys and len(unmatched_samples) < 400:
        unmatched_samples.append((top, rel, d["title"]))
    matched_rows.append((d["id"], top, depth, rel, how, keys[0] if keys else ""))

total = len(docs)
print("=" * 66)
print("【1】物件↔文書の名寄せ（TODO.md の『次の一手』）")
print("=" * 66)
for k, v in res.most_common():
    print(f"  {k:12s} {v:6d}  {v/total*100:5.1f}%")
hit = sum(v for k, v in res.items() if not k.startswith("不一致"))
print(f"  --> 何らかの物件に当たった: {hit}/{total} = {hit/total*100:.1f}%")

print("\n  トップフォルダ別:")
print(f"  {'フォルダ':<16}{'件数':>7}{'パス':>8}{'本文':>7}{'不一致':>8}  当たり率")
for top, c in sorted(by_top.items(), key=lambda x: -sum(x[1].values())):
    n = sum(c.values())
    h = c["パス"] + c["本文"]
    print(f"  {top:<16}{n:>7}{c['パス']:>8}{c['本文']:>7}{c['不一致']:>8}  {h/n*100:5.1f}%")

print(f"\n  文書が1件も紐づかなかった物件: ", end="")
zero = [p["name"] for p in props if prop_docs[p["name"]] == 0]
print(f"{len(zero)}/{len(props)}件")
print("   例:", "、".join(zero[:12]))
print("\n  文書が多い物件 上位12:")
for name, n in prop_docs.most_common(12):
    print(f"    {name:<28} {n:>5}件")

# ---------- 2. 書類の種別（中身＋ファイル名から） ----------
RULES = [
    ("賃貸借契約書",      r"賃貸借契約|定期借家|使用貸借"),
    ("重要事項説明書",    r"重要事項説明|重説"),
    ("売買契約書",        r"売買契約|不動産売買"),
    ("媒介契約書",        r"媒介契約|専任媒介|一般媒介"),
    ("入居申込・審査",    r"入居申込|申込書|保証会社|審査結果"),
    ("解約・退去精算",    r"解約|退去|原状回復|明渡"),
    ("請求書・領収書",    r"請求書|領収書|御請求|インボイス|適格請求"),
    ("見積書",            r"見積書|御見積"),
    ("レントロール・収支",r"レントロール|収支|入金管理|送金明細"),
    ("登記・謄本",        r"登記|全部事項|公図|測量|地積"),
    ("図面・間取り",      r"間取|平面図|配置図|マイソク|募集図面"),
    ("保険",              r"保険|火災保険|地震保険"),
    ("修繕・工事",        r"工事|修繕|施工|点検報告|保守"),
    ("鍵・設備",          r"鍵|シリンダー|オートロック|エレベータ"),
    ("税務・決算",        r"確定申告|決算|固定資産税|償却"),
    ("社内様式・書式",    r"様式|書式|ひな形|テンプレート|雛形"),
    ("議事録・稟議",      r"議事録|稟議|決裁"),
    ("名簿・一覧",        r"名簿|一覧表|リスト"),
]
kind_count = collections.Counter()
kind_by_top = collections.defaultdict(collections.Counter)
for d in docs:
    rel = d["filepath"][len(DROPBOX_ROOT):]
    top = rel.split("/")[0]
    blob = (d["title"] or "") + " " + (d["filename"] or "") + " " + head_text.get(d["id"], "")[:1500]
    found = None
    for label, pat in RULES:
        if re.search(pat, blob):
            found = label
            break
    kind_count[found or "(判定できず)"] += 1
    kind_by_top[top][found or "(判定できず)"] += 1

print("\n" + "=" * 66)
print("【2】書類の種別（本文＋ファイル名から自動判定）")
print("=" * 66)
for k, v in kind_count.most_common():
    print(f"  {k:<20} {v:>6}  {v/total*100:5.1f}%")

# ---------- 3. 重複 ----------
print("\n" + "=" * 66)
print("【3】中身が同一の重複（content_hash）")
print("=" * 66)
hh = collections.Counter(d["content_hash"] for d in docs if d["content_hash"])
dups = {h: n for h, n in hh.items() if n > 1}
dup_files = sum(dups.values())
print(f"  重複グループ {len(dups)}組 / のべ {dup_files}件（うち余分は {dup_files-len(dups)}件）")
byhash = collections.defaultdict(list)
for d in docs:
    if d["content_hash"] in dups:
        byhash[d["content_hash"]].append(d["filepath"][len(DROPBOX_ROOT):])
for h, paths in sorted(byhash.items(), key=lambda x: -len(x[1]))[:5]:
    print(f"    ×{len(paths)}: {os.path.basename(paths[0])}")
    for p in paths[:3]:
        print(f"        {p}")

# ---------- 4. 深さと鮮度 ----------
print("\n" + "=" * 66)
print("【4】深さ・鮮度")
print("=" * 66)
depth_c = collections.Counter()
for d in docs:
    depth_c[len(d["filepath"][len(DROPBOX_ROOT):].split("/"))] += 1
for dep in sorted(depth_c):
    print(f"  {dep:>2}層 {'█'*int(depth_c[dep]/120):<40} {depth_c[dep]:>6}")

import datetime
now = datetime.datetime.now().timestamp()
age = collections.Counter()
for d in docs:
    m = d["source_mtime"]
    if not m:
        age["(不明)"] += 1
        continue
    y = (now - m) / 86400 / 365
    age["1年以内" if y < 1 else "1〜3年" if y < 3 else "3〜5年" if y < 5 else "5〜10年" if y < 10 else "10年超"] += 1
for k in ["1年以内", "1〜3年", "3〜5年", "5〜10年", "10年超", "(不明)"]:
    if age[k]:
        print(f"  {k:<8} {age[k]:>6}  {age[k]/total*100:5.1f}%")

# 不一致サンプルを書き出す
OUT = "/tmp/unmatched_sample.txt"
with open(OUT, "w") as f:
    for top, rel, title in unmatched_samples:
        f.write(f"{top}\t{rel}\n")
print(f"\n不一致サンプル400件 -> {OUT}")
