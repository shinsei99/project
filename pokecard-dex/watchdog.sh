#!/bin/bash
# 取得が落ちていたら自動で再開する。cron や手動で回す用。
cd "$(dirname "$0")"
if pgrep -f crawl_official > /dev/null; then exit 0; fi
REMAIN=$(python3 -c "
import sqlite3
con=sqlite3.connect('data/cards.db')
done=con.execute(\"SELECT COUNT(*) FROM official WHERE status IN ('ok','gone')\").fetchone()[0]
print(50500-done)
" 2>/dev/null)
if [ "${REMAIN:-0}" -gt 20 ]; then
  echo "$(date '+%F %T') 停止を検知 → 再開（残り約${REMAIN}件）" >> data/watchdog.log
  nohup .venv/bin/python crawl_official.py 1 50500 desc >> data/crawl.log 2>&1 &
fi
