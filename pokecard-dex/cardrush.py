"""カードラッシュ（cardrush-pokemon.jp）から、他のどこにも無いカードを補う。

なぜ手間をかけるのか（2026-08-14）:
  M-P（MEGA オーガナイザープロモカード・2026年）は、公式・マイカ・TCGdex・
  スニダン・pcg-search・カーナベル のどこにも画像が無かった。ここにだけあった。
  しかも **868×1212 で透かし無し**と、手持ちのどの取得元より高精細。

⚠️ **このサイトは Cloudflare で機械的なアクセスを弾く（HTTP 403）。**
   curl も WebFetch も通らない。UA やヘッダを変えても同じ。
   → **Safari を AppleScript で動かして読む**（psa-collection の
     `harvest_collectors.js` と同じ手口）。
     前提: Safari の「設定 > 詳細 > Webデベロッパ用の機能を表示」→
     「開発 > Apple Events からの JavaScript を許可」がON。

  ただし**画像そのもの（/data/cardrushpokemon/product/*.jpg）は素通しで、
  curl で普通に落ちる**。Cloudflare が守っているのは HTML ページだけ。
  そのため Safari で使うのは「商品ページ → og:image のURL」を読む部分だけ。

商品名の形（ここから番号を読む）:
    ジャンボアイス【P】{077/M-P} [M-P]
    〔状態A-〕タケシのスカウト【P】{083/M-P} [M-P]   ← 状態違いは別商品。避ける

探し方:
    https://www.cardrush-pokemon.jp/product-list?keyword=M-P&num=100&page=N
  で一覧を出し、商品名から {番号/セット} を拾う。実測 M-P は314件・4ページ。

使い方:
    python cardrush.py --search M-P        # 一覧から番号→商品IDを集める
    python cardrush.py --dry-run           # WANT の照合だけ
    python cardrush.py                     # 取得して DB に記録
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import subprocess
import time
import urllib.request

DB = "data/cards.db"
IMG_DIR = "data/cardrush"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
WAIT = 1.0

# 実測で確かめた対応（dex の set_code / card_no ↔ カードラッシュの商品ID）。
# **状態違い（〔状態A-〕〔状態B〕）ではない通常の商品を選ぶこと。**
# M-P 079 ふしぎなアメ はカードラッシュにも無い（一覧の番号が 077→080 で飛ぶ）。
WANT = [
    ("M-P", 77, 79130),   # ジャンボアイス
    ("M-P", 80, 79166),   # ポケギア3.0
    ("M-P", 83, 79129),   # タケシのスカウト
    ("M-P", 84, 79128),   # ボスの指令/カラスバ
]


def safari_js(url: str, js: str, wait: int = 7) -> str:
    """Safari でURLを開き、JavaScript の結果を返す（Cloudflare を通すため）。"""
    script = f'''
    tell application "Safari"
      if (count of documents) = 0 then make new document
      set URL of front document to "{url}"
      delay {wait}
      try
        return do JavaScript "{js}" in front document
      on error e
        return "ERR:" & e
      end try
    end tell'''
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return r.stdout.strip()


def search(keyword: str) -> None:
    """一覧を辿って「番号 → 商品ID」を並べる。WANT を書くための下調べ。"""
    js = ("Array.from(document.querySelectorAll('a[href*=\\\"/product/\\\"]'))"
          ".map(a=>a.href+' :: '+(a.textContent||'').trim().replace(/\\\\s+/g,' ')"
          ".slice(0,40)).join('\\\\n')")
    seen = {}
    for page in range(1, 6):
        out = safari_js(
            f"https://www.cardrush-pokemon.jp/product-list?"
            f"keyword={keyword}&num=100&page={page}", js)
        for line in out.split("\n"):
            m = re.search(r"product/(\d+) :: (.*?)\{(\d{3})/([A-Za-z0-9-]+)\}", line)
            if not m or "状態" in m.group(2):
                continue          # 状態違いは避ける
            seen.setdefault((m.group(4), int(m.group(3))), (int(m.group(1)),
                                                            m.group(2).strip()))
    for (sc, no), (pid, name) in sorted(seen.items()):
        print(f'    ("{sc}", {no}, {pid}),   # {name}')
    print(f"  計 {len(seen)}件")


def setup(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS cardrush (
      dex_key  TEXT PRIMARY KEY,
      product  INTEGER,
      set_code TEXT,
      card_no  INTEGER,
      url      TEXT,
      local    TEXT,
      status   TEXT
    );
    """)
    con.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--search", help="一覧を辿って番号→商品IDを集める（例 M-P）")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if a.search:
        search(a.search)
        return

    con = sqlite3.connect(DB, timeout=300)   # 他のスクリプトが書いていても待つ
    setup(con)
    js = ("document.title.replace(/\\\\s*-\\\\s*カードラッシュ.*/,'') + '|' + "
          "(document.querySelector('meta[property=\\\"og:image\\\"]')||{content:''})"
          ".content")
    n_hit = n_dl = 0
    for set_code, no, pid in WANT:
        rows = con.execute(
            """SELECT key, name FROM dex
               WHERE set_code = ? AND card_no = ?
                 AND img IS NULL AND img_off IS NULL AND img_web IS NULL""",
            (set_code, no)).fetchall()
        if len(rows) != 1:
            print(f"{set_code}-{no:03d} dex の行が {len(rows)}件（1件でないので採らない）")
            continue
        key, dex_name = rows[0]
        out = safari_js(f"https://www.cardrush-pokemon.jp/product/{pid}", js)
        title, _, url = out.partition("|")
        # 商品名の番号が狙いと一致するかを必ず確かめる（IDの取り違え防止）
        m = re.search(r"\{(\d{3})/" + re.escape(set_code) + r"\}", title)
        if not m or int(m.group(1)) != no:
            print(f"{set_code}-{no:03d} 商品名が一致しない: {title!r}")
            continue
        if not url.startswith("http"):
            print(f"{set_code}-{no:03d} 画像URLが取れない: {out!r}")
            continue
        n_hit += 1
        print(f"{set_code}-{no:03d} {dex_name} ← {title}")
        if a.dry_run:
            continue
        path = os.path.join(IMG_DIR, set_code, f"{key.replace('/', '_')}.jpg")
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:  # 画像は素通し
                raw = r.read()
            with open(path, "wb") as f:
                f.write(raw)
            time.sleep(WAIT)
        n_dl += 1
        con.execute("""INSERT OR REPLACE INTO cardrush
                       (dex_key,product,set_code,card_no,url,local,status)
                       VALUES (?,?,?,?,?,?,?)""",
                    (key, pid, set_code, no, url, path, "ok"))
        con.commit()

    print(f"\n照合 {n_hit}枚 / 取得 {n_dl}枚"
          + ("（--dry-run なので取得していない）" if a.dry_run else ""))
    print("このあと python build_dex.py で図鑑に反映する")


if __name__ == "__main__":
    main()
