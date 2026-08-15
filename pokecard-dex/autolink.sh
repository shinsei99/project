#!/bin/bash
# 取得が進むたびに図鑑へ反映する。取得プロセスが終わるまで10分おきに回る。
cd "$(dirname "$0")"
while pgrep -f crawl_official > /dev/null; do
  ~/photo-inpainter/.venv/bin/python link_official.py >> data/autolink.log 2>&1
  ~/photo-inpainter/.venv/bin/python merge_official.py >> data/autolink.log 2>&1
  sleep 600
done
# 最後にもう一度
~/photo-inpainter/.venv/bin/python link_official.py >> data/autolink.log 2>&1
~/photo-inpainter/.venv/bin/python merge_official.py >> data/autolink.log 2>&1
echo "$(date '+%F %T') 取得完了に伴い最終反映" >> data/autolink.log
