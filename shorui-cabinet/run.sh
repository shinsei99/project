#!/bin/bash
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
fi
# 不動産カテゴリ・社内LAN共有あり＝ 0.0.0.0 バインド（他PCから 192.168.1.105:8528 で開く）。
# 個人情報（物件名・所在）を含むため、社内WiFi内のみでの利用が前提。
exec .venv/bin/streamlit run app.py --server.port 8528 --server.headless true --server.address 0.0.0.0
