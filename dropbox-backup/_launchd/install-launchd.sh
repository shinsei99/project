#!/bin/bash
# 週1回のバックアップを launchd に登録する。★メインPC（Mac mini）でだけ叩くこと。
set -eu

LABEL="com.shinsei.dropbox-backup"
SRC="$(cd "$(dirname "$0")" && pwd)/$LABEL.plist"
DST="$HOME/Library/LaunchAgents/$LABEL.plist"

mkdir -p "$HOME/Library/LaunchAgents"
cp "$SRC" "$DST"

# bootout → bootstrap（kickstart はディスクの plist を読み直さないので使わない）
launchctl bootout   "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$DST"

echo "登録しました: $LABEL"
launchctl print "gui/$(id -u)/$LABEL" | grep -E "state|program|path" | head
echo
echo "次回の実行: 毎週日曜 6:00"
echo "手で1回試すなら: launchctl kickstart -k gui/\$(id -u)/$LABEL"
