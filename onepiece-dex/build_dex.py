"""
巡回した生データ（cards / series / card_series）から、画面が引く図鑑テーブルを組み立てる。

ネットワークは使わない。crawl_official.py と fetch_images.py のあとに流す。

  dex          … カード1枚＝1行。並び順の数値（rarity_i）や日本語ラベルを足したもの
  dex_series   … シリーズ1件＝1行。収録枚数・画像枚数・表紙を持つ
  dex_features … 特徴（四皇・麦わらの一味…）を1件ずつばらしたもの。絞り込み用
  dex_colors   … 多色（赤/緑）を1色ずつばらしたもの。絞り込み用

**生データは書き換えない。** 作り直したくなったらこれを流し直せば済むようにしてある。
"""

from __future__ import annotations

import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "data", "cards.db")

# 弱い順。絞り込みの並びと、一覧の既定の並び順に使う。
# DON・L は強弱の軸ではないので先頭に寄せ、スーパーパラレル系を最上位に置く
# （各弾の最上位レアリティ。fill_super_parallel.py が付ける）
RARITY_ORDER = ["DON", "L", "C", "UC", "R", "SR", "SEC", "P", "SP P", "SPカード",
                "TR",
                "スーパーパラレル", "ゴールドスーパーパラレル", "レッドスーパーパラレル",
                "リーダースーパーパラレル", "海賊団スーパーパラレル",
                "神の騎士団スーパーパラレル"]

RARITY_NOTE = {
    "C": "コモン", "UC": "アンコモン", "R": "レア", "SR": "スーパーレア",
    "SEC": "シークレットレア", "L": "リーダー", "P": "プロモ",
    "SPカード": "スペシャルカード", "SP P": "スペシャル（プロモ）",
    "TR": "トレジャーレア", "DON": "ドン!!カード",
    "スーパーパラレル": "コミパラ。各弾の最上位",
    "ゴールドスーパーパラレル": "2周年・OP-09のみ",
    "レッドスーパーパラレル": "3周年・OP-13のみ",
    "リーダースーパーパラレル": "4周年・OP-17のみ。初のリーダー",
    "海賊団スーパーパラレル": "4周年・OP-17のみ",
    "神の騎士団スーパーパラレル": "OP-18のみ",
}

# 一覧のタイルに出す短い表記。「スーパーパラレル」は9文字あって折り返す
RARITY_SHORT = {
    "スーパーパラレル": "SP", "ゴールドスーパーパラレル": "金SP",
    "レッドスーパーパラレル": "赤SP", "リーダースーパーパラレル": "LSP",
    "海賊団スーパーパラレル": "海賊団SP", "神の騎士団スーパーパラレル": "騎士団SP",
}


def super_parallel() -> dict:
    """`fill_super_parallel.py` が作った一覧を読む。

    **公式サイトはスーパーパラレル（コミパラ）の区分を持っていない**（OP17-005 は
    通常も `_p1` も `_p2` も一律 `SR`）。無いと各弾の最上位レアリティが通常のSRに
    埋もれて引けないので、外部の一覧を典拠に補ったものをここで混ぜる。
    無ければ何もしない（図鑑は動く）。
    """
    path = os.path.join(HERE, "data", "super_parallel.json")
    if not os.path.exists(path):
        print("※ data/super_parallel.json が無いので"
              "スーパーパラレルは通常のレアリティのまま"
              "（`python fill_super_parallel.py` で作れる）")
        return {}
    import json
    return json.load(open(path, encoding="utf-8"))

# 公式の商品ラインナップの data-cat → 図鑑での分類（ポケカ図鑑と同じ言い方に揃える）
PTYPE_BY_CAT = {"boosters": "拡張パック", "decks": "構築デッキ",
                "others": "その他の商品"}

# 商品ラインナップに載っていないシリーズ用。名前の頭で判断する
PTYPE_BY_NAME = [
    ("ブースターパック", "拡張パック"), ("プレミアムブースター", "拡張パック"),
    ("エクストラブースター", "拡張パック"),
    ("スタートデッキ", "構築デッキ"), ("アルティメットデッキ", "構築デッキ"),
    ("ファミリーデッキ", "構築デッキ"),
]


def ptype_from_name(name: str | None) -> str:
    for head, t in PTYPE_BY_NAME:
        if (name or "").startswith(head):
            return t
    return "その他の商品"


CATEGORY_JA = {
    "LEADER": "リーダー", "CHARACTER": "キャラクター",
    "EVENT": "イベント", "STAGE": "ステージ", "DON!!": "ドン!!",
}


def have(rel: str) -> str | None:
    """あるファイルだけ相対パスで返す。無ければ None。"""
    return rel if os.path.exists(os.path.join(HERE, rel)) else None


