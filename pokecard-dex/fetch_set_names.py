"""公式サイトから セット記号 → 商品名・発売日 を取得する。

カード詳細ページには収録商品へのリンクが埋まっている。
    <a href="/ex/m6/">拡張パック「ストームエメラルダ」</a>
さらにその商品ページ（/ex/m6/）には「発売日：2026年7月31日」が載っている。
TCGdex に無いセットは発売日も不明で並び順が崩れるため、ここで両方取る。

セット記号ごとに代表カード1枚＋商品ページの2リクエストで済む。
結果は data/set_names.json に追記する（既に手で書いた内容は上書きしない）。
"""
import html, json, os, re, sqlite3, time
import requests

BASE = "https://www.pokemon-card.com"
NAMES = "data/set_names.json"
S = requests.Session()
S.headers.update({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"})

LINK = re.compile(r'<a[^>]*href="(/(?:ex|products)/[^"]*)"[^>]*>\s*([^<]{2,60}?)\s*</a>')


def clean(name: str) -> str:
    """「拡張パック「ストームエメラルダ」」→「ストームエメラルダ」"""
    name = html.unescape(name)          # &amp; などを戻す
    m = re.search(r'[「『]([^」』]+)[」』]', name)
    if m:
        return m.group(1).strip()
    return re.sub(r'\s+', " ", name).strip()


def main():
    con = sqlite3.connect("data/cards.db", timeout=180)
    try:
        cur = json.load(open(NAMES, encoding="utf-8"))
    except Exception:
        cur = {"_comment": "セット記号 → 正式名称。fetch_set_names.py が公式から取得して追記する。"}

    # 名前が無いもの、および発売日が仮の値（IDから作った 9xxxxxxx）のものを対象にする。
    # 仮の値のままだと発売日順の並びが本物の日付より上に来てしまう。
    need = [r[0] for r in con.execute(
        "SELECT id FROM sets WHERE name LIKE '%名称未取得%' OR release LIKE '9%' ORDER BY id")]
    todo = [c for c in need
            if not (isinstance(cur.get(c), dict) and cur[c].get("release"))]
    print(f"名前を調べるセット {len(todo)}件", flush=True)

    got = 0
    for i, code in enumerate(todo, 1):
        # そのセットの代表カード1枚のIDを使う
        row = con.execute("SELECT card_id FROM official WHERE set_code=? AND status='ok' "
                          "ORDER BY card_id LIMIT 1", (code,)).fetchone()
        if not row:
            continue
        try:
            time.sleep(0.6)                      # 取得プロセスと並走するので控えめに
            r = S.get(f"{BASE}/card-search/details.php/card/{row[0]}/regu/all", timeout=45)
            if r.status_code != 200:
                continue
            # 商品リンクがあれば文言を問わず採用する。
            # 「拡張パック」「デッキ」等で絞ると、バトルアカデミーや
            # ファミリーポケモンカードゲームのような商品を取り逃す。
            links = LINK.findall(r.text)
            if links:
                # 同じhrefで複数出るときは長い方（正式名称に近い）を選ぶ
                href = links[0][0]
                text = max((t for _, t in links), key=len)
                name = clean(text)
                rel = None
                try:                             # 商品ページから発売日も取る
                    time.sleep(0.6)
                    pr = S.get(BASE + href, timeout=45)
                    if pr.status_code == 200:
                        m = re.search(r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", pr.text)
                        if m:
                            rel = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
                except Exception:
                    pass
                cur[code] = {"name": name, "release": rel} if rel else name
                got += 1
                print(f"  {code:<8} {name}" + (f"  発売 {rel}" if rel else ""), flush=True)
        except Exception:
            continue
        if i % 10 == 0:
            json.dump(cur, open(NAMES, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    json.dump(cur, open(NAMES, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n{got}件の名前を取得 → {NAMES}", flush=True)


if __name__ == "__main__":
    main()
