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

# 毎日決まった時刻に1回だけ走らせる（常駐ではない）。KeepAlive は付けない。
# ★ /bin/bash 経由にすること: Dropbox(CloudStorage) の TCC 責任プロセスが bash になるため。
#    plist から /usr/bin/python3 を直接叩くと読めなくなる。
register_daily() {
  LABEL="$1"; SCRIPT="$2"; HOUR="$3"; MIN="$4"
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
	<key>RunAtLoad</key><false/>
	<key>StartCalendarInterval</key>
	<dict><key>Hour</key><integer>$HOUR</integer><key>Minute</key><integer>$MIN</integer></dict>
	<key>StandardOutPath</key><string>$LOGS/$LABEL.log</string>
	<key>StandardErrorPath</key><string>$LOGS/$LABEL.err.log</string>
</dict>
</plist>
PLISTEOF
  plutil -lint "$PLIST" >/dev/null
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  echo "OK: $LABEL 登録（毎日 $HOUR:$(printf %02d "$MIN")・$DIR/$SCRIPT）"
}

register "com.shinsei.chatwork-ai-manager"         "run.sh"
register "com.shinsei.chatwork-ai-manager-worker"  "run_worker.sh"
register "com.shinsei.chatwork-ai-manager-line"    "run_line_webhook.sh"
register "com.shinsei.chatwork-ai-manager-ngrok"   "run_ngrok.sh"

# 夜間のOCR一括取込（毎日 01:00 開始・3時間で打ち切り＝04:00には終わる）
# 02:00 の com.shinsei.mail-archiver-sync と16分ほど重なるが、
# あちらは IMAP＋SQLite・こちらは claude CLI＋PDF描画で取り合う資源が無い（2026-08-27 実測）。
register_daily "com.shinsei.chatwork-ai-manager-ocr" "run_ocr_nightly.sh" 1 0

echo ""
echo "確認: launchctl list | grep chatwork-ai-manager"
echo "画面: http://localhost:8540 （社内LAN: http://192.168.1.105:8540）"
echo "LINE: https://<ngrok_domain>/line/webhook"
