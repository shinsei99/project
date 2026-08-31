#!/bin/bash
# 夜間ジョブ（毎日03:30）を常駐に入れる。**メインPCだけ**。
#
#   ./_launchd/install.sh
#
# ★アカウントが1つも設定されていないうちは入れないこと（何も取り込まないのに
#   動いている風に見えて、後の担当が「動いているのに増えない」と誤解する）。
# ★引数（plist）を変えたときは kickstart では反映されない。bootout → bootstrap の順で入れ直す。
set -eu
cd "$(dirname "$0")/.."
LABEL="com.shinsei.company-mail-archiver-sync"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if ! ls .env.company-mail-archiver.* >/dev/null 2>&1; then
  echo "★社員のアカウント設定が1つもありません。先に .env.company-mail-archiver.<slug> を作ってください"
  exit 1
fi
/usr/bin/python3 guards.py

cp "_launchd/$LABEL.plist" "$PLIST"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl print "gui/$(id -u)/$LABEL" | grep -E "state|program" | head -3
echo "入れました: $LABEL（毎日03:30）"
