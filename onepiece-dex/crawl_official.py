"""
公式サイト（onepiece-cardgame.com）のカードリストを全シリーズ巡回して data/cards.db に入れる。

**ここが唯一の情報源。** ポケカ図鑑は公式がレアリティを公開していないので
DMMマイカ・TCGdex・learn-book の4ソースを継ぎ接ぎしたが、ワンピは公式1本で
カード番号・レアリティ・種類・色・コスト・パワー・カウンター・属性・特徴・
テキスト・入手情報・画像が全部揃う。

  POST https://www.onepiece-cardgame.com/cardlist/  body: series=<ID>

GET の ?series= でも 200 は返るが**カードは入っていない**（62件のシリーズ選択肢
だけ）。JS で描いているのではなく、POST でないと結果を返さないため。

実行:  python crawl_official.py            # 全シリーズ
       python crawl_official.py 550117     # シリーズを指定
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
LIST_URL = "https://www.onepiece-cardgame.com/cardlist/"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}
WAIT = 0.7          # 公式サイトへの間隔。急がない（全62件で1分程度）


def fetch(data: dict | None = None) -> str:
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(LIST_URL, body, UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def schema(cx: sqlite3.Connection) -> None:
    cx.executescript("""
    CREATE TABLE IF NOT EXISTS series (
      series_id TEXT PRIMARY KEY,   -- 公式の内部ID（550117）
      name      TEXT,               -- ブースターパック 世界最強の戦士【OP-17】
      code      TEXT,               -- OP-17（【】の中）
      kind      TEXT,               -- ブースターパック / スタートデッキ / …
      sort      INTEGER,              -- 公式の選択肢に並んでいた順（新しい順）。図鑑もこの順で出す
      cards     INTEGER,
      fetched   REAL
    );
    CREATE TABLE IF NOT EXISTS cards (
      key        TEXT PRIMARY KEY,  -- OP17-001 / EB04-061_p3。画像ファイル名と一致する
      code       TEXT,              -- OP17-001（パラレルの接尾辞を落としたもの）
      variant    TEXT,              -- ''（通常）/ p1 / p2 / p3 …（別イラスト）
      set_code   TEXT,              -- OP17 / EB04 / ST01 / P …
      card_no    INTEGER,           -- 1（001）
      name       TEXT,
      rarity     TEXT,              -- L C UC R SR SEC P DON TR …
      category   TEXT,              -- LEADER / CHARACTER / EVENT / STAGE / DON!!
      cost       INTEGER,           -- コスト。LEADER はライフの値が入る
      cost_label TEXT,              -- 'コスト' か 'ライフ'（LEADERだけ後者）
      attribute  TEXT,              -- 打 / 斬 / 特 / 知 / 射（無しは NULL）
      power      INTEGER,
      counter    INTEGER,
      color      TEXT,              -- 赤 / 赤黒 など。多色はそのまま入れる
      block      TEXT,              -- ブロックアイコン（1〜/ X / -）
      feature    TEXT,              -- 特徴（'四皇/白ひげ海賊団' のまま）
      text       TEXT,              -- テキスト（改行は \\n）
      get_info   TEXT,              -- 入手情報
      img_url    TEXT,              -- 公式の画像URL（絶対）
      img        TEXT,              -- 保存したローカルパス（data/img/…）
      price      INTEGER,           -- 相場。公式は持たないので当面 NULL（将来用）
      series_id  TEXT,              -- 最初に見つけたシリーズ
      fetched    REAL
    );
    CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(name);
    CREATE INDEX IF NOT EXISTS idx_cards_set  ON cards(set_code);
    CREATE INDEX IF NOT EXISTS idx_cards_rar  ON cards(rarity);
    -- 1枚のカードが複数シリーズに載ることがある（プロモの再録など）ので分けて持つ
    CREATE TABLE IF NOT EXISTS card_series (
      key TEXT, series_id TEXT, PRIMARY KEY (key, series_id)
    );
    -- 想定外の形が来たら捨てずに残す。欠番と「読めなかった」を混ぜないため
    CREATE TABLE IF NOT EXISTS unparsed (
      series_id TEXT, snippet TEXT, reason TEXT, fetched REAL
    );
    """)
    cx.commit()


def txt(s: str) -> str:
    """タグを落として実体参照を戻す。<br> だけは改行として残す。"""
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()


def field(block: str, cls: str) -> str | None:
    """<div class="cost"><h3>コスト</h3>10</div> の「10」を取る。"""
    m = re.search(r'<div class="%s">(.*?)</div>\s*(?:<div|</div>)' % cls, block, re.S)
    if not m:
        m = re.search(r'<div class="%s">(.*?)</div>' % cls, block, re.S)
    if not m:
        return None
    body = re.sub(r"<h3>.*?</h3>", "", m.group(1), flags=re.S)
    v = txt(body)
    return v or None


def num(v: str | None) -> int | None:
    if not v:
        return None
    m = re.search(r"-?\d+", v.replace(",", ""))
    return int(m.group()) if m else None


def parse_series_list(page: str) -> list[tuple[str, str]]:
    """シリーズの選択肢。**実体参照を戻してからタグを落とす**（順番が逆だと
    `&lt;br class="spInline"&gt;` がそのまま名前に残り、画面に <br> が出る）。"""
    out = []
    for sid, nm in re.findall(r'<option value="(\d+)"[^>]*>(.*?)</option>', page, re.S):
        out.append((sid, txt(html.unescape(nm))))
    return out


def parse_cards(page: str, series_id: str):
    """1シリーズぶんの HTML から <dl class="modalCol"> を1枚ずつ切り出す。"""
    for block in re.findall(r'<dl class="modalCol".*?</dl>', page, re.S):
        m = re.search(r'<dl class="modalCol" id="([^"]+)"', block)
        if not m:
            yield None, block, "id なし"
            continue
        key = m.group(1)

        info = re.search(r'<div class="infoCol">(.*?)</div>', block, re.S)
        spans = [txt(x) for x in re.findall(r"<span>(.*?)</span>", info.group(1), re.S)] \
            if info else []
        if len(spans) < 3:
            yield None, block, f"infoCol が3項目でない: {spans}"
            continue
        code, rarity, category = spans[0], spans[1], spans[2]

        name = txt(re.search(r'<div class="cardName">(.*?)</div>',
                             block, re.S).group(1)) if '"cardName"' in block else None

        # 属性は <img alt="打">。無いカードは "-"
        attr = None
        am = re.search(r'<div class="attribute">(.*?)</div>', block, re.S)
        if am:
            alts = re.findall(r'alt="([^"]*)"', am.group(1))
            attr = "/".join(a for a in alts if a) or None

        # コスト欄の見出しは LEADER だけ「ライフ」
        cm = re.search(r'<div class="cost"><h3>(.*?)</h3>(.*?)</div>', block, re.S)
        cost_label = txt(cm.group(1)) if cm else None
        cost = num(txt(cm.group(2))) if cm else None

        img = re.search(r'<div class="frontCol">.*?data-src="([^"?]+)', block, re.S)
        img_url = None
        if img:
            img_url = urllib.parse.urljoin(
                "https://www.onepiece-cardgame.com/cardlist/", img.group(1))

        base, _, variant = key.partition("_")
        setc, _, no = base.partition("-")
        yield {
            "key": key, "code": code or base, "variant": variant,
            "set_code": setc, "card_no": num(no), "name": name,
            "rarity": rarity or None, "category": category or None,
            "cost": cost, "cost_label": cost_label, "attribute": attr,
            "power": num(field(block, "power")),
            "counter": num(field(block, "counter")),
            "color": field(block, "color"),
            "block": field(block, "block"),
            "feature": field(block, "feature"),
            "text": field(block, "text"),
            "get_info": field(block, "getInfo"),
            "img_url": img_url, "series_id": series_id,
        }, block, None


COLS = ("key code variant set_code card_no name rarity category cost cost_label "
        "attribute power counter color block feature text get_info img_url "
        "series_id").split()


def save(cx, rows):
    now = time.time()
    for r in rows:
        vals = [r[c] for c in COLS] + [now]
        # img と price は触らない（画像取得の結果・将来の相場を消さないため）
        cx.execute(
            "INSERT INTO cards (%s, fetched) VALUES (%s) "
            "ON CONFLICT(key) DO UPDATE SET %s, fetched=excluded.fetched"
            % (",".join(COLS), ",".join("?" * (len(COLS) + 1)),
               ",".join(f"{c}=excluded.{c}" for c in COLS if c != "key")),
            vals)
        cx.execute("INSERT OR IGNORE INTO card_series VALUES (?,?)",
                   (r["key"], r["series_id"]))
    cx.commit()


def main() -> None:
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    cx = sqlite3.connect(DB)
    schema(cx)

    top = fetch()
    series = parse_series_list(top)
    if not series:
        print("シリーズ一覧が取れない。公式サイトの作りが変わった可能性がある")
        sys.exit(1)
    want = sys.argv[1:]
    if want:
        series = [s for s in series if s[0] in want]
    print(f"シリーズ {len(series)}件")

    total = 0
    for order, (sid, name) in enumerate(series):
        code = (re.search(r"【(.+?)】", name) or [None, None])[1]
        kind = name.split("【")[0].split()[0] if name else None
        try:
            page = fetch({"series": sid})
        except Exception as e:                       # 1件の失敗で全体を止めない
            print(f"  !! {sid} {name}: {e}")
            continue
        rows, bad = [], 0
        for row, block, reason in parse_cards(page, sid):
            if row is None:
                bad += 1
                cx.execute("INSERT INTO unparsed VALUES (?,?,?,?)",
                           (sid, block[:1000], reason, time.time()))
            else:
                rows.append(row)
        save(cx, rows)
        cx.execute("INSERT INTO series VALUES (?,?,?,?,?,?,?) "
                   "ON CONFLICT(series_id) DO UPDATE SET name=excluded.name, "
                   "code=excluded.code, kind=excluded.kind, sort=excluded.sort, "
                   "cards=excluded.cards, fetched=excluded.fetched",
                   (sid, name, code, kind, order, len(rows), time.time()))
        cx.commit()
        total += len(rows)
        print(f"  {sid} {len(rows):4d}枚{'  読めず%d' % bad if bad else ''}  {name}",
              flush=True)
        time.sleep(WAIT)

    n = cx.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    u = cx.execute("SELECT COUNT(*) FROM unparsed").fetchone()[0]
    print(f"\n巡回 {total}枚 / DB内 {n}枚（重複を除いた実数）/ 読めず {u}件")


if __name__ == "__main__":
    main()
