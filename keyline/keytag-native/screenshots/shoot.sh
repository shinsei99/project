#!/bin/bash
# ストア用スクリーンショットを、ネイティブ版（keytag-native）から撮る。
#
#   ./screenshots/shoot.sh
#
# 旧 Capacitor 版の `keytag/screenshots/shoot.sh` は Chrome で www/ を撮っていた。
# ネイティブ版には www/ が無いので、**シミュレータを撮る**方式に変えた。
#
# ★注意書きを隠している: シミュレータには NFC が無いため「この端末ではNFCを
#   使えません」が出る。実機では出ない文言なので、`KEYTAG_SHOTS=1`（DEBUG 限定）で
#   隠してから撮る。隠しているのはこの1文だけで、機能は何も変えていない。
#
# ★寸法: シミュレータの素は 1320×2868。App Store の 6.5型（APP_IPHONE_65）は
#   1284×2778 しか受け付けないので、最後に sips で直す。
set -euo pipefail

cd "$(dirname "$0")/.."
SIM="${KEYTAG_SIM:-5419B4D4-E3C1-413D-BCDD-8855DB39E9C4}"   # iPhone 17 Pro Max
APPID="com.shinsei99.keytag"
OUT="screenshots"
DD="build/dd"

echo "== ビルド（Debug・シミュレータ用）=="
xcodebuild -project KeyTag.xcodeproj -scheme KeyTag -configuration Debug \
  -destination "platform=iOS Simulator,id=$SIM" -derivedDataPath "$DD" build >/dev/null

xcrun simctl bootstatus "$SIM" -b >/dev/null 2>&1 || true
xcrun simctl install "$SIM" "$DD/Build/Products/Debug-iphonesimulator/KeyTag.app"
# 時刻を 9:41 に固定（Apple の慣習。撮り直しても絵が揺れない）
xcrun simctl status_bar "$SIM" override --time "9:41" --batteryState charged --batteryLevel 100 \
  --cellularMode active --cellularBars 4 --wifiMode active --wifiBars 3 >/dev/null 2>&1 || true

# 1枚撮る: shot <出力名> <環境変数の指定…>
shot() {
  local name="$1"; shift
  xcrun simctl terminate "$SIM" "$APPID" >/dev/null 2>&1 || true
  env "$@" SIMCTL_CHILD_KEYTAG_SHOTS=1 SIMCTL_CHILD_KEYTAG_SAMPLES=1 \
    xcrun simctl launch "$SIM" "$APPID" >/dev/null
  sleep 4
  xcrun simctl io "$SIM" screenshot "$OUT/$name.png" >/dev/null 2>&1
  sips -z 2778 1284 "$OUT/$name.png" >/dev/null      # ★1284×2778 に直す
  echo "  撮った: $OUT/$name.png"
}

echo "== 撮影 =="
# 並びの意図は keytag/store-text.md の「スクリーンショットの並び」を見ること
shot 01-read   SIMCTL_CHILD_KEYTAG_OPEN=out                              # かざして鍵が特定された画面
shot 02-ledger SIMCTL_CHILD_KEYTAG_TAB=ledger                            # 台帳の一覧
shot 03-lend   SIMCTL_CHILD_KEYTAG_OPEN=in                               # 貸出
shot 04-write  SIMCTL_CHILD_KEYTAG_DRAFT=1                               # タグに書き込む（入力済み）
shot 05-settings SIMCTL_CHILD_KEYTAG_TAB=settings                        # サーバー連携・Excel入出力

echo "== 完了 =="
ls -la "$OUT"/*.png
