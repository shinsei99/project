#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""標準の棚を仮に決めて、いまの文書が何%自動で入るかを測る。読むだけ。"""
import sqlite3, re, collections

DB = "/Users/apple/chatwork-ai-manager/data/app.db"
ROOT = "/Users/apple/Library/CloudStorage/Dropbox-大京商事　株式会社/共有フォルダ/（★必読★）新共有フォルダ/"
con = sqlite3.connect(DB); con.row_factory = sqlite3.Row

# 標準の棚（案）: 物件フォルダの下はこの7つだけにする
SHELVES = [
    ("01_契約",       r"契約書|重説|重要事項|覚書|合意書|更新|定期借家|保証委託|入居申込|申込書|審査|媒介|念書"),
    ("02_解約・精算",  r"解約|退去|精算|清算|原状回復|明渡|返還|敷金"),
    ("03_請求・入金",  r"請求|領収|入金|送金|月次|収支|家賃|振込|明細"),
    ("04_工事・修繕",  r"工事|修繕|リフォーム|リホーム|見積|施工|点検|保守|清掃|設備|日立|エレベータ|消防"),
    ("05_図面・写真",  r"図面|竣工|平面|間取|配置|測量|公図|写真|マイソク|パース"),
    ("06_権利・登記",  r"登記|謄本|全部事項|評価証明|固定資産|税|保険|証券|権利"),
    ("07_通知・その他", r"お知らせ|通知|案内|貼紙|掲示|連絡|報告|名簿|一覧|書式|様式"),
    ("08_検針・メーター", r"検針|メーター|水道|電気|ガス|使用量"),
    ("09_賃借人資料",   r"賃借人|入居者|テナント|車庫証|入居時確認"),
]

docs = list(con.execute("""SELECT id,title,filename,filepath FROM knowledge_documents
                           WHERE active=1 AND filepath LIKE ?""", (ROOT + "%",)))
head = {}
for did, t in con.execute("""SELECT doc_id, group_concat(text,' ') FROM
      (SELECT doc_id,text FROM knowledge_chunks WHERE ord<2 ORDER BY doc_id,ord) GROUP BY doc_id"""):
    head[did] = t or ""

target, hit = 0, collections.Counter()
multi = 0
unassigned = []
for d in docs:
    rel = d["filepath"][len(ROOT):]
    p = rel.split("/")
    if not (len(p) >= 5 and p[0] == "物件・管理" and p[1] == "管理物件"):
        continue
    target += 1
    # 判定材料 = 物件フォルダより下のパス（＝いまの棚名）＋ ファイル名 ＋ 本文先頭
    path_part = "/".join(p[4:])
    blob_path = path_part
    blob_body = (d["title"] or "") + " " + head.get(d["id"], "")[:800]
    got = [n for n, pat in SHELVES if re.search(pat, blob_path)]
    src = "棚名"
    if not got:
        got = [n for n, pat in SHELVES if re.search(pat, blob_body)]
        src = "本文"
    if not got:
        hit["(入らない)"] += 1
        if len(unassigned) < 300:
            unassigned.append(path_part)
        continue
    if len(got) > 1:
        multi += 1
    hit[got[0] + "／" + src] += 1

print("=" * 70)
print("【D】標準の棚（7つ）に自動で入るか — 対象: 管理物件フォルダ内 %d 文書" % target)
print("=" * 70)
agg = collections.Counter()
for k, v in hit.items():
    agg[k.split("／")[0]] += v
placed = target - hit["(入らない)"]
for name, _ in SHELVES:
    byname = agg[name]
    p_ = hit.get(name + "／棚名", 0); b_ = hit.get(name + "／本文", 0)
    print(f"  {name:<14}{byname:>5}  ({byname/target*100:4.1f}%)   棚名で{p_:>4} / 本文で{b_:>4}")
print(f"  {'(入らない)':<14}{hit['(入らない)']:>5}  ({hit['(入らない)']/target*100:4.1f}%)")
print(f"\n  --> 自動で棚に入る: {placed}/{target} = {placed/target*100:.1f}%")
print(f"      うち複数の棚に該当（要優先順位）: {multi}件 = {multi/target*100:.1f}%")

print("\n  ◆入らなかったものの現在のパス（上位）:")
for k, v in collections.Counter(u.split("/")[0] for u in unassigned).most_common(20):
    print(f"    {k:<40} {v:>4}")