def build(cx: sqlite3.Connection) -> None:
    # executescript は使わない。**busy_timeout を無視する**ので、
    # 裏で fetch_images.py が走っていると即 "database is locked" で落ちる
    # （2026-08-23に実測。execute は46秒待って成功、executescript は0秒で失敗）。
    # BEGIN IMMEDIATE で書き込みロックを取ってから1文ずつ流す。
    cx.execute("BEGIN IMMEDIATE")
    for stmt in filter(None, (x.strip() for x in """
    DROP TABLE IF EXISTS dex;
    DROP TABLE IF EXISTS dex_series;
    DROP TABLE IF EXISTS dex_features;
    DROP TABLE IF EXISTS dex_colors;

    CREATE TABLE dex (
      key TEXT PRIMARY KEY, code TEXT, variant TEXT, set_code TEXT, card_no INTEGER,
      name TEXT, rarity TEXT, rarity_i INTEGER, rarity_note TEXT,
      rarity_base TEXT,   -- 公式のレアリティ（スーパーパラレルを差し替える前）
      rarity_short TEXT,  -- 一覧のタイル用の短い表記（SP / 金SP …）
      category TEXT, category_ja TEXT,
      cost INTEGER, cost_label TEXT, attribute TEXT,
      power INTEGER, counter INTEGER, color TEXT, block TEXT,
      feature TEXT, text TEXT, get_info TEXT,
      img TEXT, thumb TEXT, price INTEGER,
      series_id TEXT, series_name TEXT
    );
    CREATE INDEX idx_dex_name ON dex(name);
    CREATE INDEX idx_dex_set  ON dex(set_code);
    CREATE INDEX idx_dex_rar  ON dex(rarity_i);
    CREATE INDEX idx_dex_cat  ON dex(category);
    CREATE INDEX idx_dex_no   ON dex(card_no);

    CREATE TABLE dex_series (
      series_id TEXT PRIMARY KEY, name TEXT, short TEXT, code TEXT, kind TEXT,
      sort INTEGER, cards INTEGER, images INTEGER,
      cover TEXT,        -- 商品パッケージ画像。無ければリーダーの絵で代用
      cover_src TEXT,    -- 'product'（パッケージ）か 'card'（リーダーの絵）
      ptype TEXT,        -- 拡張パック / 構築デッキ / その他
      release TEXT,      -- 2026-08-22（公式の商品ラインナップ由来）
      price TEXT,
      product_url TEXT
    );
    CREATE TABLE dex_features (key TEXT, feature TEXT);
    CREATE INDEX idx_df ON dex_features(feature);
    CREATE TABLE dex_colors  (key TEXT, color TEXT);
    CREATE INDEX idx_dc ON dex_colors(color);
    """.split(";"))):
        cx.execute(stmt)

    sp = super_parallel()
    rows = cx.execute("SELECT * FROM cards").fetchall()
    cols = [d[0] for d in cx.execute("SELECT * FROM cards LIMIT 1").description]
    idx = {c: i for i, c in enumerate(cols)}
    snames = dict(cx.execute("SELECT series_id, name FROM series").fetchall())

    for r in rows:
        g = lambda c: r[idx[c]]
        rar = base_rar = g("rarity")
        if g("key") in sp:
            rar = sp[g("key")]["rarity"]
        # 画像は**ファイルがあるかどうか**で決める。DBのフラグを信じない
        # （取得は途中で止められるし、消したファイルも拾ってしまう）
        img = have(os.path.join("data", "img", g("key") + ".png"))
        thumb = have(os.path.join("data", "thumb", g("key") + ".jpg"))
        cx.execute(
            "INSERT INTO dex VALUES (%s)" % ",".join("?" * 28),
            (g("key"), g("code"), g("variant"), g("set_code"), g("card_no"),
             g("name"), rar,
             RARITY_ORDER.index(rar) if rar in RARITY_ORDER else 99,
             RARITY_NOTE.get(rar), base_rar, RARITY_SHORT.get(rar),
             g("category"), CATEGORY_JA.get(g("category"), g("category")),
             g("cost"), g("cost_label"), g("attribute"),
             g("power"), g("counter"), g("color"), g("block"),
             g("feature"), g("text"), g("get_info"),
             img, thumb, g("price"),
             g("series_id"), snames.get(g("series_id"))))

        # 「四皇/白ひげ海賊団」→ 2件。絞り込みで「四皇」を選べるようにする
        for f in (g("feature") or "").split("/"):
            f = f.strip()
            if f and f != "-":
                cx.execute("INSERT INTO dex_features VALUES (?,?)", (g("key"), f))
        # 多色（赤/緑）は色ごとに1件。「赤」で引いたときに多色も出る
        for c in (g("color") or "").split("/"):
            c = c.strip()
            if c and c != "-":
                cx.execute("INSERT INTO dex_colors VALUES (?,?)", (g("key"), c))

    # ── シリーズ。収録は card_series（1枚が複数シリーズに載ることがある）で数える
    #
    # 公式の**商品ラインナップ**（products）と記号【OP-17】で突き合わせて、
    # パッケージ画像・発売日・価格・商品分類を持たせる。カードリスト側には
    # どれも入っていないので、これが無いと「拡張パックを表紙で選ぶ」画面が作れない。
    prod = {r[0]: r for r in cx.execute(
        "SELECT code, cat, img, release, price, url FROM products "
        "WHERE code IS NOT NULL")}
    for sid, name, code, kind, sort in cx.execute(
            "SELECT series_id, name, code, kind, sort FROM series").fetchall():
        n = cx.execute("SELECT COUNT(*) FROM card_series WHERE series_id=?",
                       (sid,)).fetchone()[0]
        im = cx.execute(
            "SELECT COUNT(*) FROM card_series cs JOIN dex d ON d.key=cs.key "
            "WHERE cs.series_id=? AND d.img IS NOT NULL", (sid,)).fetchone()[0]
        p = prod.get(code)
        ptype = PTYPE_BY_CAT.get(p[1]) if p else None
        if not ptype:
            # 商品ラインナップに無いシリーズ（ST-02〜04・ST-16〜20 は現行の
            # ラインナップから外れていて載っていない）は名前から判断する
            ptype = ptype_from_name(name)
        cover = have(p[2]) if p and p[2] else None
        cover_src = "product" if cover else None
        if not cover:
            # パッケージ画像が無いシリーズは、そのシリーズのリーダーの絵を借りる
            row = cx.execute(
                "SELECT d.thumb FROM card_series cs JOIN dex d ON d.key=cs.key "
                "WHERE cs.series_id=? AND d.thumb IS NOT NULL "
                "ORDER BY (d.category!='LEADER'), d.card_no, d.variant LIMIT 1",
                (sid,)).fetchone()
            cover = row[0] if row else None
            cover_src = "card" if cover else None
        short = (name or "").split("【")[0].strip()
        # 「ブースターパック 世界最強の戦士」→ 種別を落として作品名だけにする
        for k in ("ブースターパック", "プレミアムブースター", "エクストラブースター",
                  "アルティメットデッキ", "スタートデッキEX", "スタートデッキ"):
            if short.startswith(k):
                short = short[len(k):].strip() or k
                break
        cx.execute("INSERT INTO dex_series VALUES (%s)" % ",".join("?" * 14),
                   (sid, name, short, code, kind, sort, n, im, cover, cover_src,
                    ptype, p[3] if p else None, p[4] if p else None,
                    p[5] if p else None))
    cx.commit()


