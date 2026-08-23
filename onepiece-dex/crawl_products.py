"""
公式の商品ラインナップを巡回して、**パッケージ画像・発売日・価格・商品分類**を取る。

カードリスト（`crawl_official.py`）は「シリーズ」しか持っておらず、
**商品パッケージの画像も発売日も入っていない**。ポケカ図鑑と同じように
「拡張パックの表紙を並べて、そこから収録カードへ入る」画面にするにはこれが要る。

  GET https://www.onepiece-cardgame.com/products/?subcategory=all&page=N   （1〜15）

1ページ12件。`<li class="linkListColBox" data-cat="boosters|decks|others">` の中に
商品ページURL・カテゴリ・商品名・発売日（`<time datetime="2026-10-01">`）・
希望小売価格・サムネイル（webp）が揃っている。

商品名の【OP-17】がカードリストのシリーズ記号と一致するので、そこで突き合わせる
（`build_dex.py` が `dex_series` に混ぜ込む）。

使い方:
    python crawl_products.py            # 全ページ＋パッケージ画像
    python crawl_products.py --no-image # 情報だけ
"""

from __future__ import annotations

import html
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "data", "cards.db")
IMG = os.path.join(HERE, "data", "product_img")
BASE = "https://www.onepiece-cardgame.com/products/"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}
WAIT = 0.7
MAX_PAGES = 40          # ページャは15ページだが、増えても取り切れるよう余裕を持たせる


def fetch(url: str) -> str:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def txt(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s)
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def schema(cx: sqlite3.Connection) -> None:
    cx.execute("BEGIN IMMEDIATE")
    for stmt in filter(None, (x.strip() for x in """
    CREATE TABLE IF NOT EXISTS products (
      url        TEXT PRIMARY KEY,   -- 商品ページのURL
      title      TEXT,               -- ブースターパック 世界最強の戦士【OP-17】
      code       TEXT,               -- OP-17（【】の中。シリーズと突き合わせる鍵）
      cat        TEXT,               -- boosters / decks / others
      cat_ja     TEXT,               -- ブースター / デッキ / その他
      tag        TEXT,               -- 「BASE SHOP限定」など。無ければNULL
      release    TEXT,               -- 2026-10-01（time の datetime）
      release_label TEXT,            -- 2026.09.04(金) / 2026.10 のような表記ゆれをそのまま
      price      TEXT,
      img_url    TEXT,
      img        TEXT,               -- 保存したローカルパス（data/product_img/…）
      fetched    REAL
    );
    CREATE INDEX IF NOT EXISTS idx_prod_code ON products(code);
    CREATE INDEX IF NOT EXISTS idx_prod_cat  ON products(cat)
    """.split(";"))):
        cx.execute(stmt)
    cx.commit()


def parse(page: str):
    for b in re.findall(r'<li class="linkListColBox".*?</li>', page, re.S):
        m = re.search(r'data-cat="([^"]*)"', b)
        cat = m.group(1) if m else None
        m = re.search(r'<a href="([^"]+)"', b)
        url = m.group(1) if m else None
        if not url:
            continue
        m = re.search(r'<h4 class="linkListColTitle">(.*?)</h4>', b, re.S)
        title = txt(m.group(1)) if m else None
        m = re.search(r'<span class="linkListColCat">(.*?)</span>', b, re.S)
        cat_ja = txt(m.group(1)) if m else None
        m = re.search(r'<span class="linkListColTag">(.*?)</span>', b, re.S)
        tag = txt(m.group(1)) if m else None
        m = re.search(r'<time[^>]*datetime="([^"]*)"[^>]*>(.*?)</time>', b, re.S)
        release, rlabel = (m.group(1), txt(m.group(2))) if m else (None, None)
        m = re.search(r'<span class="data">(.*?)</span>', b, re.S)
        price = txt(m.group(1)) if m else None
        m = re.search(r'<img[^>]*data-src="([^"?]+)', b)
        img_url = urllib.parse.urljoin(BASE, m.group(1)) if m else None
        code = (re.search(r"【(.+?)】", title or "") or [None, None])[1]
        yield dict(url=url, title=title, code=code, cat=cat, cat_ja=cat_ja, tag=tag,
                   release=release, release_label=rlabel, price=price, img_url=img_url)


