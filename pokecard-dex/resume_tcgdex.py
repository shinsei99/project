"""不足しているセットだけを取り直す。
セットIDに `+`（SM4+ など）が含まれるとURL上で空白と解釈されるため、
クエリではなくパスとして安全にエンコードする必要がある。"""
import json, sqlite3, time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote
import requests

API = "https://api.tcgdex.net/v2/ja"
S = requests.Session(); S.headers["User-Agent"] = "pokecard-dex/1.0 (personal use)"

def api(path, tries=4):
    for i in range(tries):
        try:
            r = S.get(f"{API}{path}", timeout=60)
            if r.status_code == 200: return r.json()
            if r.status_code == 404: return None
        except Exception: pass
        time.sleep(1.5 * (i + 1))
    return None

con = sqlite3.connect("data/cards.db")
have = {r[0]: r[1] for r in con.execute("SELECT set_id, COUNT(*) FROM cards GROUP BY set_id")}
sets = api("/sets") or []
todo = [s for s in sets
        if have.get(s["id"], 0) < ((s.get("cardCount") or {}).get("total") or 0)]
print(f"取り直すセット {len(todo)}件", flush=True)

fixed = 0
for i, s in enumerate(todo, 1):
    sid = s["id"]
    d = api(f"/sets/{quote(sid, safe='')}")          # ← ここがエンコード
    if not d:
        print(f"\n  なお失敗: {sid}", flush=True); continue
    cc = d.get("cardCount") or {}
    con.execute("INSERT OR REPLACE INTO sets VALUES (?,?,?,?,?,?,?,?)", (
        d["id"], d.get("name"), (d.get("serie") or {}).get("name"), d.get("releaseDate"),
        cc.get("total"), cc.get("official"), d.get("logo"), d.get("symbol")))
    cards = d.get("cards", [])
    with ThreadPoolExecutor(max_workers=6) as ex:
        fulls = list(ex.map(lambda c: api(f"/cards/{quote(c['id'], safe='')}") or c, cards))
    for c, full in zip(cards, fulls):
        con.execute("INSERT OR REPLACE INTO cards VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            c["id"], d["id"], c.get("localId"), c.get("name"), full.get("category"),
            full.get("rarity"), full.get("hp"),
            json.dumps(full.get("types") or [], ensure_ascii=False), full.get("stage"),
            full.get("illustrator"), full.get("description"),
            json.dumps(full.get("attacks") or [], ensure_ascii=False),
            json.dumps(full.get("weaknesses") or [], ensure_ascii=False),
            full.get("retreat"), full.get("regulationMark"), c.get("image"), None, None))
        fixed += 1
    con.commit()
    print(f"\r  {i}/{len(todo)}  +{fixed:,}枚", end="", flush=True)
print(f"\n追加 {fixed:,}枚 / 合計 {con.execute('SELECT COUNT(*) FROM cards').fetchone()[0]:,}枚", flush=True)
