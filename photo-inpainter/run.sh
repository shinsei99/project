#!/bin/bash
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
fi
# 不動産カテゴリ・完成済みのため社内LAN共有（0.0.0.0 バインド）
exec .venv/bin/streamlit run app.py --server.port 8506 --server.address 0.0.0.0 --server.headless true
