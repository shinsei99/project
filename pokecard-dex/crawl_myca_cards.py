"""
DMMマイカの「カード単体ページ」を辿って、**出品の有無に関係なく**全カードを取る。

これまでの2経路はどちらも販売中のカードしか返さなかった。

    Web版の一覧HTML（crawl_myca.py）      ハナダシティジム カスミ =  5枚
    内部API /api/ec/item（myca_api.py）   同                     =  9枚
    カード単体ページ（このスクリプト）        同                     = 全枚数

    /pokemon-trading-card-game/items/single-card/<ID>

出品ゼロのカード（id=5420 カスミのニョロモLV.15）も HTTP 200 で開き、
ページには「現在、購入可能な商品はありません」と出る。在庫と無関係に存在する。

■ ID の規則（実測）
    ・**5刻み**。1刻みで叩くと 199116〜199119 は404、199115/199120/199125 は200
      古い帯は10刻みで並ぶが（5411〜5415は404）、5刻みで走らせれば両方拾える
    ・パックごとに固まっている（ハナダシティジム カスミ = 5410〜5650、
      冷酷の反逆者 = 199115〜199230）
    ・IDは発売順（sm9b=236290 / sv4a=338510 / M2a=364060 / M6=372580）
    ・最新のストームエメラルダが 372580 なので上限は 373000 前後

■ ページから取れるもの
    <title> に全部入っている。
        新: アメモース （ストームエメラルダ / M6 003/076 C）のシングルカード販売|…
        旧: カスミのニョロモLV.15 （ポケモンジム第1弾 ハナダシティジム カスミ）の…
    画像は og:image が直リンク（https://static.mycalinks.io/…/card/<SET>/<FILE>.jpg）

⚠️ 公開サイトへのアクセスなので1秒に1件までに抑える。
   カード画像・データの著作権は ©Pokémon/Nintendo/Creatures/GAME FREAK に帰属する。
   取得物は手元での参照に限り、公開・配布しない（data/ は gitignore）。

使い方:
    python crawl_myca_cards.py --one 5420        # 1枚だけ試す
    python crawl_myca_cards.py --range 5400 5600 # 範囲を指定して取る
    python crawl_myca_cards.py                   # 全件（10刻みで1〜373000）
    python crawl_myca_cards.py --images          # 取得済みカードの画像を落とす
"""

from __future__ import annotations

import argparse
import html as html_mod
import os
import re
import sqlite3
import time
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "https://myca.dmm.com/pokemon-trading-card-game/items/single-card"
DB = "data/cards.db"
IMG_DIR = "data/myca_images"

SLEEP = 0.5            # サーバーへの間隔（秒）＝ 2件/秒
WORKERS = 3            # 1ページ471KBあり待ち時間が長いので、間隔を守りつつ重ねる
# IDの刻みは時代で変わる。実測（末尾5のIDが生きているかを5点ずつ確認）:
#   ID  4万・8万付近 … 0/5件  → 10刻み
#   ID 12万・14万付近 … 3/5件  → 5刻みが始まっている
#   ID 15万・18万付近 … 5/5件  → 完全に5刻み
#
# 全部を5刻みで辿ると古い側が空振りだらけになり（10万未満は3,251回訪問して
# 40件しか取れず1.2%）、逆に全部10刻みだと新しい側を半分落とす
# （冷酷の反逆者が59枚のうち29枚しか取れなかった）。そこで境界で切り替える。
#
# 境界の正確な位置は判らないので、**手前から5刻みに入る**（安全側）。
# 8万〜12万の間で切り替わるため、余裕を見て8万から5刻みにする。
STEP_BOUNDARY = 80000
STEP_OLD = 10          # 境界より前（10刻みで足りる時代）
STEP_NEW = 5           # 境界以降（5刻みが必要な時代）
ID_MAX = 373000        # 最新カードの少し先まで
RETRY = 3

UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept-Language": "ja,en;q=0.8",
}

