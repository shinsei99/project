#!/bin/bash
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
fi
# 自分専用。カード画像の著作権は権利者に帰属するため社内LANにも公開しない
exec .venv/bin/streamlit run app.py --server.port 8537 --server.address 127.0.0.1 --server.headless true
