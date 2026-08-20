#!/bin/bash
# メールアーカイバ 閲覧UI。**127.0.0.1 固定**（メール本文＝個人情報を社内LANに出さない）
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
fi
exec .venv/bin/streamlit run app.py --server.port 8535 --server.address 127.0.0.1 --server.headless true
