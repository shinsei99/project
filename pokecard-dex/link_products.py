"""商品（products）とセット（sets）を対応づけ、セットに商品種別と表紙を持たせる。

対応は set_names.json に記録済みの「セット記号 → 商品名」を突き合わせて行う。
名前が完全一致しない場合は、括弧内の題名（例「ストームエメラルダ」）で照合する。
"""
import json, os, re, sqlite3

con = sqlite3.connect("data/cards.db", timeout=180)
con.execute("PRAGMA busy_timeout = 180000")
cols = {r[1] for r in con.execute("PRAGMA table_info(sets)")}
for c, t in (("ptype", "TEXT"), ("cover", "TEXT")):
    if c not in cols:
        con.execute(f"ALTER TABLE sets ADD COLUMN {c} {t}")
con.commit()

def core(s):
    """商品名から題名部分だけ取り出して正規化する。"""
    s = re.sub(r"\s+", "", s or "")
    m = re.search(r"[「『]([^」』]+)[」』]", s)
    if m:
        s = m.group(1)
    return re.sub(r"[（(].*?[)）]", "", s).replace("　", "")

# セット商品・デラックス版・ポケモンセンター限定などは、中身が既存パックと同じなので
# セットの代表としては使わない（一覧に重複して出ても意味がない）。
EXCLUDE = ("デラックス", "ポケモンセンターセット", "スペシャルセット", "同時購入")
prods = [dict(title=r[0], ptype=r[1], release=r[2], cover=r[4])
         for r in con.execute("SELECT title, ptype, release, price, cover FROM products")
         if not any(x in (r[0] or "") for x in EXCLUDE)]
by_core = {}
for p in prods:
    by_core.setdefault(core(p["title"]), p)

linked = 0
for sid, name in con.execute("SELECT id, name FROM sets").fetchall():
    p = by_core.get(core(name))
    if not p:
        # セット名が商品名に含まれるケースも拾う
        cn = core(name)
        if len(cn) >= 4:
            for k, v in by_core.items():
                if cn and (cn in k or k in cn):
                    p = v
                    break
    if not p:
        continue
    con.execute("UPDATE sets SET ptype=?, cover=? WHERE id=?", (p["ptype"], p["cover"], sid))
    # 発売日が仮の値なら商品側の日付で直す
    if p["release"]:
        con.execute("UPDATE sets SET release=? WHERE id=? AND (release IS NULL OR release LIKE '9%')",
                    (p["release"], sid))
    linked += 1
con.commit()

print(f"セットと商品を対応づけ: {linked} / {len(prods)}商品")
for r in con.execute("SELECT ptype, COUNT(*), SUM(cover IS NOT NULL) FROM sets GROUP BY ptype"):
    print(f"  {str(r[0]):<14} {r[1]:>4}セット  表紙 {r[2] or 0}")
