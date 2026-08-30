#!/bin/bash
# GrowLog（成長記録アプリ）— 開発サーバー。ツール分類なので 127.0.0.1 のみ（LANに出さない）
cd "$(dirname "$0")" || exit 1
[ -d node_modules ] || npm install
exec npm run dev
