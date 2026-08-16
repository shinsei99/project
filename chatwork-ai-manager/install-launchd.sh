#!/bin/bash
# chatwork-ai-manager を launchd に常時起動登録する（2サービス）。
#   com.shinsei.chatwork-ai-manager         … 管理画面 Streamlit (run.sh, port 8540, 0.0.0.0)
#   com.shinsei.chatwork-ai-manager-worker  … 常時起動デーモン (run_worker.sh)
# 冪等: 何度実行してもOK（unload→load）。別PCでも $HOME 基準で動く。
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
LA="$HOME/Library/LaunchAgents"
LOGS="$HOME/Library/Logs"
mkdir -p "$LA" "$LOGS"

register() {
  LABEL="$1"; SCRIPT="$2"
  PLIST="$LA/$LABEL.plist"
  chmod +x "$DIR/$SCRIPT"
  cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Label</key><string>$LABEL</string>
	<key>ProgramArguments</key>
	<array><string>/bin/bash</string><string>$DIR/$SCRIPT</string></array>
	<key>WorkingDirectory</key><string>$DIR</string>
	<key>RunAtLoad</key><true/>
	<key>KeepAlive</key><true/>
	<key>StandardOutPath</key><string>$LOGS/$LABEL.log</string>
	<key>StandardErrorPath</key><string>$LOGS/$LABEL.err.log</string>
</dict>
</plist>
PLISTEOF
  plutil -lint "$PLIST" >/dev/null
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  echo "OK: $LABEL 登録・起動（$DIR/$SCRIPT）"
}

register "com.shinsei.chatwork-ai-manager"         "run.sh"
register "com.shinsei.chatwork-ai-manager-worker"  "run_worker.sh"
register "com.shinsei.chatwork-ai-manager-line"    "run_line_webhook.sh"
register "com.shinsei.chatwork-ai-manager-ngrok"   "run_ngrok.sh"

echo ""
echo "確認: launchctl list | grep chatwork-ai-manager"
echo "画面: http://localhost:8540 （社内LAN: http://192.168.1.105:8540）"
echo "LINE: https://<ngrok_domain>/line/webhook"
