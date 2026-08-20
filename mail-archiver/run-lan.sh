#!/bin/bash
# 社内LAN（＋Tailscale）へ出して、スマホから見るための起動。**メインPC専用**。
# サブPCでは使わない（常駐・LAN共有はメインPCの役割）。
cd "$(dirname "$0")"

# パスワードが無いまま外に出さない。ここで止める（アプリ側でも二重に止めている）
if ! grep -qE '^UI_PASSWORD=.+' .env.mail-archiver 2>/dev/null; then
  echo "UI_PASSWORD が未設定です。.env.mail-archiver に書いてから起動してください。" >&2
  echo "（メール本文を扱うため、パスワード無しでLANには出しません）" >&2
  exit 1
fi

if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
fi
exec .venv/bin/streamlit run app.py --server.port 8535 --server.address 0.0.0.0 --server.headless true
