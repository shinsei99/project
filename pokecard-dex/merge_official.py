"""公式にしか存在しないカードを cards テーブルに追加する。

TCGdex は同名カード（同じカードが複数デッキに収録される等）を1件にまとめるため、
公式より枚数が少ない。例: スタートデッキ100 は 公式894枚 / TCGdex774枚。
その差分（120枚）は図鑑に表示されず「抜け」になっていた。

差分ぶんは official 側の情報だけで cards に足す。ワザや効果文は無いが、
同名カードの TCGdex 側データを引き継いで補う。
"""
import sqlite3, collections, time

con = sqlite3.connect("data/cards.db", timeout=120)
con.execute("PRAGMA busy_timeout = 120000")

added = 0
pending = []

# TCGdex に存在しないセット（公式にしかない最新パック等）を sets に登録する。
# 例: M6（アビスアイの次のパック）、MEM/MEZ/MEE。これを入れないと
# merge の対象外になり、図鑑に丸ごと出てこない。
# 公式サイトの詳細ページにセット名が無いため、記号→正式名称の対応は
# data/set_names.json で手動管理する（例: M6 = ストームエメラルダ）。
import json, os
_names_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "set_names.json")
try:
    _raw = {k: v for k, v in json.load(open(_names_path, encoding="utf-8")).items()
            if not k.startswith("_")}
except Exception:
    _raw = {}
# 値は文字列（名前だけ）と {"name":..., "release":...} の両方を許す
SET_NAMES, SET_RELEASE = {}, {}
for sc, v in _raw.items():
    if isinstance(v, dict):
        SET_NAMES[sc] = v.get("name") or sc
        if v.get("release"):
            SET_RELEASE[sc] = v["release"]
    else:
        SET_NAMES[sc] = v

# 名前が判明したセットは、既に登録済みでも名称を更新する
for sc, nm in SET_NAMES.items():
    con.execute("UPDATE sets SET name=? WHERE id=? AND (name LIKE '%名称未取得%' OR name=?)",
                (nm, sc, sc))
# 発売日が分かったものは並び順を直す（IDから作った仮の値を上書き）
for sc, rel in SET_RELEASE.items():
    con.execute("UPDATE sets SET release=? WHERE id=? AND (release IS NULL OR release LIKE '9%')",
                (rel, sc))
con.commit()

known = {r[0] for r in con.execute("SELECT id FROM sets")}
new_sets = []
for sc, n, maxid in con.execute("""SELECT set_code, COUNT(*), MAX(card_id) FROM official
        WHERE status='ok' AND set_code IS NOT NULL GROUP BY set_code"""):
    if sc not in known:
        # 発売日は不明なので、IDの大きさから並び順だけ作る（新しいIDほど新しい）
        nm = SET_NAMES.get(sc, f"{sc}（公式のみ・名称未取得）")
        new_sets.append((sc, nm, "公式サイト", f"9{maxid:06d}", n, n, None, None))
if new_sets:
    con.executemany("INSERT OR REPLACE INTO sets VALUES (?,?,?,?,?,?,?,?)", new_sets)
    con.commit()
    print(f"TCGdexに無いセットを {len(new_sets)}件 登録: " +
          ", ".join(s[0] for s in new_sets[:10]))
for set_code, in con.execute("SELECT DISTINCT set_code FROM official WHERE status='ok' AND set_code IS NOT NULL"):
    COLS = ("id,set_id,local_id,name,category,rarity,hp,types,stage,illustrator,"
            "description,attacks,weaknesses,retreat,regulation,image_tcgdex,"
            "image_official,local_file")
    tc = collections.defaultdict(list)      # 名前 → TCGdexの行
    for row in con.execute(f"SELECT {COLS} FROM cards WHERE set_id=?", (set_code,)):
        tc[row[3]].append(row)              # row[3] = name
    off = collections.defaultdict(list)
    for cid, name, local in con.execute(
            "SELECT card_id, name, local FROM official "
            "WHERE set_code=? AND status='ok' AND local IS NOT NULL ORDER BY card_id", (set_code,)):
        off[name].append((cid, local))

    for name, entries in off.items():
        base = tc.get(name)
        surplus = entries[len(base) if base else 0:]     # TCGdexに収まらなかったぶん
        for i, (cid, local) in enumerate(surplus, 1):
            new_id = f"{set_code}-off{cid}"
            if base:
                b = list(base[0])
                b[0] = new_id                            # id
                b[2] = f"{b[2]}†{i}" if b[2] else f"†{i}" # local_id（別版の印）
                b[15] = None                             # image_tcgdex は使わない
                b[16] = cid                              # image_official
                b[17] = local                            # local_file
            else:
                b = [new_id, set_code, f"†{i}", name, None, None, None, "[]",
                     None, None, None, "[]", "[]", None, None, None, cid, local]
            pending.append(b)
            added += 1

# 取得プロセスが同じDBに書き込み続けているため、
# executemany で一度に流し込んでロック時間を最小にする
for attempt in range(12):
    try:
        con.executemany(f"INSERT OR REPLACE INTO cards ({COLS}) VALUES (" + ",".join("?"*18) + ")", pending)
        con.commit()
        break
    except sqlite3.OperationalError as e:
        if "locked" not in str(e) or attempt == 11:
            raise
        time.sleep(10)

tot = con.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
wi  = con.execute("SELECT COUNT(*) FROM cards WHERE local_file IS NOT NULL OR image_tcgdex IS NOT NULL").fetchone()[0]
print(f"追加 {added:,}枚 → カード合計 {tot:,}枚 / 絵がある {wi:,}枚 ({100*wi/tot:.1f}%)")
for sid, nm in (("MC","スタートデッキ100"), ("M2a","MEGAドリームex"), ("M5","アビスアイ")):
    r = con.execute("SELECT COUNT(*), SUM(local_file IS NOT NULL) FROM cards WHERE set_id=?", (sid,)).fetchone()
    o = con.execute("SELECT COUNT(*) FROM official WHERE set_code=? AND status='ok'", (sid,)).fetchone()[0]
    print(f"  {nm:<18} 図鑑{r[0]:>4}枚 / 絵{r[1] or 0:>4}枚 / 公式取得{o:>4}枚")
