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

# 毎週決まった曜日・時刻に1回だけ走らせる。register_daily に曜日を足しただけ。
# ★StandardOutPath を "$LABEL.log" にしないこと。スクリプト側の log() が tee で
#   同じファイルへ書くので、二重化する（2026-08-27 に別ジョブで踏んだ）。
register_weekly() {
  LABEL="$1"; SCRIPT="$2"; WDAY="$3"; HOUR="$4"; MIN="$5"
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
	<dict><key>Weekday</key><integer>$WDAY</integer><key>Hour</key><integer>$HOUR</integer><key>Minute</key><integer>$MIN</integer></dict>
	<key>StandardOutPath</key><string>$LOGS/$LABEL.out.log</string>
	<key>StandardErrorPath</key><string>$LOGS/$LABEL.err.log</string>
</dict>
</plist>
PLISTEOF
  plutil -lint "$PLIST" >/dev/null
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  echo "OK: $LABEL 登録（毎週 曜日$WDAY $HOUR:$(printf %02d "$MIN")・$DIR/$SCRIPT）"
}

register "com.shinsei.chatwork-ai-manager"         "run.sh"
register "com.shinsei.chatwork-ai-manager-worker"  "run_worker.sh"
register "com.shinsei.chatwork-ai-manager-line"    "run_line_webhook.sh"
register "com.shinsei.chatwork-ai-manager-ngrok"   "run_ngrok.sh"

# 夜間のOCR一括取込（毎日 02:00 開始・2時間で打ち切り＝04:00には終わる）
# メール取込＋翻訳は00:30〜01:00に前倒ししたので、こちらと重ならない（2026-08-28）。旧: 
# あちらは IMAP＋SQLite・こちらは claude CLI＋PDF描画で取り合う資源が無い（2026-08-27 実測）。
register_daily "com.shinsei.chatwork-ai-manager-ocr" "run_ocr_nightly.sh" 2 0

# 共有フォルダの棚卸し（毎週日曜 5:00）。2026-09-03 に file-finder から引き取った。
# ★このジョブは廃止できない。作られる「全ファイル一覧.xlsx」は
#   ①このアプリの知識索引 ②find_files ツールの元データ ③全社員が共有フォルダで開く実物
#   の3役を兼ねている。file-finder（8520）を消したときに一緒に消しかけた。
register_weekly "com.shinsei.chatwork-ai-manager-inventory" "run_inventory_weekly.sh" 0 5 0

echo ""
echo "確認: launchctl list | grep chatwork-ai-manager"
echo "画面: http://localhost:8540 （社内LAN: http://192.168.1.105:8540）"
echo "LINE: https://<ngrok_domain>/line/webhook"
