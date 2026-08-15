#!/bin/bash
# LINE Webhook 受信サーバー（port 8530）。claude を subprocess 呼び出すため /usr/bin/python3。
# ポートバインドで単一化される（2つ目は EADDRINUSE で失敗）。
cd "$(dirname "$0")"
PY=/usr/bin/python3
export PATH="/opt/homebrew/bin:$HOME/.local/bin:/usr/local/bin:$PATH"
if ! "$PY" -c "import streamlit, pandas" 2>/dev/null; then
  "$PY" -m pip install --user -q -r requirements.txt
fi
exec "$PY" line_webhook.py
