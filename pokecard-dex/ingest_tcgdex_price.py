"""TCGdex から相場（pricing）を取り込み、為替レートと一緒に保存する。

## なぜ別スクリプトなのか

`ingest_tcgdex.py` はカードの中身（ワザ・HP・効果文）を取る。あちらは一度取れば
めったに変わらないが、**相場は毎日動く**ので取り込みの周期が違う。同じ処理に
混ぜると「相場を更新したいだけなのに全カードを取り直す」ことになる。

## 実測して分かっていること（2026-08-20）

- `dex` 31,520枚のうち **TCGdex の本物のIDを持つのは 9,508枚（30%）**。
  残りは `*-off*`（公式サイト由来の合成ID）か tcg_id が空で、TCGdex には存在しない
- そのうち **無作為25枚中22枚（88%）に相場が付いた** → 全体で約8,400枚が対象
- **日本語カードは Cardmarket(EUR) しか付かない。** TCGplayer の marketPrice は None。
  つまり **これは欧州市場の相場であって、日本国内の相場ではない**（画面にもそう書く）
- **グレード品（PSA鑑定済み）の相場は取れない。** 生カードの相場だけ

## 使い方

    .venv/bin/python ingest_tcgdex_price.py              # 全件（再開可能）
    .venv/bin/python ingest_tcgdex_price.py --limit 50   # お試し
    .venv/bin/python ingest_tcgdex_price.py --fx-only    # 為替だけ更新
    .venv/bin/python ingest_tcgdex_price.py --max-age 0  # 取得済みも取り直す

途中で止めても、既に取り込んだぶんは `--max-age`（既定7日）以内なら飛ばすので
続きから再開できる。
"""
import argparse
import datetime
import json
import os
import sqlite3
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "data", "cards.db")
API = "https://api.tcgdex.net/v2/ja"

# 為替。キー不要のものを上から順に試す（1つが落ちても止まらないように）
FX_SOURCES = [
    ("open.er-api.com", "https://open.er-api.com/v6/latest/{base}",
     lambda d: d.get("rates")),
    ("frankfurter.dev", "https://api.frankfurter.dev/v1/latest?base={base}",
     lambda d: d.get("rates")),
    ("exchangerate-api", "https://api.exchangerate-api.com/v4/latest/{base}",
     lambda d: d.get("rates")),
]

_lock = threading.Lock()
_done = 0


def _get(url, tries=3, timeout=30):
    for i in range(tries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "pokecard-dex/1.0 (personal use)"})
            with urllib.request.urlopen(req, timeout=timeout) as f:
                return json.load(f)
        except Exception:
            if i == tries - 1:
                return None
            time.sleep(1.5 * (i + 1))
    return None


def setup(con):
    """テーブルを足すだけ。既存のテーブルには触らない。"""
    con.executescript("""
    CREATE TABLE IF NOT EXISTS prices (
      tcg_id     TEXT PRIMARY KEY,   -- TCGdex のカードID（dex.tcg_id と同じ）
      cm_avg     REAL,               -- Cardmarket 平均（EUR）
      cm_low     REAL,
      cm_trend   REAL,
      cm_avg7    REAL,
      cm_avg30   REAL,
      tp_market  REAL,               -- TCGplayer 市場価（USD）※日本語カードはほぼ空
      tp_low     REAL,
      src_updated TEXT,              -- TCGdex 側の更新日時
      fetched_at  TEXT               -- こちらが取り込んだ日時
    );
    CREATE TABLE IF NOT EXISTS fx (
      pair       TEXT PRIMARY KEY,   -- 'EUR/JPY' のような通貨ペア
      rate       REAL,
      source     TEXT,
      fetched_at TEXT
    );
    """)
    con.commit()


def update_fx(con) -> dict:
    """EUR/JPY と USD/JPY を取る。取れたぶんだけ保存する。"""
    now = datetime.datetime.now().isoformat(timespec="seconds")
    got = {}
    for base in ("EUR", "USD"):
        for name, tpl, pick in FX_SOURCES:
            d = _get(tpl.format(base=base), tries=2, timeout=20)
            rates = pick(d) if d else None
            jpy = (rates or {}).get("JPY")
            if isinstance(jpy, (int, float)) and jpy > 0:
                pair = f"{base}/JPY"
                con.execute(
                    "INSERT INTO fx (pair, rate, source, fetched_at) VALUES (?,?,?,?) "
                    "ON CONFLICT(pair) DO UPDATE SET rate=excluded.rate, "
                    "source=excluded.source, fetched_at=excluded.fetched_at",
                    (pair, float(jpy), name, now))
                got[pair] = (float(jpy), name)
                break
        else:
            print(f"  ! {base}/JPY はどの取得元からも取れなかった", flush=True)
    con.commit()
    for pair, (rate, src) in got.items():
        print(f"  {pair} = {rate:.3f}  （出所: {src}）", flush=True)
    return got


