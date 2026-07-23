#!/bin/bash
# Dropbox同期でxattrが消えるたびに横断ファイル検索.lnk のアイコンを再設定する
# GUIセッション経由の osascript (AppKit) で書き込む

LNK="/Users/apple/Library/CloudStorage/Dropbox-大京商事　株式会社/共有フォルダ/（★必読★）新共有フォルダ/横断ファイル検索.lnk"
ICON="/Users/apple/Desktop/社内ツール/横断ファイル検索.app/Contents/Resources/AppIcon.icns"
LOG="$HOME/gyomu-manual/logs/lnk-icon.log"

[ -f "$LNK" ] || exit 0

sleep 2  # Dropboxが書き込み完了するまで少し待つ

RESULT=$(osascript <<SCPT
use framework "AppKit"
use scripting additions
set theIcon to current application's NSImage's alloc()'s initWithContentsOfFile_("$ICON")
set ws to current application's NSWorkspace's sharedWorkspace()
set ok to ws's setIcon:theIcon forFile:"$LNK" options:0
return ok as text
SCPT
)

echo "$(date '+%Y-%m-%d %H:%M:%S') result=$RESULT" >> "$LOG"