TITLE = re.compile(r"<title>([^<]*)</title>")
OGIMG = re.compile(r'property="og:image"\s+content="([^"]+)"')
# ページに埋め込まれたJSONの release_date。公式サイトに商品ページが無い
# 古いパックでもここから発売日が判る（ポケモンジム第1弾 ハナダシティジム
# カスミ = 1998-04-26）。表示上の「発売日」欄も同じ値。
RELEASE = re.compile(r'release_date\\?"?:\\?"?(\d{4}-\d{2}-\d{2})')
# 「カスミのニョロモLV.15 （ポケモンジム第1弾 ハナダシティジム カスミ）のシングルカード販売」
# 「アメモース （ストームエメラルダ / M6 003/076 C）のシングルカード販売」
# カード名そのものに括弧が入ることがある。
#   博士の研究（ナナカマド博士） （スターバース / s9 095/100 R）
# 最短一致にすると最初の「）」を終端と誤認し、パック名が
# 「ナナカマド博士） （スターバース」になってしまう（実測127枚が該当）。
# **最後の（…）**をパック情報として取る。
T_PAT = re.compile(r"^(.+)（([^（）]+)）のシングルカード販売")
# パック名の中に括弧が入ることもある。
#   マリィ （エクストラバトルの日 2022版（2回目）参加賞 / S-P 340/S-P PROMO）
# 括弧の入れ子を数えられないので、「カード名 （…）」の区切りは
# **半角空白＋全角開き括弧**で切る。カード名側の括弧（博士の研究（ナナカマド博士））
# には空白が入らないため、これで両方を正しく分けられる。
T_SPACE = re.compile(r"^(.+?)\s+（(.+)）のシングルカード販売")
# 「ストームエメラルダ / M6 003/076 C」→ パック名 / セット 番号 レアリティ
INNER = re.compile(r"^(.*?)\s*/\s*([A-Za-z0-9+-]+)\s+(\d{1,3})/(\d{1,3})(?:\s+(\S+))?$")
# 「ポケモンカードゲームADV 第3弾拡張パック 天空の覇者 / ☆」＝ パック名 / レアリティ。
# ADV期など番号が印字されていない時代はこの形。記号（● ◆ ★ ☆ ◇ ○ e キラ
# ミラー）と英字レアリティ（PROMO など）の両方が来る
# 「… / ☆」「… / ノーマル」＝ レアリティ・仕様だけ。記号と日本語の両方が来る
SYM_ONLY = re.compile(
    r"^(.*?)\s*/\s*([●◆★☆◇○eキラミラーA-Z]{1,8}|ノーマル|キラ|ミラー|"
    r"マスターボールミラー|モンスターボールミラー)$")
# 「アルセウス光臨 / Pt4 -」＝ パック名 / セット記号（番号もレアリティも無い）。
# 基本エネルギーなど番号が振られていないカードがこの形になる。放置すると
# パック名が「アルセウス光臨 / Pt4 -」のまま残り、公式商品と照合できず
# 「収録カード0枚」に見える（実測199件）。
SET_ONLY = re.compile(r"^(.*?)\s*/\s*([A-Za-z0-9+-]{1,10})\s*-+\s*-*$")
# 「25th ANNIVERSARY COLLECTION / s8a WAT」＝ パック名 / セット記号 エネルギー種別。
# 基本エネルギーは番号の代わりに種別（WAT FIR GRA LIG PSY FIG DAR MET）が入る。
# 「2016スタートダッシュキャンペーン / XY-P 210/XY-P PROMO」
#   ＝ パック名 / セット記号 番号/セット記号 レアリティ
# プロモは分母が数字ではなくセット記号になる。既存の番号パターン
# （数字/数字）に合わないため、専用に受ける。実測2,600種以上が該当した。
PROMO_NO = re.compile(
    r"^(.*?)\s*/\s*([A-Za-z0-9+-]{1,10})\s+(\d{1,3})/([A-Za-z0-9+-]{1,10})"
    r"(?:\s+(\S+))?$")
# 番号すら無いプロモ（「/ XY-P XY-P PROMO」）
PROMO_BARE = re.compile(
    r"^(.*?)\s*/\s*([A-Za-z0-9+-]{1,10})\s+([A-Za-z0-9+-]{1,10})\s+(\S+)$")
# 末尾にレアリティが付く場合もある（「/ s8b WAT ミラー」）
# エネルギー種別や版の識別子は種類が多い（WAT FIR GRA LIG PSY FIG DAR MET
# COL FAI DRA THU …）。列挙し切れないので「セット記号＋英大文字の短い語」で受ける。
# 「/ PW PW」のようにセット記号が繰り返される形もここに入る。
SET_ENERGY = re.compile(
    r"^(.*?)\s*/\s*([A-Za-z0-9+-]{1,10})\s+([A-Z]{2,5}|[A-Za-z0-9+-]{1,10})"
    r"(?:\s+(\S+))?$")