def main() -> None:
    # 画像取得（fetch_images.py）を裏で流したまま組み立てることがあるので、
    # 書き込みロックが空くのを待つ。待たないと "database is locked" で落ちる
    cx = sqlite3.connect(DB, timeout=120)
    build(cx)
    q = lambda s: cx.execute(s).fetchone()[0]
    print(f"カード     {q('SELECT COUNT(*) FROM dex'):,}枚")
    print(f"画像       {q('SELECT COUNT(*) FROM dex WHERE img IS NOT NULL'):,}枚")
    print(f"サムネイル {q('SELECT COUNT(*) FROM dex WHERE thumb IS NOT NULL'):,}枚")
    print(f"シリーズ   {q('SELECT COUNT(*) FROM dex_series')}件")
    print(f"特徴       {q('SELECT COUNT(DISTINCT feature) FROM dex_features')}種")
    n_sp = q("SELECT COUNT(*) FROM dex WHERE rarity_short IS NOT NULL")
    print(f"スーパーパラレル系 {n_sp}枚")
    print("\n分類ごとのシリーズ")
    for t, n, c in cx.execute("SELECT ptype, COUNT(*), SUM(cards) FROM dex_series "
                              "GROUP BY 1 ORDER BY 2 DESC"):
        print(f"  {t or '（なし）':10s} {n:3d}件  {c:,}枚")
    npkg = q("SELECT COUNT(*) FROM dex_series WHERE cover_src='product'")
    print(f"\nパッケージ画像を持つシリーズ {npkg}/{q('SELECT COUNT(*) FROM dex_series')}件"
          "（残りはリーダーの絵で代用）")


if __name__ == "__main__":
    main()
