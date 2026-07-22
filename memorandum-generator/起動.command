#!/bin/bash
cd "$(dirname "$0")"
# 既存の8524を止めてから起動
lsof -ti :8524 2>/dev/null | xargs kill -9 2>/dev/null
python3 -m streamlit run app.py --server.port 8524 --server.address 0.0.0.0