# 「エントリーパック / DP1 DPBP#448」＝ パック名 / セット記号 管理番号。
# DP期（2006〜2008年）はカード番号の代わりに DPBP# の通し番号が入り、
# 末尾にレアリティ記号が付くこともある。実測766枚が該当し、放置すると
# パック名が「秘境の叫び / DP5 DPBP#180 ★」のまま残って商品と照合できない。
SET_DPBP = re.compile(
    r"^(.*?)\s*/\s*([A-Za-z0-9+-]{1,10})\s+DPBP#(\d+)"
    r"(?:\s+([●◆★☆◇○eキラミラーA-Z-]{1,8}))?$")

_last = [0.0]
_lock = threading.Lock()


def get(url: str, binary: bool = False):
    """全スレッド合わせて SLEEP 間隔を超えないように取得する。404 は None（欠番）。"""
    for attempt in range(RETRY):
        with _lock:
            w = SLEEP - (time.time() - _last[0])
            if w > 0:
                time.sleep(w)
            _last[0] = time.time()
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read()
            return body if binary else body.decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (429, 500, 502, 503) and attempt < RETRY - 1:
                time.sleep(10 * (attempt + 1))
                continue
            return None
        except Exception:
            if attempt < RETRY - 1:
                time.sleep(3)
                continue
            return None
    return None


def parse(html: str):
    """タイトルと og:image から必要な項目を取り出す。"""
    t = TITLE.search(html)
    if not t:
        return None
    # &amp; &gt; などのHTMLエスケープを戻す。放置すると
    # 「スターターセットexクワッス&amp;ミミッキュex」というパック名になり、
    # 公式商品「スターターセットex クワッス&ミミッキュex」と照合できない。
    title = html_mod.unescape(t.group(1)).strip()
    # まず「カード名 （パック情報）」で切る。パック情報に「/」が含まれるか、
    # 括弧が入れ子になっている場合はこちらが正しい
    # 「カード名 （パック情報）」を空白で切るのが基本。ただしカード名にも
    # 括弧が入るので（マキシマムベルト（ACE SPEC）、プリン（光沢あり））、
    # 空白で切った結果が「パック情報らしいか」を見て選ぶ。
    # パック情報らしさ = 「/」を含む、または括弧を含まない。
    m = T_SPACE.match(title)
    if m:
        inner = m.group(2)
        looks_pack = ("/" in inner) or ("（" not in inner and "）" not in inner)
        if not looks_pack:
            m = T_PAT.match(title)
    else:
        m = T_PAT.match(title)
    if not m:
        return None
    name, inner = m.group(1).strip(), m.group(2).strip()

    pack, set_code, no, total, rarity = inner, None, None, None, None
    im = INNER.match(inner)
    if im:
        pack = im.group(1).strip()
        set_code = im.group(2)
        no, total = int(im.group(3)), int(im.group(4))
        rarity = (im.group(5) or "").replace("仕様", "").strip() or None
    else:
        # ADV期など番号が印字されていない時代は「パック名 / レアリティ」だけ。
        #   ベトベトンex （ポケモンカードゲームADV 第3弾拡張パック 天空の覇者 / ☆）
        # 判定順が大事。SET_ENERGY は「セット記号＋短い語」を広く受けるので、
        # プロモ（「/ M-P 042/M-P」）やDP期（「/ DP5 DPBP#180」）より後に見る。
        sm = SYM_ONLY.match(inner)
        dp = SET_DPBP.match(inner)
        pr = PROMO_NO.match(inner) or PROMO_BARE.match(inner)
        so = SET_ONLY.match(inner) or SET_ENERGY.match(inner)
        if pr:
            # プロモ。番号があれば取り、レアリティは末尾（PROMO 等）
            pack = pr.group(1).strip()
            set_code = pr.group(2)
            g3 = pr.group(3)
            if g3 and g3.isdigit():
                no = int(g3)
            # 末尾のグループはレアリティ。ただし分母のセット記号と同じ文字列
            # （「042/M-P」の M-P）はレアリティではないので捨てる
            r = ""
            if pr.lastindex and pr.lastindex >= 5:
                r = (pr.group(5) or "").strip()
            elif pr.lastindex and pr.lastindex >= 4:
                g4 = (pr.group(4) or "").strip()
                r = g4 if g4 not in (set_code, pr.group(3)) else ""
            rarity = (r.replace("仕様", "") or None) if r and r != "-" else None
        elif dp:
            # DP期。DPBP# は印刷された番号ではないので card_no には入れない
            pack = dp.group(1).strip()
            set_code = dp.group(2)
            r4 = (dp.group(4) or "").strip()
            rarity = r4 if r4 and r4 != "-" else None
        elif so:
            # セット記号だけ、またはセット記号＋エネルギー種別。
            # 「/ s8b WAT ミラー」のようにレアリティが続くこともある
            pack = so.group(1).strip()
            set_code = so.group(2)
            if so.lastindex and so.lastindex >= 4:
                r4 = (so.group(4) or "").strip()
                rarity = r4.replace("仕様", "") or None if r4 != "-" else None
        elif sm:
            pack = sm.group(1).strip()
            rarity = sm.group(2).strip()

    img_set = img_file = None
    o = OGIMG.search(html)
    if o:
        # マイカに画像が無いカードは noimage.jpg が入る。これを画像として
        # 扱うと全カードが同じ「画像なし」の絵になってしまう
        if "noimage" in o.group(1):
            o = None
        else:
            mm = re.search(r"/card/([A-Za-z0-9_-]+)/([A-Za-z0-9_-]+)\.(?:gif|jpg|png)",
                           o.group(1))
            if mm:
                img_set, img_file = mm.group(1), mm.group(2)

    # パック名の末尾に「/ ●」のようにレアリティが付いてくることがある。
    # そのまま持つと同じパックが「第1弾拡張パック」「第1弾拡張パック / ●」…と
    # 4行に割れ、収録枚数の集計が壊れる（金、銀、新世界へ… が 34+25+24+13 に
    # 分裂していた。合算すると96枚でTCGdexと一致する）。
    pack = re.sub(r"\s*/\s*[●◆★☆◇○eキラミラーA-Z]{1,8}\s*$", "", pack).strip()

    rel = RELEASE.search(html)
    return {"name": name, "pack_name": pack, "set_code": set_code or img_set,
            "card_no": no, "total": total, "rarity": rarity,
            "img_set": img_set, "img_file": img_file,
            "img_url": o.group(1) if o else None,
            "release": rel.group(1) if rel else None}


