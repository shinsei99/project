#!/bin/bash
# AIツールベース 開発サーバー。port 3004 / 127.0.0.1（ツール分類・社内共有なし）
cd "$(dirname "$0")"
exec npx next dev --hostname 127.0.0.1 --port 3004
