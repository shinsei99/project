"""スニダン（snkrdunk.com）の商品画像から、他のどこにも無いカードを補う。

なぜここを使うのか:
  learn-book は eシリーズのページに一部の番号を載せていない（E4 の 069 グランブル
  など）。マイカ・公式・TCGdex にもこの年代は無い。フリマ系サイトのうち
  **スニダンだけが「背景除去済み・透かしなし・1000px級」の画像**を持っていた。

  比較（E4-069 グランブルで実測）:
      スニダン        1000×730（切り抜き後 430×610）透かし無し・背景透明
      フルアヘッド      287×400  中央に「COPY」の透かし
      learn-book     そもそも 069 が無い

公開APIの使い方（再調査不要）:
  GET https://snkrdunk.com/v1/apparels/<id>   … 認証不要・JSONを返す
      productNumber       "pkmn-tcg-e4-069" ＝ セット記号と番号がそのまま入る
      name                "Granbull [e4 069/088](...)" 。":1ED" が付く版もある
      primaryMedia.imageUrl  https://cdn.snkrdunk.com/upload_bg_removed/....webp

  **商品IDは連番だが、カード1枚につき 1ED版と通常版で2つある**（E4-070 は
  430158=1ED / 430159=通常）ので、番号との一対一対応にはならない。
  ポケカ以外の商品（服・靴）も同じ連番に混ざる。そのため
  **IDは範囲を走査して productNumber で拾う**（`--scan`）。実測の位置:
      e3 … 429900 付近   e4 … 430070〜430195

  検索APIは見つけられなかった（`/v1/apparels/search` は存在するが引数不明。
  keyword / q / word / text / name / productNumber すべて bad_input）。
  サイト内検索ページは Next.js のクライアント描画で HTML に結果が出ない。

  画像は `upload_bg_removed`＝**背景がアルファで抜けている**ので、
  アルファの外接矩形で切り抜けばカードだけが正確に取れる。

⚠️ 取得は1秒1件に抑える。画像の著作権は ©Pokémon/Nintendo/Creatures/GAME FREAK
   に帰属し、取得物は手元での参照に限る（data/ は gitignore・公開配布しない）。

使い方:
    python snkrdunk.py --scan 430070 430200    # IDを走査して品番を一覧する
    python snkrdunk.py --dry-run               # 何枚照合できるか数える
    python snkrdunk.py                         # 取得して DB に記録
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sqlite3
import time
import urllib.request

from PIL import Image

DB = "data/cards.db"
IMG_DIR = "data/snkrdunk"
API = "https://snkrdunk.com/v1/apparels/{id}"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
      "Accept": "application/json"}
WAIT = 1.0

PN_RE = re.compile(r"^pkmn-tcg-(e\d)-(\d{3})$")

# 取りに行く商品ID。`--scan` で見つけたものを**カードを確かめてから**書く。
# learn-book に無かった E4 の6枚（2026-08-14）。
# 072 と 075 は 071 / 074 のキラ版で、スニダンは同じ1枚として扱っていて
# 別商品が無い。dex では build_dex.py の `add_twin_images()` が相方から埋める。
WANT = [430157, 430160, 430162, 430164, 430170, 430182]


def api(apparel_id: int) -> dict:
    req = urllib.request.Request(API.format(id=apparel_id), headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def scan(lo: int, hi: int) -> None:
    """IDを順に叩いて品番を並べる。どのIDがどのカードかを決めるための下調べ。"""
    for i in range(lo, hi + 1):
        try:
            d = api(i)
        except Exception:
            time.sleep(WAIT)
            continue
        pn = d.get("productNumber") or "-"
        if PN_RE.match(pn):
            print(f"{i} {pn:22} {d.get('name','')[:56]}", flush=True)
        time.sleep(WAIT)


def crop_card(raw: bytes) -> bytes:
    """背景が抜けている画像から、カードの外接矩形だけを切り出して JPEG にする。"""
    im = Image.open(io.BytesIO(raw))
    if im.mode in ("RGBA", "LA"):
        bb = im.split()[-1].getbbox()
        if bb:
            im = im.crop(bb)
    out = io.BytesIO()
    im.convert("RGB").save(out, "JPEG", quality=92)
    return out.getvalue()


def setup(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS snkrdunk (
      dex_key   TEXT PRIMARY KEY,
      apparel   INTEGER,
      pn        TEXT,        -- pkmn-tcg-e4-069
      name      TEXT,
      url       TEXT,
      local     TEXT,
      status    TEXT
    );
    """)
    con.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", nargs=2, type=int, metavar=("LO", "HI"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if a.scan:
        scan(*a.scan)
        return

    con = sqlite3.connect(DB)
    setup(con)
    n_hit = n_dl = 0
    for aid in WANT:
        try:
            d = api(aid)
        except Exception as e:
            print(f"{aid} 取得失敗: {e}")
            continue
        time.sleep(WAIT)
        pn = d.get("productNumber") or ""
        m = PN_RE.match(pn)
        if not m:
            print(f"{aid} 品番が想定と違う: {pn}")
            continue
        set_code, no = m.group(1).upper(), int(m.group(2))
        url = (d.get("primaryMedia") or {}).get("imageUrl")
        # 画像がまだ無い行だけを相手にする。番号が重複するセットは扱わない
        rows = con.execute(
            """SELECT key, name FROM dex
               WHERE set_code = ? AND card_no = ?
                 AND img IS NULL AND img_off IS NULL AND img_web IS NULL""",
            (set_code, no)).fetchall()
        if len(rows) != 1:
            print(f"{aid} {pn} dex の行が {len(rows)}件（1件でないので採らない）")
            continue
        key, dex_name = rows[0]
        n_hit += 1
        print(f"{aid} {pn} → {key}  dex名={dex_name!r}  {d.get('name','')[:40]}")
        if a.dry_run or not url:
            continue
        path = os.path.join(IMG_DIR, set_code, f"{key.replace('/', '_')}.jpg")
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            req = urllib.request.Request(url, headers={"User-Agent": UA["User-Agent"]})
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
            with open(path, "wb") as f:
                f.write(crop_card(raw))
            time.sleep(WAIT)
        n_dl += 1
        con.execute("""INSERT OR REPLACE INTO snkrdunk
                       (dex_key, apparel, pn, name, url, local, status)
                       VALUES (?,?,?,?,?,?,?)""",
                    (key, aid, pn, d.get("name"), url, path, "ok"))
        con.commit()

    print(f"\n照合 {n_hit}枚 / 取得 {n_dl}枚"
          + ("（--dry-run なので取得していない）" if a.dry_run else ""))
    print("このあと python build_dex.py で図鑑に反映する")


if __name__ == "__main__":
    main()
