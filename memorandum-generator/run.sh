#!/bin/bash
# launchd 用（メインMac）。ブラウザ自動起動なし・LAN公開。
cd "$(dirname "$0")"
exec python3 -m streamlit run app.py \
  --server.port 8524 \
  --server.address 0.0.0.0 \
  --server.headless true \
  --browser.gatherUsageStats false
