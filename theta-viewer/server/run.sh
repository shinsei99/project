#!/bin/bash
cd "$(dirname "$0")"
# FTP APIサーバー（Express、port 8523はserver.js内で定義）。node/npmのパスを明示。
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
if [ ! -d node_modules ]; then npm install; fi
exec node server.js
