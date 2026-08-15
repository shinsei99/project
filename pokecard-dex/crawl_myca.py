"""
DMMマイカ（myca.dmm.com）から日本語版ポケモンカードの全データを取得する。

公式サイト（pokemon-card.com）は**レアリティを一切公開していない**ため、
番号の連続性やカード画像の隅をAIで読む方法を試したがどちらも実用にならなかった
（同じ番号帯にレアリティ有り・無しが混在するため規則性が無い）。
一方マイカは「番号/総数/レアリティ/セット記号」を文字列で持っている。

  ・封入パックの一覧は list ページの絞り込みメニューに全549件入っている
    （data/myca_packs.json。初代「第1弾拡張パック」1996年〜最新のMEGAまで）
  ・1パックあたり 46件/ページ で totalPages まで送る
  ・実測: ストームエメラルダ(M6) は 113枚すべて・欠番なし・レアリティ8種すべて取れた

取れるもの: カード名 / 番号 / 総数 / レアリティ / セット記号 / 画像ファイル名
画像URLは https://static.mycalinks.io/app/item/image/card/<SET>/<SET>_<NO>.gif
（180x251・認証不要。取得は fetch_myca_images.py）

⚠️ 公開サイトへのアクセスになるため 1秒1件に抑えている。
   カード画像・データの著作権は ©Pokémon/Nintendo/Creatures/GAME FREAK に帰属する。
   取得物は自分の手元での参照に限り、公開・配布しない（data/ は gitignore）。

使い方:
    python crawl_myca.py              # 未取得のパックを順に取る（中断・再開可）
    python crawl_myca.py 6621         # パックIDを指定して取り直す
    python crawl_myca.py --retry      # 失敗したパックだけやり直す
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request

BASE = "https://myca.dmm.com/pokemon-trading-card-game/list"
DB = "data/cards.db"
PACKS = "data/myca_packs.json"

REQ_INTERVAL = 1.0        # サイトへの負荷を抑えるための間隔（秒）

UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept-Language": "ja,en;q=0.8",
}

# 1商品ブロックは「カード名 → 番号/総数/レアリティ/セット」の順で現れる。
# 画像URLはその手前にあるので、名前の位置を起点に前後を探す。
NAME = re.compile(r'line-clamp-2[^>]*>([^<]{1,60})</p>')
# 「110/076/SAR/M6」＝番号/総数/レアリティ/セット。ただし表記に3つの揺れがある。
#   ・レアリティが無い普通のカード … 「406/414/sI」（3要素）
#   ・スタートデッキ100の特別仕様  … 「418/414/SR仕様/sI」
#   ・旧シリーズのミラー仕様       … 「408/414/ミラー/sI」
REC = re.compile(r'>(\d{1,3})/(\d{1,3})/(?:([^/<]{1,10})/)?([A-Za-z0-9-]{1,8})<')
IMG = re.compile(r'card%2F([A-Za-z0-9_-]+)%2F([A-Za-z0-9_-]+)\.(?:gif|jpg|png)')
# 旧裏面カードのレアリティ表記。フィルタの選択肢にあった記号をそのまま拾う
SYMBOL = re.compile(r'min-h-\[1em\][^>]*text-\[10px\][^>]*>\s*([●◆★◇○☆eキラミラー]{1,3})\s*</span>')
TOTAL_PAGES = re.compile(r'totalPages\\":(\d+)')

_last = [0.0]


def norm_rarity(r: str | None) -> str | None:
    """マイカ表記のレアリティを検索に使える形に揃える。

    スタートデッキ100は「MUR仕様」「SAR仕様」「SR仕様」と表記されているが、
    レアリティとしては MUR / SAR / SR と同じものなので「仕様」を落とす。
    """
    if not r:
        return None
    r = r.strip().replace("仕様", "").strip()
    return r or None


def get(url: str, _depth: int = 0) -> str:
    """1秒1件に抑えて取得する。

    一部のパックは「200 だが本文が転送先のパスだけ」という応答を返す
    （例: プロモカードの pack_id=250 に &page=1 を付けたとき、56バイトで
    "/pokemon-trading-card-game/list?myca_primary_pack_id=250" だけが返る）。
    HTTPのリダイレクトではないので urllib は追ってくれない。自分で追う。
    """
    wait = REQ_INTERVAL - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        html = r.read().decode("utf-8", "ignore")

    if len(html) < 4000 and _depth < 2:
        path = html.strip()
        if path.startswith("/"):
            return get("https://myca.dmm.com" + path, _depth + 1)
    return html


def setup(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS myca (
      set_code  TEXT,      -- セット記号（M6, sv8a …）。旧裏面は画像パス由来（dai1dan …）
      card_no   INTEGER,   -- 印刷されている番号（110/076 の 110）。旧裏面はNULL
      total     INTEGER,   -- 総数（同 076）。特別枠は total を超える。旧裏面はNULL
      rarity    TEXT,      -- C U R RR SR SAR AR MUR MA … / 旧裏面は ● ◆ ★ などの記号
      name      TEXT,
      img_set   TEXT,      -- 画像パスのセット（M6 / dai1dan …）
      img_file  TEXT,      -- M6_110 / 1st1093 形式。画像URLの組み立てに使う
      pack_id   TEXT,
      pack_name TEXT,
      fetched   REAL,
      PRIMARY KEY (img_set, img_file, pack_id)
    );
    CREATE INDEX IF NOT EXISTS idx_myca_set  ON myca(set_code);
    CREATE INDEX IF NOT EXISTS idx_myca_name ON myca(name);
    CREATE INDEX IF NOT EXISTS idx_myca_pack ON myca(pack_id);

    CREATE TABLE IF NOT EXISTS myca_packs (
      pack_id   TEXT PRIMARY KEY,
      pack_name TEXT,
      pages     INTEGER,
      cards     INTEGER,
      status    TEXT,      -- ok / error
      fetched   REAL
    );
    """)
    con.commit()


