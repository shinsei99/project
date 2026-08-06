#!/bin/bash
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
fi
# ツール分類（社内LAN共有なし）＝ localhost バインド（--server.address 指定なし）
exec .venv/bin/streamlit run app.py --server.port 8527 --server.headless true