def slug_of(url: str) -> str:
    """商品ページURL → ファイル名にする短い名前。

    **末尾スラッシュに注意。** `/products/boosters/op17/` を basename すると空になり、
    そういう商品が全部 `.webp` という同じ名前に潰れていた（2026-08-23に実際に発生。
    171件中152件しかファイルが残らなかった）。空でない最後の区切りを使う。
    """
    path = urllib.parse.urlparse(url).path.rstrip("/")
    return os.path.splitext(os.path.basename(path))[0] or "product"


def get_image(row) -> str | None:
    """パッケージ画像。**ファイル名は商品ページのスラッグ**（op17.html → op17.webp）。
    元のURLは日付とハッシュを含んでいて商品と結びつかないため。"""
    if not row["img_url"]:
        return None
    slug = slug_of(row["url"])
    ext = os.path.splitext(row["img_url"])[1] or ".webp"
    dest = os.path.join(IMG, slug + ext)
    rel = os.path.join("data", "product_img", slug + ext)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return rel
    try:
        with urllib.request.urlopen(
                urllib.request.Request(row["img_url"], headers=UA), timeout=45) as r:
            body = r.read()
    except Exception as e:
        print(f"  !! 画像 {slug}: {e}")
        return None
    if len(body) < 500:
        return None
    tmp = dest + ".part"
    with open(tmp, "wb") as f:
        f.write(body)
    os.replace(tmp, dest)
    time.sleep(0.1)
    return rel


def main() -> None:
    os.makedirs(IMG, exist_ok=True)
    cx = sqlite3.connect(DB, timeout=120)
    schema(cx)

    rows, seen = [], set()
    for p in range(1, MAX_PAGES + 1):
        page = fetch(f"{BASE}?subcategory=all&page={p}")
        # 同じページの中にも重複が出る（1商品が2枠に載ることがある）。
        # 1件ずつ seen に入れないと取りこぼす（171件拾って実数は156件だった）
        got = []
        for r in parse(page):
            if r["url"] in seen:
                continue
            seen.add(r["url"])
            got.append(r)
        if not got:
            print(f"  page {p}: 0件 → ここで終わり")
            break
        rows += got
        print(f"  page {p}: {len(got)}件", flush=True)
        time.sleep(WAIT)

    cols = ("url title code cat cat_ja tag release release_label price img_url").split()
    cx.execute("BEGIN IMMEDIATE")
    for r in rows:
        cx.execute(
            "INSERT INTO products (%s, fetched) VALUES (%s) "
            "ON CONFLICT(url) DO UPDATE SET %s, fetched=excluded.fetched"
            % (",".join(cols), ",".join("?" * (len(cols) + 1)),
               ",".join(f"{c}=excluded.{c}" for c in cols if c != "url")),
            [r[c] for c in cols] + [time.time()])
    cx.commit()
    print(f"\n商品 {len(rows)}件（重複を除いた実数）")
    for cat, n in cx.execute("SELECT cat_ja, COUNT(*) FROM products GROUP BY 1 "
                             "ORDER BY 2 DESC"):
        print(f"  {cat or '（分類なし）'}  {n}件")
    n_code = cx.execute("SELECT COUNT(*) FROM products WHERE code IS NOT NULL").fetchone()[0]
    print(f"  うち記号【】つき {n_code}件（シリーズと突き合わせられるもの）")

    if "--no-image" not in sys.argv:
        ok = 0
        cx.execute("BEGIN IMMEDIATE")
        for r in rows:
            rel = get_image(r)
            if rel:
                ok += 1
                cx.execute("UPDATE products SET img=? WHERE url=?", (rel, r["url"]))
        cx.commit()
        print(f"パッケージ画像 {ok}/{len(rows)}件")


if __name__ == "__main__":
    main()