def targets(con, max_age_days: int):
    """相場を取りに行くカードのIDを返す。

    `*-off*` は公式サイト由来の合成IDで TCGdex には存在しないため最初から除く
    （問い合わせても404になるだけで、相手のサーバーに無駄な負荷をかける）。
    """
    rows = con.execute(
        "SELECT DISTINCT tcg_id FROM dex "
        "WHERE tcg_id IS NOT NULL AND tcg_id NOT LIKE '%-off%'").fetchall()
    ids = [r[0] for r in rows]
    if max_age_days <= 0:
        return ids
    limit = (datetime.datetime.now()
             - datetime.timedelta(days=max_age_days)).isoformat(timespec="seconds")
    fresh = {r[0] for r in con.execute(
        "SELECT tcg_id FROM prices WHERE fetched_at >= ?", (limit,))}
    return [i for i in ids if i not in fresh]


def fetch_one(tcg_id):
    d = _get(f"{API}/cards/{tcg_id}")
    if not d:
        return None
    pr = d.get("pricing") or {}
    cm = pr.get("cardmarket") or {}
    tp = pr.get("tcgplayer") or {}
    # TCGplayer は holofoil / normal / reverseHolofoil… と版ごとに分かれる。
    # 版の区別は dex 側に無いので、最初に見つかった市場価を代表として持つ。
    tp_market = tp_low = None
    for v in tp.values():
        if isinstance(v, dict):
            if tp_market is None and v.get("marketPrice") is not None:
                tp_market = v.get("marketPrice")
                tp_low = v.get("lowPrice")
    if not cm and tp_market is None:
        return (tcg_id, None)          # 相場が無いカード（記録して再取得を避ける）
    return (tcg_id, {
        "cm_avg": cm.get("avg"), "cm_low": cm.get("low"),
        "cm_trend": cm.get("trend"), "cm_avg7": cm.get("avg7"),
        "cm_avg30": cm.get("avg30"),
        "tp_market": tp_market, "tp_low": tp_low,
        "src_updated": cm.get("updated") or tp.get("updated"),
    })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="お試し用に件数を絞る")
    ap.add_argument("--workers", type=int, default=6,
                    help="同時接続数。無料の公開APIなので控えめにする")
    ap.add_argument("--max-age", type=int, default=7,
                    help="この日数以内に取得済みなら飛ばす（0で全件取り直し）")
    ap.add_argument("--fx-only", action="store_true", help="為替だけ更新する")
    args = ap.parse_args()

    con = sqlite3.connect(DB, check_same_thread=False)
    setup(con)

    print("為替を取得")
    fx = update_fx(con)
    if args.fx_only:
        return 0
    if not fx:
        print("! 為替が1つも取れなかった。相場の取り込みは続けるが円換算は出ない", flush=True)

    ids = targets(con, args.max_age)
    if args.limit:
        ids = ids[:args.limit]
    total = len(ids)
    print(f"\n相場を取りに行く: {total:,} 件（同時 {args.workers} 接続）")
    if not total:
        print("すべて取得済み。やることなし")
        return 0

    now = datetime.datetime.now().isoformat(timespec="seconds")
    global _done
    _done = 0
    hit = miss = fail = 0

    def work(tcg_id):
        global _done
        r = fetch_one(tcg_id)
        with _lock:
            _done += 1
            if _done % 250 == 0 or _done == total:
                print(f"  {_done:,}/{total:,}", flush=True)
        return r

    # 250件ごとにコミットする。最後に1回だけだと、途中で落ちたときに
    # それまでの取得が全部消えて「再開可能」が嘘になる（WALなので読み手は止まらない）。
    n_since_commit = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for r in ex.map(work, ids):
            n_since_commit += 1
            if n_since_commit >= 250:
                con.commit()
                n_since_commit = 0
            if r is None:
                fail += 1
                continue
            tcg_id, p = r
            if p is None:
                miss += 1
                con.execute(
                    "INSERT INTO prices (tcg_id, fetched_at) VALUES (?,?) "
                    "ON CONFLICT(tcg_id) DO UPDATE SET fetched_at=excluded.fetched_at",
                    (tcg_id, now))
                continue
            hit += 1
            con.execute(
                "INSERT INTO prices (tcg_id, cm_avg, cm_low, cm_trend, cm_avg7, "
                "cm_avg30, tp_market, tp_low, src_updated, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(tcg_id) DO UPDATE SET "
                "cm_avg=excluded.cm_avg, cm_low=excluded.cm_low, "
                "cm_trend=excluded.cm_trend, cm_avg7=excluded.cm_avg7, "
                "cm_avg30=excluded.cm_avg30, tp_market=excluded.tp_market, "
                "tp_low=excluded.tp_low, src_updated=excluded.src_updated, "
                "fetched_at=excluded.fetched_at",
                (tcg_id, p["cm_avg"], p["cm_low"], p["cm_trend"], p["cm_avg7"],
                 p["cm_avg30"], p["tp_market"], p["tp_low"], p["src_updated"], now))
    con.commit()
    print(f"\n完了: 相場あり {hit:,} / 相場なし {miss:,} / 取得失敗 {fail:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
