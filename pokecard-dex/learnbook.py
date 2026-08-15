"""
learn-book.com のカードリストから、公式・マイカ・TCGdex のどこにも画像が無い
年代（eシリーズ・PCG期・1996年の第1弾）のカード画像を補う。

なぜ第三者サイトを使うのか:
  この年代は**公開元が存在しない**ことを確認済み。TCGdex は該当カードの
  `image` が null、公式サイト（pokemon-card.com）はカードIDを 1〜52,000 まで
  全巡回しても収録が無い（実在最大ID 50,484）。→ README「到達点」参照。

照合の考え方（誤って別のカードの絵を出さないための決まり）:
  ページの各画像には alt にカード名が入っている（例 alt="ミュウ"）。
  ファイル名にも番号が入る（e1087.jpg = E1の087番）。

  **まず名前で照合する。** そのセットの dex 側にもページ側にもその名前が
  1枚しか無く、まだ画像が無い行だけを採る。

  **番号は、そのセットで信用できると確かめてからでないと使わない。**
  eシリーズと PCG4 は dex 側のカード名が壊れている（TCGdex の日本語データが
  英語や誤訳のまま入っている。E1の1番は "Koffing"、5番は "奇妙な"＝Oddish）
  ため、名前照合はほとんど当たらない。そこで、

    名前で照合できた組のうち、両方に番号があるものを取り出し、
    **3組以上あって、かつ1組も食い違わない**なら、そのセットは番号が
    信用できると判断して、残りも番号で照合する。

  実測: E1 は 5/5、E3 は 7/7 で一致したため番号を採用。PMCG1（1996年の
  第1弾拡張パック）は名前が正しく65組当たるが番号は割り当てが違うため、
  この判定で自動的に名前照合だけになる。ソースごとに番号の体系が違う例は
  他にもある（M-P はマイカ72番=ジェット／TCGdex72番=ジーランス）。

⚠️ 個人ブログなので取得は1秒1件に抑える。画像の著作権は
   ©Pokémon/Nintendo/Creatures/GAME FREAK に帰属し、取得物は手元での参照に
   限る（data/ は gitignore・公開配布しない）。

使い方:
    python learnbook.py --dry-run     # 何枚照合できるか数えるだけ（取得しない）
    python learnbook.py               # 照合できたものを取得して DB に記録
    python learnbook.py --pages e01,pcg4
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
import time
from collections import Counter

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_dex import nname                     # 表記ゆれを潰す（同じ規則を使う）

DB = "data/cards.db"
IMG_DIR = "data/learnbook"
BASE = "https://learn-book.com/pokemon-cardlist-{slug}/"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
WAIT = 1.0                                      # ページ・画像とも1秒に1件

# learn-book のページ ↔ dex のセット記号。
# セット記号を持たない1996年のスターターパックだけ pack_name で対応づける。
# 画像が1枚も無いセットだけを相手にする。同じ PCG 期でも PCG-1〜PCG-37
# （マイカ由来の記号）は既に画像が揃っているので触らない。
PAGES = [
    ("e01", "E1", None), ("e02", "E2", None), ("e03", "E3", None),
    ("e04", "E4", None), ("e05", "E5", None),
    ("pcg4", "PCG4", None),          # 金の空、銀の海
    ("pcg9", "PCG9", None),          # さいはての攻防
    ("pmcg01", "PMCG1", None),       # 1996年 第1弾拡張パック
    # 1996年の第1弾は「スターターパック」と「拡張パック」で102枚の同じ札を
    # 分け合っており、learn-book も2ページで同じ画像を使い回している。
    # そのため両方のページを両方のグループに当てる（重複は取得時に飛ばす）
    ("pmcg01-deck", None, "第1弾スターターパック"),
    ("pmcg01", None, "第1弾スターターパック"),
    # 1999年「ポケモンカード★neo スターターパック」（全102種）。dex 側は
    # set_code を持たず pack_name="スターターパック" の96行。カード名は
    # 正しい日本語で入っており、96行に同名は無い（番号は NULL なので名前照合のみ）
    ("neo01-deck", None, "スターターパック"),

    # --- デッキ商品に同梱されたエネルギー（2026-08-14追加） -----------------
    # マイカはデッキ商品の**エネルギーだけ**画像も番号も持っていない（同じ商品の
    # ポケモン・トレーナーには画像がある）。dex 側では set_code が NULL の行になる。
    #
    # **スラッグの番号はマイカの PCG-n / ADV-n と対応しない。** 実例:
    # `pcg07-deck` は「ロケット団ハーフデッキW -silver-」で、マイカ PCG-7 の
    # レックウザデッキ（= `pcg05-deck`）ではない。**必ずページの title
    # （【全N種類まとめ】<商品名>の内容と…）を読んで商品名で対応づけること。**
    #
    # ⚠️ learn-book はエネルギーの画像を商品をまたいで使い回している
    # （`pcg02-deck` の中でも `pcgs07en1` と `pcgs08en2` が混在）。つまり得られるのは
    # **シリーズ共通の絵**であって「その商品に入っていた実物の刷り」ではない。
    # 図鑑の用途として許容する判断（2026-08-14）。出所は `img_web` で分かる。
    ("pmcg01-deck", None, "第1弾スターターパック / -"),        # 基本エネ6
    ("pmcg02-deck", None, "ポケモンジム第1弾 ニビシティジム タケシ"),
    ("pmcg03-deck", None, "ポケモンジム第1弾 ハナダシティジム カスミ"),
    ("pmcg04-deck", None, "ポケモンジム第2弾 クチバシティジム マチス"),
    ("pmcg05-deck", None, "ポケモンジム第2弾 タマムシシティジム エリカ"),
    ("pmcg06-deck", None, "ポケモンジム第3弾 ヤマブキシティジム ナツメ"),
    ("pmcg07-deck", None, "ポケモンジム第3弾 グレンタウンジム カツラ"),
    # ★neo スターターパックは全102種＝96枚（pack_name "スターターパック"）＋
    # 基本エネルギー6枚（同 "スターターパック / -"）。**マイカ自身が2つの名前で
    # 出している**ので、同じページを2つのグループに当てる
    ("neo01-deck", None, "スターターパック / -"),
    ("adv04-deck", None, "構築済みスターター フライゴンデッキ"),
    ("adv05-deck", None, "構築済みスターター ボーマンダデッキ"),
    ("adv08-deck", None, "構築済みスターター メタグロスデッキ"),
    ("pcg01-deck", None, "ランダム構築スターター フシギバナ★草"),
    ("pcg02-deck", None, "ランダム構築スターター リザードン★炎"),
    ("pcg03-deck", None, "ランダム構築スターター カメックス★水"),
    ("pcg04-deck", None, "構築済みスターター デオキシスデッキ"),
    ("pcg05-deck", None, "構築済みスターター レックウザデッキ"),
    ("pcg08-deck", None, "構築済みスターター メガニウムex★草"),
    ("pcg09-deck", None, "構築済みスターター バクフーンex★炎"),
    ("pcg10-deck", None, "構築済みスターター オーダイルex★水"),
    ("pcg11-deck", None, "構築済みスターター まぼろしのミュウ"),
    ("pcg14-deck", None, "構築済みデッキ 封印! サーナイトex"),   # ページ側は全角「！」
    ("pcg15-deck", None, "構築済みデッキ 雷震! バンギラスex"),   # 同上

    # --- learn-book にページが無い商品（同じシリーズの絵を借りる） -------------
    # 上と違い、**その商品のページが learn-book に無い**もの。エネルギーの絵は
    # シリーズ単位で共通なので、同時期の別商品のページから借りる。
    # 借り先は発売日で決めた（`myca_card.release`）。対象グループは set_code が
    # NULL の行＝**エネルギーだけ**なので、借り先ページのポケモン・トレーナーが
    # 誤って当たることはない（実際に全行を確認した）。
    #
    #   1998-12-04 クイックスターターギフト        → 初期シリーズ（pmcg01-deck）
    #   2002-07-13 劇場限定VSパック                → VSシリーズ（vs01〜03-deck）
    #   2003-07-19 映画公開記念VSパック（ADV-9）    → ADVシリーズ ※名前はVSだがADV期
    #   2003-11-28 ADV ギフトボックス              → ADVシリーズ（adv01〜03-deck）
    #   2004-07-17 裂空のデオキシス（PCG-8）        → PCGシリーズ
    #   2005-07-16 波導のルカリオ（PCG-27）         → PCGシリーズ
    #   2006-07-15 蒼海のマナフィ（moviemana）      → PCGシリーズ
    ("pmcg01-deck", None, "クイックスターターギフト"),
    ("vs01-deck", None, "劇場限定VSパック"),
    ("vs02-deck", None, "劇場限定VSパック"),
    ("vs03-deck", None, "劇場限定VSパック"),
    ("adv01-deck", None, "映画公開記念VSパック"),
    ("adv02-deck", None, "映画公開記念VSパック"),
    ("adv03-deck", None, "映画公開記念VSパック"),
    ("adv01-deck", None, "ポケモンカードゲームADV ギフトボックス"),
    ("adv02-deck", None, "ポケモンカードゲームADV ギフトボックス"),
    ("adv03-deck", None, "ポケモンカードゲームADV ギフトボックス"),
    ("pcg01-deck", None, "映画公開記念VSパック 裂空のデオキシス"),  # 基本エネ
    ("pcg04-deck", None, "映画公開記念VSパック 裂空のデオキシス"),  # マルチエネルギー
    ("pcg01-deck", None, "映画公開記念VSパック 波導のルカリオ"),
    ("pcg01-deck", None, "映画公開記念VSパック 蒼海のマナフィ"),
]

# 自動判定では番号を採用できないが、**目視で番号の一致を確認したセット**。
#
# PCG9（さいはての攻防）は dex 側の名前が英語・誤訳で、自動判定では
# 「食い違い53件」となって弾かれる。しかし中身を並べると全て同じポケモンで、
# 番号は完全に一致していた（左が dex／右が learn-book）。
#
#   #1 Snorlax=カビゴン ／ #2 ドラチーニ=ミニリュウ ／ #3 ドラゴンエア=ハクリュー
#   #4 ドラゴナイトex=カイリュー ／ #5 ウーパー=ウパー ／ #6 quagsire=ヌオー
#   #7 エカン=アーボ ／ #10 テイロウ=スバメ
#
# 英語名と日本語名の対応表を持っていないので、この判断は自動化できない。
# **セットを足すときは必ず同じ確認をしてからここに書くこと。**
VERIFIED_NUMBERING = {"PCG9"}

# ページの alt が dex のカード名と綴りだけ違うもの。**同じカードだと確認できた
# ものだけ**をここに書く（ページ側の表記 → dex の表記）。
#
# neo01-deck（1999年 ★neo スターターパック）は、ファイル名 neo1001〜neo1096 が
# dex の96行と **1対1・同じ並びで対応する**ことを確認済み（93行は名前も完全一致し、
# 残り3行が下記。位置がずれている組は1つも無い）。
#   ・「新ポケモン図鑑」= dex「新ポケモン図鑑HANDY808」… ページ側が略記
#   ・「悪／鋼エネルギー（初期シリーズ）」… ページ側が付けた注記。
#     基本エネルギー6枚（草炎水雷超闘）も同じ注記つきで載るが、そちらは
#     ファイル名が 1st1s001〜006 ＝ neo ではなく第1弾の絵で、dex の96行にも
#     含まれない。注記だけを一律に落とすと**この6枚を巻き込む**ので、
#     alt 全体の一致でしか置き換えない。
ALIAS = {
    "neo01-deck": {
        "新ポケモン図鑑": "新ポケモン図鑑HANDY808",
    },
}

# エネルギーの表記ゆれ。ページは「炎エネルギー（PCGシリーズ）」、dex は
# 「基本炎エネルギー」のように、**注記と 基本/特殊 の接頭辞だけが違う**。
# 商品ごとに ALIAS を書くと同じ行が何十個も並ぶので、規則で寄せる。
#
# 安全のため、**そのグループの dex に実在する名前にしか書き換えない**
# （`energy_alias()`）。寄せた結果そのグループで同名が2つになる場合は
# `match()` の重複チェックが弾く。
#
# neo01-deck の基本エネルギー6枚がこの規則で誤って当たらないのは、
# 96枚のグループ側に「基本草エネルギー」等の行が無いから。
# 6枚は別のグループ（"スターターパック / -"）に入っていて、そちらで当たる。
ENERGY_ANNOT = re.compile(r"（[^（）]*）\s*$")     # 末尾の（PCGシリーズ）など


def energy_key(name: str) -> str:
    """「基本炎エネルギー」も「炎エネルギー（PCGシリーズ）」も同じ鍵にする。"""
    n = ENERGY_ANNOT.sub("", name).strip()
    n = re.sub(r"^(基本|特殊)", "", n)
    return nname(n)


def energy_alias(rows, items):
    """ページ側のエネルギー名を、そのグループの dex に実在する名前へ寄せる。

    rows は match() が見るのと同じ dex の行。書き換え先が一意に決まるものだけ。
    """
    cand = Counter(energy_key(nm) for _, _, nm, _ in rows if "エネルギー" in nm)
    to = {energy_key(nm): nm for _, _, nm, _ in rows if "エネルギー" in nm}
    out = []
    for alt, url, no in items:
        if "エネルギー" in alt:
            k = energy_key(alt)
            if cand.get(k) == 1 and to[k] != alt:
                alt = to[k]
        out.append((alt, url, no))
    return out

IMG_RE = re.compile(
    r'data-src="(https://learn-book\.com/wp-content/uploads/[^"]+?\.(?:jpg|png))"'
    r'[^>]*?alt="([^"]*)"')
# ファイル名の末尾3桁を番号とみなす（e1087 / pcg4001 / 1st1016）。目安にしか使わない
NO_RE = re.compile(r"/([a-z0-9]+?)(\d{3})(?:-\d+x\d+)?\.(?:jpg|png)$")


def setup(con):
    # 主キーは dex_key（URLではない）。1996年の第1弾は「スターターパック」と
    # 「拡張パック」が同じ札を分け合っていて、**1つの画像URLが2つの dex 行に
    # 対応する**。URLを主キーにすると後から入れた方が前の対応を上書きしてしまう。
    old = con.execute("SELECT sql FROM sqlite_master WHERE name='learnbook'").fetchone()
    if old and "url       TEXT PRIMARY KEY" in old[0]:
        con.execute("DROP TABLE learnbook")          # 旧スキーマからの移行
    con.executescript("""
    CREATE TABLE IF NOT EXISTS learnbook (
      set_code  TEXT,
      name      TEXT,          -- ページの alt（カード名）
      url       TEXT,
      page      TEXT,
      web_no    INTEGER,       -- ファイル名から読んだ番号（目安。照合には使わない）
      dex_key   TEXT PRIMARY KEY,   -- 紐づいた dex の行
      local     TEXT,          -- 保存先。未取得なら NULL
      status    TEXT           -- ok:名前 / ok:番号 / error
    );
    CREATE INDEX IF NOT EXISTS idx_lb_url ON learnbook(url);
    """)
    con.commit()


def fetch_page(slug: str) -> list[tuple[str, str, int | None]]:
    """1ページから (カード名, 画像URL, 番号) を返す。縮小版(-214x300)は捨てる。

    **番号は、そのページの主役のセットのファイルからしか読まない。**
    ページには「当たりカード」等で別セットの画像が混ざっており、末尾3桁だけを
    見ると番号がぶつかる。実例（2026-08-14に発覚）:

        e01 のページに ★neo第4弾の `neo4098.jpg`（ヨルノズク）があり、
        `e1098` と同じ「098」に化けていた。その結果
        ・E1-098（バタフリー）に**ヨルノズクの絵が入る**
        ・番号が重複した 47/68/80/82/84 は「曖昧」として捨てられ、
          ページに `e1068.jpg`（ラフレシア）があるのに未収録のままになる

    そこでファイル名の接頭辞（`e1` / `neo1` / `1st1s` …）を数え、**最も多い
    接頭辞のものだけ番号を持たせる**。それ以外は番号を None にして名前照合に回す
    （neo01-deck の基本エネルギー `1st1s001` のように、接頭辞が違っても
    名前で正しく当たるものがあるため、捨てはしない）。
    """
    r = requests.get(BASE.format(slug=slug), headers=UA, timeout=30)
    r.raise_for_status()
    rows, seen = [], set()
    for url, alt in IMG_RE.findall(r.text):
        if re.search(r"-\d+x\d+\.(?:jpg|png)$", url):
            continue                              # サムネイル
        alt = alt.strip()
        if not alt or url in seen:
            continue
        seen.add(url)
        m = NO_RE.search(url)
        rows.append((alt, url, m.group(1) if m else None,
                     int(m.group(2)) if m else None))

    main_pre = Counter(p for _, _, p, _ in rows if p).most_common(1)
    main_pre = main_pre[0][0] if main_pre else None
    return [(alt, url, no if pre == main_pre else None)
            for alt, url, pre, no in rows]


def group_rows(con, set_code, pack_name):
    """このページが相手にする dex の行。match() と energy_alias() で同じものを使う。"""
    if set_code:
        return con.execute(
            """SELECT key, card_no, name,
                  (img IS NULL AND img_off IS NULL AND img_web IS NULL) noimg
               FROM dex WHERE set_code = ?""", (set_code,)).fetchall()
    # set_code を持たない行だけを相手にする。**パック名だけで引くと別年代の
    # 同名商品を巻き込む**（「スターターパック」は1996年に96枚、2016年の 20th に
    # 84枚ある。20th 側は既に画像がある）。デッキ商品のエネルギーもここに入る
    return con.execute(
        """SELECT key, card_no, name,
                  (img IS NULL AND img_off IS NULL AND img_web IS NULL) noimg
           FROM dex WHERE set_code IS NULL AND pack_name = ?""",
        (pack_name,)).fetchall()


def match(con, set_code, pack_name, items, rows=None, claimed=None):
    """ページの画像と dex の行を突き合わせる。曖昧なものは捨てる。

    返す hit は (dex_key, dex名, URL, ページ番号, dex番号, 照合方法)。

    claimed には**この実行ですでに埋めた dex_key** を渡す。`dex.img_web` を
    書くのは build_dex.py なので、実行中の dex はまだ空のまま。渡さないと、
    同じ行を複数のページが奪い合って後勝ちになる（1商品に複数ページを
    当てる「シリーズの絵を借りる」対応づけで実際に起きる）。
    """
    if rows is None:
        rows = group_rows(con, set_code, pack_name)
    if claimed:
        rows = [r for r in rows if r[0] not in claimed]

    by_name, dup = {}, Counter()
    by_no, no_dup = {}, Counter()
    for k, no, nm, noimg in rows:
        dup[nname(nm)] += 1
        by_name.setdefault(nname(nm), (k, no, nm, noimg))
        if no is not None:
            no_dup[no] += 1
            by_no.setdefault(no, (k, no, nm, noimg))

    page_dup = Counter(nname(a) for a, _, _ in items)
    page_no_dup = Counter(n for _, _, n in items if n is not None)

    out = {"hit": [], "ambiguous": 0, "not_in_dex": 0, "already": 0,
           "agree": 0, "disagree": 0, "by_no": 0}
    used, rest = set(), []
    for alt, url, web_no in items:
        n = nname(alt)
        if n not in by_name or dup[n] > 1 or page_dup[n] > 1:
            if n in by_name:
                out["ambiguous"] += 1           # 同名が複数。絵を取り違えるので捨てる
            else:
                out["not_in_dex"] += 1
            rest.append((alt, url, web_no))
            continue
        key, no, nm, noimg = by_name[n]
        # 番号が信用できるセットかどうかの判断材料を貯める（採否には使わない）
        if web_no is not None and no is not None:
            out["agree" if web_no == no else "disagree"] += 1
        if not noimg:
            out["already"] += 1                 # 既に画像がある
            continue
        used.add(key)
        out["hit"].append((key, nm, url, web_no, no, "名前"))

    # 名前で当たった組が3組以上あって1組も食い違わないなら、このセットは
    # 番号の体系が同じとみなして残りを番号で拾う（名前が壊れている年代の救済）
    if (out["agree"] >= 3 and out["disagree"] == 0) or set_code in VERIFIED_NUMBERING:
        for alt, url, web_no in rest:
            if web_no is None or page_no_dup[web_no] > 1 or no_dup.get(web_no, 0) > 1:
                continue
            hit = by_no.get(web_no)
            if not hit:
                continue
            key, no, nm, noimg = hit
            if not noimg or key in used:
                continue
            used.add(key)
            out["by_no"] += 1
            out["hit"].append((key, nm, url, web_no, no, "番号"))
    return out


def download(con, set_code, key, url, dry=False):
    path = os.path.join(IMG_DIR, set_code or "misc",
                        f"{key.replace('/', '_')}.jpg")
    if os.path.exists(path):
        return path
    if dry:
        return None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    with open(path, "wb") as f:
        f.write(r.content)
    time.sleep(WAIT)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="数えるだけで取得しない")
    ap.add_argument("--pages", help="スラッグをカンマ区切りで指定（既定は全部）")
    a = ap.parse_args()

    pages = PAGES
    if a.pages:
        want = {s.strip() for s in a.pages.split(",")}
        pages = [p for p in PAGES if p[0] in want]

    con = sqlite3.connect(DB)
    setup(con)

    tot_hit = tot_dl = 0
    claimed = set()          # この実行で埋めた dex_key（後勝ちを防ぐ）
    print(f"{'ページ':8} {'セット':6} {'画像':>4} {'照合':>4} "
          f"{'名前':>4} {'番号':>4} {'番号の検証':>12}")
    for slug, set_code, pack_name in pages:
        try:
            items = fetch_page(slug)
        except Exception as e:
            print(f"{slug:10} {set_code or '-':7} 取得失敗: {e}")
            continue
        time.sleep(WAIT)
        alias = ALIAS.get(slug, {})
        if alias:
            items = [(alias.get(a, a), u, n) for a, u, n in items]
        rows = group_rows(con, set_code, pack_name)
        items = energy_alias(rows, items)
        m = match(con, set_code, pack_name, items, rows, claimed)
        by_name_n = len(m["hit"]) - m["by_no"]
        verdict = (f"一致{m['agree']}/食違{m['disagree']}"
                   + ("→採用" if m["by_no"] else "→不採用"))
        print(f"{slug:8} {set_code or '-':6} {len(items):>4} {len(m['hit']):>4} "
              f"{by_name_n:>4} {m['by_no']:>4} {verdict:>12}")
        tot_hit += len(m["hit"])

        claimed.update(h[0] for h in m["hit"])
        for key, nm, url, web_no, dex_no, how in m["hit"]:
            local = None
            status = "ok"
            try:
                local = download(con, set_code, key, url, dry=a.dry_run)
                if local:
                    tot_dl += 1
            except Exception as e:
                status = "error"
                print(f"    画像取得失敗 {nm}: {e}")
            con.execute("""INSERT OR REPLACE INTO learnbook
                           (set_code, name, url, page, web_no, dex_key, local, status)
                           VALUES (?,?,?,?,?,?,?,?)""",
                        (set_code, nm, url, slug, web_no, key, local,
                         status if status != "ok" else f"ok:{how}"))
        con.commit()

    print(f"\n照合 {tot_hit}枚 / 取得 {tot_dl}枚"
          + ("（--dry-run なので取得していない）" if a.dry_run else ""))
    print("このあと python build_dex.py で図鑑に反映する")


if __name__ == "__main__":
    main()
