"""公式サイトから取得した画像を、TCGdex のカードデータに紐付ける。

突き合わせは「セット記号 + カード名」で行う。
公式のセット記号（M5, SV5M …）は TCGdex のセットIDとほぼ一致する。
同名カードが同一セットに複数ある場合（例: 同じポケモンの別イラスト）は
ID順に若い方から割り当てる。
"""
import sqlite3, collections

# 取得プロセスが同じDBに書き込んでいるので、ロック待ちを長めに取る
con = sqlite3.connect("data/cards.db", timeout=120)
con.execute("PRAGMA busy_timeout = 120000")
con.execute("UPDATE cards SET image_official=NULL, local_file=NULL")

# 公式側を「セット記号 → 名前 → IDの列」に整理
off = collections.defaultdict(lambda: collections.defaultdict(list))
for cid, name, sc, local in con.execute(
        "SELECT card_id, name, set_code, local FROM official "
        "WHERE status='ok' AND local IS NOT NULL ORDER BY card_id"):
    if name and sc:
        off[sc][name].append((cid, local))

linked = 0
for cid_t, set_id, name in con.execute("SELECT id, set_id, name FROM cards").fetchall():
    pool = off.get(set_id, {}).get(name)
    if not pool:
        continue
    ocid, local = pool.pop(0)          # 若いIDから順に割り当てる
    con.execute("UPDATE cards SET image_official=?, local_file=? WHERE id=?",
                (ocid, local, cid_t))
    linked += 1
con.commit()

tot = con.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
tc  = con.execute("SELECT COUNT(*) FROM cards WHERE image_tcgdex IS NOT NULL").fetchone()[0]
of  = con.execute("SELECT COUNT(*) FROM cards WHERE local_file IS NOT NULL").fetchone()[0]
either = con.execute("SELECT COUNT(*) FROM cards WHERE image_tcgdex IS NOT NULL OR local_file IS NOT NULL").fetchone()[0]
print(f"紐付け {linked:,}件")
print(f"  TCGdexに画像      {tc:,}")
print(f"  公式から取得       {of:,}")
print(f"  どちらかで絵がある  {either:,} / {tot:,} ({100*either/tot:.1f}%)")
print("\n主要パックの状況:")
for r in con.execute("""SELECT s.name, COUNT(c.id),
        SUM(CASE WHEN c.local_file IS NOT NULL THEN 1 ELSE 0 END),
        SUM(CASE WHEN c.image_tcgdex IS NOT NULL THEN 1 ELSE 0 END)
      FROM cards c JOIN sets s ON c.set_id=s.id
      GROUP BY s.id ORDER BY s.release DESC LIMIT 10"""):
    print(f"  {(r[0] or '')[:22]:<24} {r[1]:>4}枚  公式{r[2]:>4} TCGdex{r[3]:>4}")
