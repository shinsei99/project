#!/bin/bash
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
fi
# 不動産分類＝社内LAN共有あり。他17本と揃えてバインド先を明示する
exec .venv/bin/streamlit run app.py --server.port 8519 --server.headless true --server.address 0.0.0.0
