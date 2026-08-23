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
# L（リーダー）は強弱の軸ではないので最後に寄せる
RARITY_ORDER = ["C", "UC", "R", "SR", "SEC", "SPカード", "SP P", "P", "TR", "DON", "L"]

RARITY_NOTE = {
    "C": "コモン", "UC": "アンコモン", "R": "レア", "SR": "スーパーレア",
    "SEC": "シークレットレア", "L": "リーダー", "P": "プロモ",
    "SPカード": "スペシャルカード", "SP P": "スペシャル（プロモ）",
    "TR": "トレジャーレア", "DON": "ドン!!カード",
}

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
      sort INTEGER, cards INTEGER, images INTEGER, cover TEXT
    );
    CREATE TABLE dex_features (key TEXT, feature TEXT);
    CREATE INDEX idx_df ON dex_features(feature);
    CREATE TABLE dex_colors  (key TEXT, color TEXT);
    CREATE INDEX idx_dc ON dex_colors(color);
    """.split(";"))):
        cx.execute(stmt)

    rows = cx.execute("SELECT * FROM cards").fetchall()
    cols = [d[0] for d in cx.execute("SELECT * FROM cards LIMIT 1").description]
    idx = {c: i for i, c in enumerate(cols)}
    snames = dict(cx.execute("SELECT series_id, name FROM series").fetchall())

    for r in rows:
        g = lambda c: r[idx[c]]
        rar = g("rarity")
        # 画像は**ファイルがあるかどうか**で決める。DBのフラグを信じない
        # （取得は途中で止められるし、消したファイルも拾ってしまう）
        img = have(os.path.join("data", "img", g("key") + ".png"))
        thumb = have(os.path.join("data", "thumb", g("key") + ".jpg"))
        cx.execute(
            "INSERT INTO dex VALUES (%s)" % ",".join("?" * 26),
            (g("key"), g("code"), g("variant"), g("set_code"), g("card_no"),
             g("name"), rar,
             RARITY_ORDER.index(rar) if rar in RARITY_ORDER else 99,
             RARITY_NOTE.get(rar),
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
    for sid, name, code, kind, sort in cx.execute(
            "SELECT series_id, name, code, kind, sort FROM series").fetchall():
        n = cx.execute("SELECT COUNT(*) FROM card_series WHERE series_id=?",
                       (sid,)).fetchone()[0]
        im = cx.execute(
            "SELECT COUNT(*) FROM card_series cs JOIN dex d ON d.key=cs.key "
            "WHERE cs.series_id=? AND d.img IS NOT NULL", (sid,)).fetchone()[0]
        # 表紙は商品パッケージ画像ではなく**そのシリーズのリーダーの絵**を借りる。
        # 公式のカードリストに商品画像が無いため（正直に README に書いてある）
        cover = cx.execute(
            "SELECT d.thumb FROM card_series cs JOIN dex d ON d.key=cs.key "
            "WHERE cs.series_id=? AND d.thumb IS NOT NULL "
            "ORDER BY (d.category!='LEADER'), d.card_no, d.variant LIMIT 1",
            (sid,)).fetchone()
        short = (name or "").split("【")[0].strip()
        # 「ブースターパック 世界最強の戦士」→ 種別を落として作品名だけにする
        for k in ("ブースターパック", "プレミアムブースター", "エクストラブースター",
                  "アルティメットデッキ", "スタートデッキEX", "スタートデッキ"):
            if short.startswith(k):
                short = short[len(k):].strip() or k
                break
        cx.execute("INSERT INTO dex_series VALUES (?,?,?,?,?,?,?,?,?)",
                   (sid, name, short, code, kind, sort, n, im,
                    cover[0] if cover else None))
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


if __name__ == "__main__":
    main()