def parse(html: str):
    """1ページからカードを取り出す。

    表記が2系統ある。
      新（DP以降）: 「110/076/SAR/M6」＝ 番号/総数/レアリティ/セット記号
      旧（旧裏面）: 番号表記が無く、レアリティが ● ◆ ★ ◇ ○ ☆ などの記号だけ
    どちらもセットと画像は画像URL（.../card/<SET>/<FILE>.gif）から取れる。
    """
    out = []
    for m in NAME.finditer(html):
        tail = html[m.end():m.end() + 900]
        head = html[max(0, m.start() - 2500):m.start()]
        img_set = img_file = None
        for i in IMG.finditer(head):     # 直前のものが自分の画像
            img_set, img_file = i.group(1), i.group(2)
        if not img_file:
            continue

        r = REC.search(tail)
        if r:
            no, total, rarity, set_code = (int(r.group(1)), int(r.group(2)),
                                           norm_rarity(r.group(3)), r.group(4))
        else:
            sym = SYMBOL.search(tail)
            if sym:
                no, total, rarity, set_code = None, None, sym.group(1), img_set
            else:
                # プロモは番号・総数の表記が無く、レアリティ欄も空で描画される。
                # 画像ファイル名（SV-P_001n）から番号だけ拾い、レアリティは
                # あとから rarity 絞り込みの巡回（fill_rarity_myca.py）で埋める。
                m2 = re.search(r"_(\d{1,3})", img_file)
                no = int(m2.group(1)) if m2 else None
                total, rarity, set_code = None, None, img_set

        out.append({
            "name": m.group(1).strip(),
            "card_no": no, "total": total, "rarity": rarity, "set_code": set_code,
            "img_set": img_set, "img_file": img_file,
        })
    return out


