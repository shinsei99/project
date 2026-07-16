#!/bin/bash
cd "$(dirname "$0")"
# launchd は最小PATHしか渡さないため、Homebrew/nodenv等の一般的な場所を明示的に追加する
export PATH="/usr/local/bin:/opt/homebrew/bin:$HOME/.nodenv/shims:$PATH"
if [ ! -d node_modules ]; then
  npm install
fi
if [ ! -d dist ]; then
  npm run build
fi
exec npx vite preview
