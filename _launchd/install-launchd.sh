#!/bin/bash
# ============================================================
# launchd 登録スクリプト（file-finder / owner-payout-tracker）
#   メインPC・サブPC 両方で使える。git pull 後にこれを実行するだけ。
#   $HOME を使うのでユーザー名に依存しない。冪等（何度実行してもOK）。
# ============================================================
set -e

LA="$HOME/Library/LaunchAgents"
LOGS="$HOME/Library/Logs"
mkdir -p "$LA" "$LOGS"

# 対象: "ラベル|アプリフォルダ名"
APPS=(
  "com.shinsei.file-finder|file-finder"
  "com.shinsei.owner-payout-tracker|owner-payout-tracker"
  "com.shinsei.gyomu-manual|gyomu-manual"
  "com.shinsei.madori-tracer|madori-tracer"
  "com.shinsei.madori-tracer-editor|madori-tracer/editor"
  "com.shinsei.memorandum-generator|memorandum-generator"
)

for entry in "${APPS[@]}"; do
  LABEL="${entry%%|*}"
  DIR="$HOME/${entry##*|}"
  PLIST="$LA/$LABEL.plist"

  if [ ! -f "$DIR/run.sh" ]; then
    echo "!! $DIR/run.sh が無い（git pull 済みか確認）。スキップ: $LABEL"
    continue
  fi
  chmod +x "$DIR/run.sh"

  cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Label</key>
	<string>$LABEL</string>
	<key>ProgramArguments</key>
	<array>
		<string>/bin/bash</string>
		<string>$DIR/run.sh</string>
	</array>
	<key>WorkingDirectory</key>
	<string>$DIR</string>
	<key>RunAtLoad</key>
	<true/>
	<key>KeepAlive</key>
	<true/>
	<key>StandardOutPath</key>
	<string>$LOGS/$LABEL.log</string>
	<key>StandardErrorPath</key>
	<string>$LOGS/$LABEL.err.log</string>
</dict>
</plist>
PLISTEOF

  plutil -lint "$PLIST" >/dev/null
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  echo "OK: $LABEL 登録・起動（$DIR/run.sh）"
done

echo
echo "=== launchd 登録確認 ==="
launchctl list | grep -E "file-finder|owner-payout|madori-tracer|gyomu-manual|memorandum-generator" || echo "(まだ起動処理中の可能性あり)"
echo
echo "※ file-finder/owner-payout-tracker/madori-tracer は初回 .venv 自動作成のため、"
echo "   ポート(8519/8520/8511)が上がるまで数十秒かかることがあります。"
echo "※ gyomu-manual は python3 の標準モジュールのみ使用（即時起動）。"
echo "※ madori-tracer-editor(port 5175) は Node.js/npm が必要。初回は npm install→build のため数分かかることがあります。"
