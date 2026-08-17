#!/bin/bash
# KeyLine 起動スクリプト
#
# 不動産カテゴリ＝社内LAN共有ありなので 0.0.0.0 にバインドする。
# （CLAUDE.md「バインド先のルール」参照。省略すると既定が何かに依存するので必ず明示する）
#
# Python は /usr/bin/python3 固定。venv の Python だと OCR で呼ぶ `claude`
# サブプロセスが SIGSEGV する既知の問題があるため（CLAUDE.md 参照）。

cd "$(dirname "$0")" || exit 1

PORT=8534
HOST=0.0.0.0
PY=/usr/bin/python3

# pip install --user で入れた fastapi/uvicorn を確実に見つけさせる
export PYTHONPATH="$HOME/Library/Python/3.9/lib/python/site-packages:$PYTHONPATH"

if ! $PY -c "import fastapi, uvicorn" 2>/dev/null; then
  echo "依存が入っていません。次を実行してください:"
  echo "  /usr/bin/python3 -m pip install --user fastapi 'uvicorn[standard]' python-multipart"
  exit 1
fi

# DBが無ければ作る（マイグレーションもここで当たる）
$PY db.py >/dev/null || exit 1

if ! $PY -c "
import sys; sys.path.insert(0,'.')
import db; con = db.connect()
sys.exit(0 if con.execute('SELECT COUNT(*) FROM users').fetchone()[0] else 1)
" 2>/dev/null; then
  echo "──────────────────────────────────────────────"
  echo " まだアカウントがありません。先に初期設定をしてください:"
  echo "   /usr/bin/python3 seed.py"
  echo "──────────────────────────────────────────────"
  # launchd は KeepAlive で即座に再起動をかけるため、そのまま exit すると
  # 1秒間隔で回り続けてログを埋める。少し待ってから落ちる。
  sleep 60
  exit 1
fi

# ★NFCタグに書き込むURLのホスト。
#   このMacは en0=192.168.1.140 / en1=192.168.1.105 の2枚刺しで、
#   CLAUDE.md の「配布は .105 で統一」に従う（自動検出だと en0 の .140 が返る）。
#   ここを間違えたURLをタグに書くと、タグを物理的に書き直すことになる。
LAN_IP=$(ipconfig getifaddr en1 2>/dev/null || ipconfig getifaddr en0 2>/dev/null || echo 127.0.0.1)
export KEYLINE_BASE_URL="${KEYLINE_BASE_URL:-http://${LAN_IP}:${PORT}}"

echo "KeyLine を起動します"
echo "  管理画面   : ${KEYLINE_BASE_URL}/"
echo "  タグURLの形 : ${KEYLINE_BASE_URL}/t/<トークン>"
exec $PY -m uvicorn app:app --host "$HOST" --port "$PORT" --log-level warning
