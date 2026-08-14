"""公式の商品情報APIから、商品の種類・表紙画像・発売日を取得する。

    /products/resultAPI.php?productType=expansion&...&page=1

拡張パック / 構築デッキ / その他 を区別したいので、商品ごとにこの分類を持つ。
表紙画像（tumbsImg）も落として、パックの表紙一覧を作れるようにする。

商品とセット記号（M6 等）の対応は、商品ページ /ex/<code>/ のURLから取る。
"""
import json, os, re, sqlite3, time
import requests

BASE = "https://www.pokemon-card.com"
IMG_DIR = "data/products"
S = requests.Session()
S.headers.update({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"})

# カードが入っている商品だけ。peripheral（デッキケース・スリーブ等の
# 周辺グッズ）はカードが無いので取得しない。
TYPES = {"expansion": "拡張パック", "construction": "構築デッキ",
         "others": "その他の商品"}


def setup(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS products (
      title TEXT PRIMARY KEY,
      ptype TEXT,            -- 拡張パック / 構築デッキ / その他の商品 / サプライ
      release TEXT,          -- YYYY-MM-DD
      price TEXT,
      cover TEXT,            -- 表紙画像のローカルパス
      set_code TEXT,         -- 対応するセット記号（分かった場合）
      url TEXT
    );
    """)
    con.commit()


def jp_date(s):
    m = re.search(r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", s or "")
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else None


def api(ptype, page):
    q = (f"productType={ptype}&keyword=&priceLower=0&priceUpper=1000000"
         f"&dateLowerY=1996&dateLowerM=1&dateLowerD=1"
         f"&dateUpperY=2027&dateUpperM=12&dateUpperD=31&sort=1&page={page}")
    r = S.get(f"{BASE}/products/resultAPI.php?{q}", timeout=60)
    r.raise_for_status()
    return r.json()


def main():
    os.makedirs(IMG_DIR, exist_ok=True)
    con = sqlite3.connect("data/cards.db", timeout=180)
    con.execute("PRAGMA busy_timeout = 180000")
    setup(con)

    total = 0
    for ptype, label in TYPES.items():
        page, maxpage = 1, 1
        while page <= maxpage:
            try:
                d = api(ptype, page)
            except Exception as e:
                print(f"  {label} p{page} 失敗: {str(e)[:80]}", flush=True)
                break
            maxpage = d.get("maxPage", 1)
            for p in d.get("products", []):
                title = p.get("productTitle") or ""
                rel = jp_date(p.get("releaseDate"))
                cover = None
                img = p.get("tumbsImg")
                if img:
                    dst = os.path.join(IMG_DIR, re.sub(r"[^\w.-]", "_", os.path.basename(img)))
                    if not os.path.exists(dst):
                        try:
                            time.sleep(0.4)
                            ir = S.get(BASE + img, timeout=60)
                            if ir.status_code == 200:
                                open(dst, "wb").write(ir.content)
                        except Exception:
                            pass
                    if os.path.exists(dst):
                        cover = dst
                con.execute("INSERT OR REPLACE INTO products VALUES (?,?,?,?,?,?,?)",
                            (title, p.get("productType") or label, rel,
                             p.get("priceTxt"), cover, None, img))
                total += 1
            con.commit()
            print(f"\r  {label}: {page}/{maxpage}ページ  累計 {total}件", end="", flush=True)
            page += 1
            time.sleep(0.5)
        print(flush=True)

    print(f"\n商品 {total}件を取得", flush=True)
    for r in con.execute("SELECT ptype, COUNT(*) FROM products GROUP BY ptype"):
        print(f"  {r[0]:<12} {r[1]:>4}件")


if __name__ == "__main__":
    main()
