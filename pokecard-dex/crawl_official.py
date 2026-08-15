"""
公式サイト（pokemon-card.com）から日本語版の全カードを取得する。

TCGdex は最新11パックの画像を一切収録しておらず（アビスアイ・ニンジャスピナー等が0%）、
セット単位の一覧APIも公開されていないため、カードIDの連番を辿る方式を採る。

  ・カードIDは 1 〜 約52,000 の連番。欠番は302で返る
  ・画像は large（1枚1MB）の1種類のみ。原寸だと3万枚で30GBになり
    ディスクに収まらないので、**取得後すぐ360px/品質85に縮小**して保存する（1枚56KB→計1.6GB）
    ※サーバーから落とすのは常に1MBの原寸。節約できるのはローカルの容量だけ
  ・中断・再開できる。既に取得済みのIDは飛ばす

⚠️ 公開サイトへの大量アクセスになるため、既定で1秒あたり2件までに抑えている。
   カード画像の著作権は ©Pokémon/Nintendo/Creatures/GAME FREAK に帰属する。
   取得物は自分の手元での参照に限り、公開・配布しない（data/ は gitignore）。

  ・IDの低い側（1〜5,000）は8割以上が欠番で、新しいカードは高いIDに詰まっている。
    実測で ID 1〜4,600 の有効率は13%だった。最新パックから欲しい場合は desc を付ける。

使い方:
    python crawl_official.py 1 52000 desc   # 最新パックから遡る（推奨）
    python crawl_official.py 1 52000        # 古い順
    python crawl_official.py 40000 52000    # 範囲を指定
"""

from __future__ import annotations

import io
import os
import re
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from PIL import Image

BASE = "https://www.pokemon-card.com"
DB = "data/cards.db"
IMG_DIR = "data/images"

IMG_WIDTH = 360          # 保存する画像の幅（原寸868pxから縮小）
IMG_QUALITY = 85         # 1枚約56KB。3万枚で約1.6GB に収まる
REQ_PER_SEC = 2.0        # サイトへの負荷を抑えるための上限
WORKERS = 2

S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept-Language": "ja,en;q=0.8",
})

_lock = threading.Lock()
_last = [0.0]


def throttle():
    """全スレッド合わせて REQ_PER_SEC を超えないように待つ。"""
    with _lock:
        wait = 1.0 / REQ_PER_SEC - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()


