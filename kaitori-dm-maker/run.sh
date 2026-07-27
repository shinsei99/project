#!/bin/bash
cd "$(dirname "$0")"
# 社内共有不要（ツール）。localhostバインド＝このMacからのみアクセス可
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
fi
exec .venv/bin/streamlit run app.py --server.port 8526 --server.headless true
