#!/bin/bash
# KeyLine を常駐に登録する（メインPCのみ）。
#
# ⚠️ サブPCでは実行しないこと。CLAUDE.md の役割分担どおり、
#    常駐＋社内LAN共有はメインPC（Mac mini）だけの担当。
#    サブPCで画面が要るときは ./run.sh で都度起動する。

set -e
cd "$(dirname "$0")"
LA="$HOME/Library/LaunchAgents"
mkdir -p "$LA" "$HOME/keyline/logs"

for f in com.shinsei.keyline com.shinsei.keyline-purge; do
  cp "$f.plist" "$LA/$f.plist"
  launchctl unload "$LA/$f.plist" 2>/dev/null || true
  launchctl load  "$LA/$f.plist"
  echo "  ✅ $f を登録しました"
done

sleep 3
echo ""
echo "待ち受け確認（*:8534 なら社内LANに公開されている）:"
lsof -nP -iTCP:8534 -sTCP:LISTEN || echo "  ⚠️ 起動していません。logs/stderr.log を見てください"
