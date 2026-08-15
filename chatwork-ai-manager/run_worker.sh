#!/bin/bash
# 常時起動デーモン（ポーリング→解析→監督→スケジューラ）。
# claude を subprocess 呼び出しするため /usr/bin/python3 を使う（run.sh と同じ理由）。
cd "$(dirname "$0")"
PY=/usr/bin/python3
export PATH="/opt/homebrew/bin:$HOME/.local/bin:/usr/local/bin:$PATH"
if ! "$PY" -c "import streamlit, pandas" 2>/dev/null; then
  "$PY" -m pip install --user -q -r requirements.txt
fi
exec "$PY" worker.py
