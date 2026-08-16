#!/bin/bash
# 管理画面（Streamlit）起動。port 8540 / 0.0.0.0（社内LAN・要パスワード認証）。
#
# claude を subprocess 呼び出しするため、venv Python ではなく /usr/bin/python3 を使う
# （venv Python + launchd 常時起動 の組み合わせで claude が SIGSEGV(-11) で落ちるため。
#   詳細は feedback_claude_subprocess.md / CLAUDE.md 参照）。
cd "$(dirname "$0")"
PY=/usr/bin/python3
export PATH="/opt/homebrew/bin:$HOME/.local/bin:/usr/local/bin:$PATH"
if ! "$PY" -c "import streamlit, pandas" 2>/dev/null; then
  "$PY" -m pip install --user -q -r requirements.txt
fi
exec "$PY" -m streamlit run app.py \
  --server.port 8540 --server.address 0.0.0.0 --server.headless true
