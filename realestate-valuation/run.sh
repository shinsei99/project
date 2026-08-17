#!/bin/bash
# claude を subprocess 呼び出しするため、venv Python ではなく /usr/bin/python3 を使う。
# （venv Python + launchd/常時起動 の組み合わせで claude が SIGSEGV(-11) で落ちるため。
#   詳細は feedback_claude_subprocess.md / CLAUDE.md 参照）
cd "$(dirname "$0")"
PY=/usr/bin/python3
# 必要パッケージをユーザー領域にインストール（未導入時のみ実体を取りに行く）
if ! "$PY" -c "import streamlit, pandas, pdfplumber, openpyxl, fitz, PIL, requests" 2>/dev/null; then
  "$PY" -m pip install --user -q -r requirements.txt
fi
exec "$PY" -m streamlit run app.py --server.port 8509 --server.address 0.0.0.0 --server.headless true
