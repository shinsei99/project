#!/bin/bash
# App Store 用スクリーンショットを、シミュレータから撮る（タップ不要）。
#
# ios/App/App/public/app.js の末尾に「撮影専用の起動処理」を足したビルドを作り、
# 画面ごとに1回ずつ起動して simctl で撮る。**www/ は触らない。**
# 撮り終わったら public/app.js を www/app.js で上書きして元に戻す。
set -euo pipefail
cd /Users/apple/keyline/keytag

SP=$(dirname "$0")
OUT="$SP/shots"
UDID=5E2E9348-B744-409E-B43E-471FB7E42385
BUNDLE=com.shinsei99.keytag
PUB=ios/App/App/public/app.js

mkdir -p "$OUT"

for SHOT in "$@"; do
  echo "── $SHOT ──"
  cp www/app.js "$PUB"
  sed "s/__SHOT__/$SHOT/" "$SP/shot-boot.js" >> "$PUB"

  xcodebuild -project ios/App/App.xcodeproj -scheme App -configuration Debug \
    -destination "platform=iOS Simulator,id=$UDID" -derivedDataPath build-sim \
    -allowProvisioningUpdates build > "$SP/shot-build.log" 2>&1 \
    || { echo "  ❌ ビルド失敗（$SP/shot-build.log）"; tail -5 "$SP/shot-build.log"; exit 1; }

  xcrun simctl terminate "$UDID" "$BUNDLE" >/dev/null 2>&1 || true
  xcrun simctl install "$UDID" build-sim/Build/Products/Debug-iphonesimulator/App.app
  xcrun simctl launch "$UDID" "$BUNDLE" >/dev/null
  python3 -c "import time; time.sleep(5)"
  xcrun simctl io "$UDID" screenshot "$OUT/$SHOT.png" >/dev/null 2>&1
  echo "  → $OUT/$SHOT.png  $(sips -g pixelWidth -g pixelHeight "$OUT/$SHOT.png" | tail -2 | tr -d ' \n')"
done

# 元に戻す（撮影用の細工を残さない）
cp www/app.js "$PUB"
echo "public/app.js を www/app.js で戻しました"
