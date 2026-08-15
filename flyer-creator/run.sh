#!/bin/bash
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
fi
# 自分専用＝ localhost バインド。
# 注意: --server.address を省略すると Streamlit の既定は 0.0.0.0（＝LANに公開）なので必ず明示する。
exec .venv/bin/streamlit run app.py --server.port 8529 --server.headless true --server.address 127.0.0.1
