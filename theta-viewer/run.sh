#!/bin/bash
cd "$(dirname "$0")"
# Vite製SPA。launchdは最小PATHしか渡さないためnode/npmのパスを明示（[[reference-cross-pc-handoff]]）
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
if [ ! -d node_modules ]; then npm install; fi
# 起動のたびに必ず再ビルド（古いdistを配信し続けないように）
npm run build
exec npx vite preview --host 0.0.0.0 --port 8512
