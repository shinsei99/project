"""
DMMマイカの内部API（/api/ec/item）からカード情報と画像を取得する。

Web版の一覧ページ（HTMLをパースする crawl_myca.py）より、同じパックでも
多くのカードが返る。実測: 第1弾拡張パックが 43枚 → 70枚、ハナダシティジムが
5枚 → 9枚。ただし出品のあるカードだけで、出品ゼロのカードは返らない
（productCount が0の行は1件も無い）。アプリ版のような全カード網羅ではない。

■ エンドポイント（認証不要・実測で確定）
    GET /api/ec/genre                    ジャンル一覧（ポケモン = id:1）
    GET /api/ec/item?take=&skip=&...     カード検索。これが本命
    GET /api/ec/item/{id}/product        個別の出品情報

■ パラメータ（実測。名前を間違えると黙って0件が返るので注意）
    take                  1ページの件数。**これが無いと100件固定**
                          （limit / perPage / page / offset はすべて無効）
    skip                  送り位置
    myca_primary_pack_id  封入パックの絞り込み。Web版URLと同じ名前
    id                    カードIDの直指定（カンマ区切り）

■ 返ってくる項目
    id / cardname / cardnumber / rarity / expansion / full_image_url
    item_category_handle（CARD か BOX）/ productCount / myca_market_price

■ 画像
    full_image_url は https://static.mycalinks.io/... の直リンク（認証不要）。
    カード画像は .../app/item/image/card/<SET>/<SET>_<番号>.gif（180x251）。

⚠️ 公開サイトへのアクセスなので待ち時間を必ず入れる（既定1.5秒）。
   画像の著作権は ©Pokémon/Nintendo/Creatures/GAME FREAK に帰属する。
   取得物は手元での参照に限り、公開・配布しない。

使い方:
    python myca_api.py --one              # 1枚だけ取得して内容を確かめる
    python myca_api.py --pack 6621        # 1パック分の情報を表示（保存しない）
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import time
import urllib.parse
import urllib.request

BASE = "https://myca.dmm.com/api/ec/item"
OUT = "pokemon_cards"
SLEEP = 1.5                # サーバーへの間隔（秒）
RETRY = 3

UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/json",
}

_last = [0.0]


def _wait():
    w = SLEEP - (time.time() - _last[0])
    if w > 0:
        time.sleep(w)
    _last[0] = time.time()


def get(url: str, binary: bool = False):
    """待ち時間を入れて取得する。429/5xx は間隔を空けて数回だけやり直す。"""
    for attempt in range(RETRY):
        _wait()
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read()
            return body if binary else json.loads(body.decode("utf-8", "ignore"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < RETRY - 1:
                time.sleep(5 * (attempt + 1))
                continue
            raise
        except Exception:
            if attempt < RETRY - 1:
                time.sleep(3)
                continue
            raise


def search(**params):
    """/api/ec/item を叩く。take を省くと100件固定になる。"""
    q = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    return get(f"{BASE}?{q}")


def safe_name(s: str) -> str:
    """WindowsとmacOSの両方で使えるファイル名にする。"""
    s = re.sub(r'[\\/:*?"<>|]', "_", s or "")
    s = s.strip().strip(".")
    return (s or "noname")[:80]


def show(item: dict, saved: str | None = None):
    print(f"  カード名   : {item.get('cardname')}")
    print(f"  カードID   : {item.get('id')}")
    print(f"  カード番号  : {item.get('cardnumber')}")
    print(f"  レアリティ  : {item.get('rarity') or '（なし）'}")
    print(f"  収録        : {item.get('expansion')}")
    print(f"  種別        : {item.get('item_category_handle')}")
    print(f"  画像URL    : {item.get('full_image_url')}")
    if saved:
        print(f"  保存先      : {saved}")


def fetch_one(pack_id: str = "6621"):
    """1枚だけ取得して内容と画像を確かめる。"""
    d = search(take=20, myca_primary_pack_id=pack_id)
    cards = [i for i in d.get("items", [])
             if i.get("item_category_handle") == "CARD" and i.get("full_image_url")]
    if not cards:
        print("カードが取得できませんでした。")
        return
    print(f"このパックのAPI総件数: {d.get('totalCount')}（うちCARD {len(cards)}件を取得）\n")

    it = cards[0]
    os.makedirs(os.path.join(OUT, "images"), exist_ok=True)
    ext = os.path.splitext(urllib.parse.urlparse(it["full_image_url"]).path)[1] or ".gif"
    dst = os.path.join(OUT, "images", f"{it['id']}{ext}")
    raw = get(it["full_image_url"], binary=True)
    with open(dst, "wb") as f:
        f.write(raw)

    show(it, dst)
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(raw))
        print(f"  画像の実体  : {im.format} {im.size[0]}x{im.size[1]} / {len(raw)/1024:.0f}KB")
    except Exception:
        print(f"  画像の実体  : {len(raw)/1024:.0f}KB（Pillow未使用）")


def fetch_pack(pack_id: str):
    """1パック分を表示する（保存はしない）。"""
    d = search(take=200, myca_primary_pack_id=pack_id)
    items = d.get("items", [])
    cards = [i for i in items if i.get("item_category_handle") == "CARD"]
    print(f"pack_id={pack_id}  API総件数 {d.get('totalCount')} / 取得 {len(items)}件"
          f" / うちCARD {len(cards)}件")
    for i in cards[:12]:
        print(f"   {str(i.get('cardnumber')):<10} {str(i.get('rarity')):<5} "
              f"{(i.get('cardname') or '')[:20]:<22} 出品{i.get('productCount')}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--one", action="store_true", help="1枚だけ取得して検証")
    ap.add_argument("--pack", help="パックIDを指定して一覧表示")
    a = ap.parse_args()
    if a.pack:
        fetch_pack(a.pack)
    else:
        fetch_one()


if __name__ == "__main__":
    main()
