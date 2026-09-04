#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""① 5階層へ寄せる（実体フォルダは深さを問わず残す） ② 完全重複を数える。読むだけ。"""
import os, re, collections, unicodedata, hashlib

ROOT = "/Users/apple/Library/CloudStorage/Dropbox-大京商事　株式会社/共有フォルダ"
N = lambda s: unicodedata.normalize("NFC", s)
ARC = N("_アーカイブ（2027年7月削除予定）")
PRE = N("物件・管理/管理物件/")

files, sizes = [], {}
for cur, dn, fn in os.walk(ROOT):
    rel = N(os.path.relpath(cur, ROOT))
    for f in fn:
        f = N(f)
        if f in {".DS_Store", "desktop.ini"} or f.startswith("._"):
            continue
        p = (rel + "/" + f) if rel != "." else f
        files.append(p)
        try:
            sizes[p] = os.path.getsize(os.path.join(cur, f))
        except OSError:
            sizes[p] = -1
live = [p for p in files if not p.startswith(ARC)]
mp = [p for p in live if p.startswith(PRE) and len(p.split("/")) >= 5]

# ================= ① 5階層へ寄せる =================
ENTITY_PAT = re.compile(
    r"^\d+番|^\d+号|^[A-Z]?\d{3,4}(号|室|_)|^\d+F|^\d+階|^[0-9]{3}_|"
    r"（\d{4}[.\-/]\d{1,2}|～）|^\d{4}[.\-]\d{2}[.\-]\d{2}_")

# 「兄弟が同じファイル名を持つ」フォルダ = 実体。深さを問わず全階層で判定する。
sib = collections.defaultdict(lambda: collections.defaultdict(set))
for p in mp:
    parts = p.split("/")
    for i in range(4, len(parts) - 1):
        parent = "/".join(parts[:i])
        sib[parent][parts[i]].add(parts[-1])
entity = set()          # (親パス, フォルダ名)
for parent, kids in sib.items():
    names = list(kids)
    for i, a in enumerate(names):
        if ENTITY_PAT.search(a):
            entity.add((parent, a)); continue
        for b in names[i + 1:]:
            if kids[a] & kids[b]:
                entity.add((parent, a)); entity.add((parent, b))

SHELVES = [
    ("01_契約",        r"契約書|重説|重要事項|覚書|合意書|更新|定期借家|保証委託|入居申込|申込書|審査|媒介|念書"),
    ("02_解約・精算",   r"解約|退去|精算|清算|原状回復|明渡|返還|敷金"),
    ("03_請求・入金",   r"請求|領収|入金|送金|月次|収支|家賃|振込|明細"),
    ("04_工事・修繕",   r"工事|修繕|リフォーム|リホーム|見積|施工|点検|保守|清掃|設備|昇降|エレベータ|消防"),
    ("05_図面・写真",   r"図面|竣工|平面|間取|配置|測量|公図|写真|マイソク|パース"),
    ("06_権利・登記",   r"登記|謄本|全部事項|評価証明|固定資産|税|保険|証券|権利"),
    ("08_検針・メーター", r"検針|メーター|水道|電気|ガス|使用量"),
    ("09_賃借人資料",   r"賃借人|入居者|テナント|車庫証|入居時確認"),
]
def shelf(below, fname):
    for n, pat in SHELVES:
        if re.search(pat, below): return n
    for n, pat in SHELVES:
        if re.search(pat, fname): return n
    return "07_通知・その他"

plan = []
for p in mp:
    parts = p.split("/")
    prop = "/".join(parts[:4]); fname = parts[-1]
    below = "/".join(parts[4:-1])
    # 物件フォルダより下で「実体」と判定された最も深いフォルダ名を1つだけ残す
    keep = None
    for i in range(4, len(parts) - 1):
        if ("/".join(parts[:i]), parts[i]) in entity:
            keep = parts[i]
    if keep:
        new = f"{prop}/09_賃借人資料/{keep}/{fname}"
    else:
        new = f"{prop}/{shelf(below, fname)}/{fname}"
    plan.append((p, new))

dest = collections.Counter(b for a, b in plan)
col = {k: v for k, v in dest.items() if v > 1}
print("=" * 74)
print("【①】5階層へ寄せる（実体フォルダは深さを問わず1つ残す）")
print("=" * 74)
dd = collections.Counter(len(b.split("/")) - 1 for a, b in plan)
print(f"  対象 {len(plan):,}件（物件・管理/管理物件 の中）")
for k in sorted(dd):
    print(f"    移動後 {k}階層 {dd[k]:>6,}件 ({dd[k]/len(plan)*100:4.1f}%)")
print(f"  ★衝突: {len(col)}か所 / {sum(col.values())}件")

# 衝突のうち「中身も同じ＝ただの重複」なのか「別物」なのかを分ける
def h(p):
    try:
        with open(os.path.join(ROOT, p), "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None
bysrc = collections.defaultdict(list)
for a, b in plan:
    if b in col: bysrc[b].append(a)
same, diff = 0, 0
diff_ex = []
for b, srcs in bysrc.items():
    hs = {h(s) for s in srcs}
    if len(hs) == 1:
        same += len(srcs)
    else:
        diff += len(srcs)
        if len(diff_ex) < 6: diff_ex.append((b, srcs))
print(f"     ├ 中身も同じ（＝②の重複削除で自然に消える） {same}件")
print(f"     └ ★中身が違う（上書き事故になる。個別対応が要る） {diff}件")
for b, s in diff_ex[:5]:
    print(f"        {b.split('/')[-1]}  ←{len(s)}件  @{'/'.join(b.split('/')[2:4])}")

# ================= ② 完全な重複 =================
print("\n" + "=" * 74)
print("【②】中身が完全に同じファイル（実物・全22,671件をハッシュ照合）")
print("=" * 74)
bysize = collections.defaultdict(list)
for p in files:
    if sizes[p] > 0: bysize[sizes[p]].append(p)
groups = collections.defaultdict(list)
for sz, ps in bysize.items():
    if len(ps) < 2: continue
    for p in ps:
        d = h(p)
        if d: groups[(sz, d)].append(p)
dups = {k: v for k, v in groups.items() if len(v) > 1}
extra = sum(len(v) - 1 for v in dups.values())
wasted = sum(k[0] * (len(v) - 1) for k, v in dups.items())
print(f"  重複グループ {len(dups):,}組 / のべ {sum(len(v) for v in dups.values()):,}件")
print(f"  ★消せる余分 {extra:,}件 ({extra/len(files)*100:.1f}%) / 節約 {wasted/1024/1024:.0f}MB")

inarc = sum(1 for v in dups.values() for p in v[1:] if p.startswith(ARC))
print(f"    └ うち凍結アーカイブ側 {inarc:,}件（2027年7月に消えるので急がない）")
cross = sum(1 for v in dups.values()
            if any(p.startswith(ARC) for p in v) and any(not p.startswith(ARC) for p in v))
print(f"    └ 現役とアーカイブに同じものが両方ある: {cross:,}組")
print("\n  余分が多い順:")
for k, v in sorted(dups.items(), key=lambda x: -len(x[1]))[:8]:
    print(f"    ×{len(v)}  {os.path.basename(v[0])}")
    for p in v[:2]:
        print(f"         {p}")
