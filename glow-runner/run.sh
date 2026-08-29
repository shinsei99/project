#!/bin/bash
# グロウランナー — 手元で開くだけの静的サーバー（127.0.0.1 のみ。LANには出さない）
cd "$(dirname "$0")" || exit 1
PORT="${PORT:-8899}"
if lsof -nP -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; then
  echo "すでに起動しています → http://127.0.0.1:$PORT/index.html"
else
  nohup python3 -m http.server "$PORT" --bind 127.0.0.1 >/tmp/glow-runner-$PORT.log 2>&1 &
  sleep 1
  echo "起動しました → http://127.0.0.1:$PORT/index.html"
fi
open "http://127.0.0.1:$PORT/index.html"