def setup(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS official (
      card_id   INTEGER PRIMARY KEY,   -- 公式サイトのカードID
      name      TEXT,
      set_code  TEXT,                  -- 画像パスに含まれるセット記号（M4, SV5M …）
      img_name  TEXT,                  -- 画像ファイル名
      local     TEXT,                  -- 保存したローカルパス
      status    TEXT,                  -- ok / gone / error
      fetched   REAL
    );
    CREATE INDEX IF NOT EXISTS idx_off_set  ON official(set_code);
    CREATE INDEX IF NOT EXISTS idx_off_name ON official(name);
    """)
    con.commit()


def parse(html: str):
    """カード名と画像パスを取り出す。取れなければ None。"""
    m = re.search(r'src="(/assets/images/card_images/large/([^/]+)/([^"]+))"', html)
    if not m:
        return None
    n = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    name = re.sub(r"<[^>]+>", "", n.group(1)).strip() if n else None
    return {"path": m.group(1), "set_code": m.group(2), "img_name": m.group(3), "name": name}


def fetch_one(cid: int):
    """1枚ぶん取得して縮小保存する。戻り値は official テーブルの行。"""
    throttle()
    try:
        r = S.get(f"{BASE}/card-search/details.php/card/{cid}/regu/all",
                  timeout=45, allow_redirects=False)
    except Exception:
        return (cid, None, None, None, None, "error", time.time())

    if r.status_code in (301, 302, 303, 307, 308):
        return (cid, None, None, None, None, "gone", time.time())      # 欠番
    if r.status_code == 429 or r.status_code == 403:
        time.sleep(30)                                                  # 締められたら休む
        return (cid, None, None, None, None, "error", time.time())
    if r.status_code != 200:
        return (cid, None, None, None, None, "error", time.time())

    info = parse(r.text)
    if not info:
        return (cid, None, None, None, None, "error", time.time())

    dst = os.path.join(IMG_DIR, info["set_code"], f"{cid}.jpg")
    if not os.path.exists(dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        throttle()
        try:
            ir = S.get(BASE + info["path"], timeout=90)
            if ir.status_code != 200:
                return (cid, info["name"], info["set_code"], info["img_name"], None,
                        "error", time.time())
            im = Image.open(io.BytesIO(ir.content)).convert("RGB")
            im.thumbnail((IMG_WIDTH, IMG_WIDTH * 2), Image.LANCZOS)
            im.save(dst, quality=IMG_QUALITY, optimize=True)
        except Exception:
            return (cid, info["name"], info["set_code"], info["img_name"], None,
                    "error", time.time())

    return (cid, info["name"], info["set_code"], info["img_name"], dst, "ok", time.time())


def main():
    lo = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    hi = int(sys.argv[2]) if len(sys.argv) > 2 else 52000
    desc = "desc" in sys.argv[3:]

    os.makedirs(IMG_DIR, exist_ok=True)
    # 自動反映（link_official / merge_official）が同じDBに書き込むため、
    # ロック待ちを長く取る。これが無いと衝突した瞬間に落ちて取得が止まる。
    con = sqlite3.connect(DB, timeout=180)
    con.execute("PRAGMA busy_timeout = 180000")
    setup(con)

    done = {r[0] for r in con.execute("SELECT card_id FROM official WHERE status IN ('ok','gone')")}
    todo = [i for i in range(lo, hi + 1) if i not in done]
    if desc:
        todo.reverse()      # 新しいカードが詰まっている高いIDから先に取る
    print(f"対象 {len(todo):,}件（{lo}〜{hi} のうち未取得分"
          f"{'・最新から遡る' if desc else ''}）", flush=True)
    if not todo:
        print("すべて取得済みです。", flush=True)
        return

    est = len(todo) * 2 / REQ_PER_SEC / 3600            # 詳細＋画像で2リクエスト
    print(f"上限 {REQ_PER_SEC}件/秒 → 見込み約 {est:.1f}時間", flush=True)

    t0 = time.time()
    ok = gone = err = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for n, row in enumerate(ex.map(fetch_one, todo), 1):
            for attempt in range(20):           # 競合しても諦めずに書き込む
                try:
                    # read_official.py が読み取った番号・レアリティ（card_no /
                    # rarity_img）を消さないよう、列を指定した UPSERT にする。
                    # INSERT OR REPLACE だと行ごと差し替わって読み取り結果が失われる。
                    con.execute("""
                        INSERT INTO official
                          (card_id, name, set_code, img_name, local, status, fetched)
                        VALUES (?,?,?,?,?,?,?)
                        ON CONFLICT(card_id) DO UPDATE SET
                          name=excluded.name, set_code=excluded.set_code,
                          img_name=excluded.img_name, local=excluded.local,
                          status=excluded.status, fetched=excluded.fetched""", row)
                    break
                except sqlite3.OperationalError as e:
                    if "locked" not in str(e) or attempt == 19:
                        raise
                    time.sleep(3)
            st = row[5]
            ok += st == "ok"; gone += st == "gone"; err += st == "error"
            if n % 25 == 0:
                con.commit()
                el = time.time() - t0
                print(f"\r  {n:,}/{len(todo):,}  取得{ok:,} 欠番{gone:,} 失敗{err:,}  "
                      f"{el/3600:.1f}h経過 / 残り約{(len(todo)-n)/(n/el)/3600:.1f}h",
                      end="", flush=True)
    con.commit()
    print(f"\n完了: 取得{ok:,} / 欠番{gone:,} / 失敗{err:,} / {(time.time()-t0)/3600:.1f}時間", flush=True)
    con.close()


if __name__ == "__main__":
    main()