def setup(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS myca_card (
      card_id   INTEGER PRIMARY KEY,   -- single-card ページのID（10刻み）
      name      TEXT,
      set_code  TEXT,
      card_no   INTEGER,
      total     INTEGER,
      rarity    TEXT,
      pack_name TEXT,
      img_set   TEXT,
      img_file  TEXT,
      img_url   TEXT,
      status    TEXT,                  -- ok / gone / unparsed
      fetched   REAL,
      release   TEXT                   -- ページの「発売日」欄。公式に商品ページが
                                       -- 無い古いパックでもここから判る
    );
    CREATE INDEX IF NOT EXISTS idx_mc_set  ON myca_card(set_code);
    CREATE INDEX IF NOT EXISTS idx_mc_pack ON myca_card(pack_name);
    CREATE INDEX IF NOT EXISTS idx_mc_name ON myca_card(name);
    """)
    # 後から足した列（既存のDBにも入れる）
    cols = {r[1] for r in con.execute("PRAGMA table_info(myca_card)")}
    if "release" not in cols:
        con.execute("ALTER TABLE myca_card ADD COLUMN release TEXT")
    con.commit()


def write(con, sql, data):
    """他のスクリプトと同じDBを触るのでロック待ちで諦めない。"""
    for a in range(20):
        try:
            con.executemany(sql, data) if isinstance(data, list) else con.execute(sql, data)
            con.commit()
            return
        except sqlite3.OperationalError as e:
            if "locked" not in str(e) or a == 19:
                raise
            time.sleep(3)


def fetch_one(cid: int):
    """戻り値の status は3値。

      ok        … 取れた
      gone      … 404（そのIDにカードが無い）
      unparsed  … ページはあるのにタイトルを読めなかった

    unparsed を gone と混ぜてはいけない。混ぜると「知らない表記の時代」を
    丸ごと落としても欠番に見えて気づけない。実際 ADV期の
    「ベトベトンex （…天空の覇者 / ☆）」という形（番号なし・レアリティのみ）に
    最初は対応しておらず、たまたま目視で気づいた。
    """
    html = get(f"{BASE}/{cid}")
    if html is None:
        return (cid, None, None, None, None, None, None, None, None, None,
                "gone", time.time(), None)
    d = parse(html)
    if not d:
        t = TITLE.search(html)
        title = (t.group(1)[:120] if t else None)
        return (cid, title, None, None, None, None, None, None, None, None,
                "unparsed", time.time(), None)
    return (cid, d["name"], d["set_code"], d["card_no"], d["total"], d["rarity"],
            d["pack_name"], d["img_set"], d["img_file"], d["img_url"],
            "ok", time.time(), d["release"])


def show(row):
    (cid, name, set_code, no, total, rarity, pack, img_set, img_file, url,
     st, _, rel) = row
    print(f"  カードID   : {cid}")
    print(f"  カード名   : {name}")
    print(f"  カード番号  : {f'{no:03d}/{total:03d}' if no else '（番号なし）'}")
    print(f"  レアリティ  : {rarity or '（なし）'}")
    print(f"  セット      : {set_code}")
    print(f"  収録パック  : {pack}")
    print(f"  発売日      : {rel or '（不明）'}")
    print(f"  画像URL    : {url}")
    print(f"  保存ファイル名: {img_set}/{img_file}.jpg" if img_file else "  画像なし")


def crawl(con, lo: int, hi: int):
    done = {r[0] for r in con.execute("SELECT card_id FROM myca_card")}
    ids = list(range(lo, min(hi, STEP_BOUNDARY - 1) + 1, STEP_OLD))
    if hi >= STEP_BOUNDARY:
        ids += list(range(max(lo, STEP_BOUNDARY), hi + 1, STEP_NEW))
    todo = [i for i in ids if i not in done]
    print(f"対象 {len(todo):,}件（ID {lo:,}〜{hi:,}／"
          f"{STEP_BOUNDARY:,}未満は{STEP_OLD}刻み・以降は{STEP_NEW}刻み・"
          f"{1/SLEEP:.0f}件/秒で約{len(todo)*SLEEP/3600:.1f}時間）", flush=True)
    if not todo:
        print("すべて取得済みです。")
        return

    t0, ok, gone, bad, buf = time.time(), 0, 0, 0, []
    ex = ThreadPoolExecutor(max_workers=WORKERS)
    for n, row in enumerate(ex.map(fetch_one, todo), 1):
        buf.append(row)
        ok += row[10] == "ok"
        gone += row[10] == "gone"
        bad += row[10] == "unparsed"
        if len(buf) >= 25:
            write(con, "INSERT OR REPLACE INTO myca_card VALUES (" + ",".join("?" * 13) + ")",
                  buf)
            buf = []
            el = time.time() - t0
            print(f"\r  {n:,}/{len(todo):,}  カード{ok:,} 欠番{gone:,}"
                  f"{' 未対応' + format(bad, ',') if bad else ''}  "
                  f"{el/3600:.1f}h経過 / 残り約{(len(todo)-n)/(n/el)/3600:.1f}h   ",
                  end="", flush=True)
    ex.shutdown()
    if buf:
        write(con, "INSERT OR REPLACE INTO myca_card VALUES (" + ",".join("?" * 13) + ")", buf)
    print(f"\n完了: カード{ok:,} / 欠番{gone:,} / 未対応の表記{bad:,} "
          f"/ {(time.time()-t0)/3600:.1f}時間", flush=True)
    if bad:
        print("⚠️ 未対応の表記があります。次で中身を確認してください:")
        print("   sqlite3 data/cards.db \"SELECT card_id, name FROM myca_card "
              "WHERE status='unparsed' LIMIT 20\"")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--one", type=int, help="1枚だけ試す（IDを指定）")
    ap.add_argument("--range", nargs=2, type=int, metavar=("LO", "HI"))
    a = ap.parse_args()

    con = sqlite3.connect(DB, timeout=300)
    con.execute("PRAGMA busy_timeout = 300000")
    setup(con)

    if a.one:
        row = fetch_one(a.one)
        if row[10] != "ok":
            print(f"id={a.one} は取得できませんでした（欠番）")
            return
        show(row)
        write(con, "INSERT OR REPLACE INTO myca_card VALUES (" + ",".join("?" * 13) + ")",
              [row])
        return

    lo, hi = (a.range if a.range else (10, ID_MAX))
    crawl(con, lo, hi)
    con.close()


if __name__ == "__main__":
    main()
