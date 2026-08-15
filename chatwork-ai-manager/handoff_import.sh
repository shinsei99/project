#!/bin/bash
# 機密引き継ぎ（受け取り側）: 個人Dropboxの機密tarを展開してこのアプリに戻す。
# 事前に `cd ~ && git pull origin main` でコードを取得しておくこと。
set -e
cd "$(dirname "$0")"

DB_PERSONAL="$HOME/Library/CloudStorage/Dropbox-個人"
SRC="$DB_PERSONAL/chatwork-ai-manager-handoff"
TAR="$SRC/chatwork-ai-manager-secret.tar"

if [ ! -f "$TAR" ]; then
  echo "機密tarが見つかりません: $TAR" >&2
  echo "（メインPCで handoff_export.sh を実行し、Dropboxの同期を待ってください）" >&2
  exit 1
fi

# 既存DBがあれば安全のためバックアップ
if [ -f data/app.db ]; then
  ts=$(date '+%Y%m%d-%H%M%S')
  mkdir -p data/_backup
  cp data/app.db "data/_backup/app.db.$ts" 2>/dev/null || true
  echo "既存DBをバックアップ: data/_backup/app.db.$ts"
fi

echo "機密を展開しています…"
tar xf "$TAR"

# ngrok authtoken を復元（あれば）
if [ -f "$SRC/ngrok.yml" ]; then
  mkdir -p "$HOME/Library/Application Support/ngrok"
  cp "$SRC/ngrok.yml" "$HOME/Library/Application Support/ngrok/ngrok.yml"
  echo "ngrok authtoken を復元しました"
fi

echo ""
echo "展開完了。次の手順:"
echo "  1) /usr/bin/python3 -m pip install --user -r requirements.txt"
echo "  2) claude CLI にログイン済みか確認（claude --version / 未ログインなら claude でログイン）"
echo "  3) bash install-launchd.sh   （4サービス常駐起動）"
echo "  4) curl -s -o /dev/null -w '%{http_code}' http://localhost:8529/  → 200 を確認"
echo ""
echo "⚠️ メインPC側の worker/ngrok を停止してから起動すること（二重起動・二重返信の防止）。"
