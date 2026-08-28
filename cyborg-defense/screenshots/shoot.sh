#!/bin/bash
# App Store 用スクリーンショットを、シミュレータから撮る（タップ不要）。
#
# なぜタップを使わないか: このMacのターミナルには「アクセシビリティ」権限が無く、
# シミュレータへタップや ⌘V を送れない（simtap.py が使えない）。
# 代わりに、**画面の状態を作る細工を差し込んだビルド**を1画面につき1回作って撮る。
#
#   ios/App/App/public/index.html …… 撮影用に細工した版（ビルドはこれを包む）
#   www/index.html                …… 触らない（配信物の正）
#
# 撮り終わったら public/index.html を www/index.html で上書きして元に戻す。
#
# 使い方:
#   ./screenshots/shoot.sh title gate battle boss over            # iPhone
#   DEVICE=ipad ./screenshots/shoot.sh title gate battle boss over
set -euo pipefail
cd /Users/apple/cyborg-defense

SP=$(dirname "$0")
DEVICE="${DEVICE:-iphone}"
if [ "$DEVICE" = "ipad" ]; then
  UDID=4888A8EF-9F7C-465D-A2A0-11065F6D067A     # iPad Pro 13-inch (M5)
  OUT="$SP/shots-ipad"
else
  UDID=5419B4D4-E3C1-413D-BCDD-8855DB39E9C4     # iPhone 17 Pro Max
  OUT="$SP/shots"
fi
BUNDLE=com.daikyo.cyborgdefense
PUB=ios/App/App/public/index.html

mkdir -p "$OUT"
xcrun simctl boot "$UDID" 2>/dev/null || true

for SHOT in "$@"; do
  echo "── $SHOT ($DEVICE) ──"
  python3 - "$SHOT" <<'PY'
import sys
shot = sys.argv[1]
src  = open('www/index.html', encoding='utf-8').read()
boot = open('screenshots/shot-boot.js', encoding='utf-8').read().replace('__SHOT__', shot)
marker = "\n})();\n</script>"
assert src.count(marker) == 1, "差し込み位置が特定できない（IIFE の終わりが変わった？）"
open('ios/App/App/public/index.html', 'w', encoding='utf-8').write(
    src.replace(marker, "\n" + boot + marker))
PY

  # ★このアプリは Capacitor 8＝SPM なので **-project** で建てる（.xcworkspace は無い）。
  #   にゃんこアイスは Capacitor 6＝CocoaPods で -workspace が要る。アプリごとに違う
  xcodebuild -project ios/App/App.xcodeproj -scheme App -configuration Debug \
    -destination "platform=iOS Simulator,id=$UDID" -derivedDataPath build-sim \
    -allowProvisioningUpdates build > "$SP/shot-build.log" 2>&1 \
    || { echo "  ❌ ビルド失敗（$SP/shot-build.log）"; tail -8 "$SP/shot-build.log"; exit 1; }

  xcrun simctl terminate "$UDID" "$BUNDLE" >/dev/null 2>&1 || true
  xcrun simctl install "$UDID" build-sim/Build/Products/Debug-iphonesimulator/App.app
  xcrun simctl launch "$UDID" "$BUNDLE" >/dev/null
  # ★6秒だと起動画面のまま撮れて真っ黒になる（実測）。WebViewの描画まで待つ
  python3 -c "import time; time.sleep(12)"
  xcrun simctl io "$UDID" screenshot "$OUT/$SHOT.png" >/dev/null 2>&1
  echo "  → $OUT/$SHOT.png  $(sips -g pixelWidth -g pixelHeight "$OUT/$SHOT.png" | tail -2 | tr -d ' \n')"
done

cp www/index.html "$PUB"
echo "public/index.html を www/index.html で戻しました"
