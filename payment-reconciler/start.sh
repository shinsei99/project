#!/bin/zsh
# 入金突合システム 起動スクリプト

cd "$(dirname "$0")"

python3 -m streamlit run app.py \
    --server.port 8514 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false \
    >> logs/streamlit.log 2>&1
