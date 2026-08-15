#!/bin/bash
# マルチプロダクション（agent-platform）の起動スクリプト
# 分類は「ツール」のため 127.0.0.1 バインド（社内LANには公開しない）
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "初回起動: .venv を作成してライブラリを入れます（数分かかります）"
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
fi

exec .venv/bin/streamlit run app.py \
  --server.port 8532 \
  --server.address 127.0.0.1 \
  --server.headless true
