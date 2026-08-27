#!/bin/bash
# メールアーカイバ 閲覧UI。**127.0.0.1 固定**（メール本文＝個人情報を社内LANに出さない）。
#
# ★ venv ではなく /usr/bin/python3 で起動する。AI検索が claude をサブプロセス呼び出しするが、
#   Homebrew/xcode 由来の venv Python を launchd 経由で動かした状態で claude を呼ぶと
#   fork/exec 後に SIGSEGV(-11) で落ちる（[[feedback_claude_subprocess]]）。
#   外部依存は streamlit だけで、/usr/bin/python3 にグローバル導入済み。
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:$PATH"   # ai_query が claude を見つけられるように

if ! /usr/bin/python3 -c "import streamlit" 2>/dev/null; then
  echo "streamlit が /usr/bin/python3 に見つかりません。次で入れてください:" >&2
  echo "  /usr/bin/python3 -m pip install --user streamlit" >&2
  exit 1
fi

exec /usr/bin/python3 -m streamlit run app.py \
  --server.port 8535 --server.address 127.0.0.1 --server.headless true
