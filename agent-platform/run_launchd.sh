#!/bin/bash
# 社内共有・launchd常駐用（0.0.0.0）。開発時のローカルは run.sh(127.0.0.1)を使う。
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:$HOME/.local/bin:/usr/local/bin:$PATH"
[ -d .venv ] || { python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; }
exec .venv/bin/streamlit run app.py --server.port 8532 --server.address 0.0.0.0 --server.headless true
