#!/bin/bash
# 公式サイトからのカード取得の進捗を見る。実行するだけ。
cd "$(dirname "$0")"
if pgrep -f crawl_official > /dev/null; then
  echo "🟢 稼働中（経過 $(ps -o etime= -p $(pgrep -f crawl_official|head -1) | tr -d ' ')）"
else
  echo "🔴 停止中 — 再開: .venv/bin/python crawl_official.py 1 52000"
fi
python3 - <<'PY'
import sqlite3, glob, os, time

con = sqlite3.connect("data/cards.db")
q = lambda s: con.execute(s).fetchone()[0]
ok   = q("SELECT COUNT(*) FROM official WHERE status='ok'")
gone = q("SELECT COUNT(*) FROM official WHERE status='gone'")
err  = q("SELECT COUNT(*) FROM official WHERE status='error'")
seen = ok + gone + err
print(f"進捗   {seen:,}/50,500  ({100*seen/50500:.1f}%)")
print(f"内訳   カード {ok:,} / 欠番 {gone:,} / 失敗 {err:,}")

f = glob.glob("data/images/*/*.jpg")
if f:
    mb = sum(os.path.getsize(x) for x in f) / 1024 / 1024
    print(f"画像   {len(f):,}枚 / {mb:,.0f}MB / {len({os.path.basename(os.path.dirname(x)) for x in f})}パック")

# 直近の状況は「取得した時刻」で見る。card_id の最大値は試運転の行に
# 引っ張られるため使わない。
recent = con.execute("""SELECT status, card_id, fetched FROM official
                        ORDER BY fetched DESC LIMIT 2000""").fetchall()
if len(recent) > 50:
    rate = sum(1 for r in recent if r[0] == "ok") / len(recent)
    # 降順で走っているときは「いま走っている位置」は最小側になる。
    # 直近200件の中で最も新しく取得したIDを現在地とする
    pos  = recent[0][1]
    span = recent[0][2] - recent[-1][2]             # この2000件にかかった秒数
    print(f"直近   ID {pos:,} 付近 / 有効率 {100*rate:.0f}%")
    if span > 0:
        ips = len(recent) / span                    # 実測 ID/秒
        left = max(0, 50500 - seen) / ips / 3600
        # 残っているIDの本数 × 直近の有効率
        remain = con.execute("SELECT COUNT(*) FROM official").fetchone()[0]
        est  = ok + int((50500 - remain) * rate)
        print(f"速度   {ips*60:.0f} ID/分 → 残り約 {left:.1f}時間")
        print(f"見込み 最終 約{est:,}枚 / 約{est*55/1024/1024:.1f}GB")
PY
