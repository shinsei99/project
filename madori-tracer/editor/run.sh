#!/bin/bash
cd "$(dirname "$0")"
# launchd は最小PATHしか渡さないため、Homebrew/nodenv等の一般的な場所を明示的に追加する
export PATH="/usr/local/bin:/opt/homebrew/bin:$HOME/.nodenv/shims:$PATH"
if [ ! -d node_modules ]; then
  npm install
fi
# 起動のたびに必ず再ビルドする（distが在っても古いソースを配信し続けないように。ビルドは1秒未満）
npm run build
exec npx vite preview
