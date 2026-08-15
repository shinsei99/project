"""TCGdex から日本語版の全カードデータを取得して SQLite に保存する。

画像は TCGdex にあるものだけ URL を記録する（収録率は約3割）。
残りは公式サイトから補完する想定（fill_images_official.py）。
"""
import json, os, sqlite3, sys, time
from concurrent.futures import ThreadPoolExecutor
import requests

API = "https://api.tcgdex.net/v2/ja"
DB = "data/cards.db"
S = requests.Session()
S.headers["User-Agent"] = "pokecard-dex/1.0 (personal use)"


def api(path, tries=4):
    for i in range(tries):
        try:
            r = S.get(f"{API}{path}", timeout=60)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:
                return None
        except Exception:
            pass
        time.sleep(1.5 * (i + 1))
    return None


def setup(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS sets (
      id TEXT PRIMARY KEY, name TEXT, serie TEXT, release TEXT,
      total INTEGER, official INTEGER, logo TEXT, symbol TEXT
    );
    CREATE TABLE IF NOT EXISTS cards (
      id TEXT PRIMARY KEY,          -- TCGdex の ID（例 SV2a-001）
      set_id TEXT, local_id TEXT, name TEXT, category TEXT, rarity TEXT,
      hp INTEGER, types TEXT, stage TEXT, illustrator TEXT,
      description TEXT, attacks TEXT, weaknesses TEXT, retreat INTEGER,
      regulation TEXT, image_tcgdex TEXT, image_official TEXT, local_file TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(name);
    CREATE INDEX IF NOT EXISTS idx_cards_set  ON cards(set_id);
    """)


def main():
    os.makedirs("data", exist_ok=True)
    con = sqlite3.connect(DB); setup(con)

    sets = api("/sets") or []
    print(f"セット {len(sets)}件", flush=True)
    t0, ncards = time.time(), 0
    for i, s in enumerate(sets, 1):
        d = api(f"/sets/{s['id']}")
        if not d:
            print(f"\n  取得失敗: {s['id']}", flush=True); continue
        cc = d.get("cardCount") or {}
        con.execute("INSERT OR REPLACE INTO sets VALUES (?,?,?,?,?,?,?,?)", (
            d["id"], d.get("name"), (d.get("serie") or {}).get("name"),
            d.get("releaseDate"), cc.get("total"), cc.get("official"),
            d.get("logo"), d.get("symbol")))
        cards = d.get("cards", [])
        # 1枚ずつ順番に詳細を取ると全体で2時間かかるため並列化する
        with ThreadPoolExecutor(max_workers=8) as ex:
            fulls = list(ex.map(lambda c: api(f"/cards/{c['id']}") or c, cards))
        for c, full in zip(cards, fulls):
            con.execute("INSERT OR REPLACE INTO cards VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                c["id"], d["id"], c.get("localId"), c.get("name"),
                full.get("category"), full.get("rarity"),
                full.get("hp"), json.dumps(full.get("types") or [], ensure_ascii=False),
                full.get("stage"), full.get("illustrator"), full.get("description"),
                json.dumps(full.get("attacks") or [], ensure_ascii=False),
                json.dumps(full.get("weaknesses") or [], ensure_ascii=False),
                full.get("retreat"), full.get("regulationMark"),
                c.get("image"), None, None))
            ncards += 1
        con.commit()
        el = time.time() - t0
        print(f"\r  {i}/{len(sets)} セット / {ncards:,}枚 / {el:.0f}s "
              f"/ 残り約{(len(sets)-i)/(i/el)/60:.0f}分", end="", flush=True)
    print(f"\n完了: {ncards:,}枚 / {time.time()-t0:.0f}s → {DB}", flush=True)
    n_img = con.execute("SELECT COUNT(*) FROM cards WHERE image_tcgdex IS NOT NULL").fetchone()[0]
    print(f"  TCGdexに画像あり: {n_img:,}枚 ({100*n_img/max(1,ncards):.1f}%)", flush=True)
    con.close()


if __name__ == "__main__":
    main()