def crawl_pack(con, pack_id: str, pack_name: str) -> tuple[int, int]:
    """1パックを全ページ巡回して書き込む。戻り値は (ページ数, 新規カード数)。"""
    page, total_pages, rows = 1, None, {}
    while True:
        # page=1 を明示すると404になるパックがある（30th CELEBRATION 等）。
        # 1ページ目はパラメータを付けない。
        url = f"{BASE}?myca_primary_pack_id={pack_id}" + (f"&page={page}" if page > 1 else "")
        try:
            html = get(url)
        except urllib.error.HTTPError as e:
            if e.code == 404 and page > 1:
                break            # totalPages を超えたページは404。取れた分で確定させる
            raise
        if total_pages is None:
            m = TOTAL_PAGES.search(html)
            total_pages = int(m.group(1)) if m else 1
        for c in parse(html):
            # 同じカードが複数出品されるので、最初に見たものを採る
            rows.setdefault((c["img_set"], c["img_file"]), c)
        if page >= total_pages:
            break
        page += 1

    now = time.time()
    data = [(c["set_code"], c["card_no"], c["total"], c["rarity"], c["name"],
             c["img_set"], c["img_file"], pack_id, pack_name, now)
            for c in rows.values()]
    write(con, "INSERT OR REPLACE INTO myca VALUES (?,?,?,?,?,?,?,?,?,?)", data)
    return total_pages, len(data)


def write(con, sql: str, data):
    """公式クローラと同じDBを触るので、ロック待ちで諦めない。"""
    for attempt in range(20):
        try:
            con.executemany(sql, data) if isinstance(data, list) else con.execute(sql, data)
            con.commit()
            return
        except sqlite3.OperationalError as e:
            if "locked" not in str(e) or attempt == 19:
                raise
            time.sleep(3)


def main():
    packs = json.load(open(PACKS, encoding="utf-8"))
    con = sqlite3.connect(DB, timeout=180)
    con.execute("PRAGMA busy_timeout = 180000")
    setup(con)

    args = sys.argv[1:]
    if args and args[0].isdigit():
        todo = [p for p in packs if p["id"] == args[0]]
    elif "--retry" in args:
        # 失敗したものと、0枚しか取れなかったものをやり直す
        bad = {r[0] for r in con.execute(
            "SELECT pack_id FROM myca_packs WHERE status='error' OR cards=0")}
        todo = [p for p in packs if p["id"] in bad]
    else:
        done = {r[0] for r in con.execute("SELECT pack_id FROM myca_packs WHERE status='ok'")}
        todo = [p for p in packs if p["id"] not in done]

    print(f"対象 {len(todo)}/{len(packs)}パック（1秒1件・見込み約{len(todo)*3*1.0/60:.0f}分）",
          flush=True)
    t0, cards = time.time(), 0
    for n, p in enumerate(todo, 1):
        try:
            pages, got = crawl_pack(con, p["id"], p["name"])
            st = "ok"
        except Exception as e:
            pages, got, st = 0, 0, "error"
            print(f"\n  !! {p['name']} ({p['id']}): {e}", flush=True)
        write(con, "INSERT OR REPLACE INTO myca_packs VALUES (?,?,?,?,?,?)",
              (p["id"], p["name"], pages, got, st, time.time()))
        cards += got
        el = time.time() - t0
        print(f"\r  {n}/{len(todo)}  {p['name'][:22]:<24} {got:>4}枚  "
              f"累計{cards:,}枚 / {el/60:.0f}分経過 / 残り約"
              f"{(len(todo)-n)/(n/el)/60:.0f}分   ", end="", flush=True)

    tot = con.execute("SELECT COUNT(*) FROM myca").fetchone()[0]
    uniq = con.execute("SELECT COUNT(*) FROM (SELECT DISTINCT set_code, card_no FROM myca)"
                       ).fetchone()[0]
    print(f"\n完了: 今回{cards:,}枚 / 全{tot:,}行（ユニーク{uniq:,}枚）"
          f" / {(time.time()-t0)/60:.0f}分", flush=True)
    con.close()


if __name__ == "__main__":
    main()
