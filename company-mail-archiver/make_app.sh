#!/bin/bash
# Desktop/社内ツール の `.app`（ブラウザで画面を開くだけのランチャ）を作り直す。
#
#   ./make_app.sh
#
# ★なぜスクリプトにするか（2026-08-31 に踏んだ）
#   シェルで `.app` の中身を書いただけでは **LaunchServices に登録されない**。
#   Finder でダブルクリックしても何も起きず、`open` は
#   `_LSOpenURLsWithCompletionHandler() failed with error -10810` で落ちる。
#   **最後に `lsregister -f` を叩くまでが「アプリを作る」作業**。手順に混ぜておかないと必ず忘れる。
set -eu
cd "$(dirname "$0")"

NAME="社内メールアーカイバ"
PORT=8538
BUNDLE_ID="com.shinsei.company-mail-archiver"
APP="$HOME/Desktop/社内ツール/${NAME}.app"
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"

# アイコンが無ければ作る（PIL と iconutil を使う）
[ -f icon-src/AppIcon.icns ] || /usr/bin/python3 icon-src/make_icon.py

mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/MacOS/launcher" <<EOF
#!/bin/zsh
open "http://localhost:${PORT}"
EOF
chmod +x "$APP/Contents/MacOS/launcher"

cat > "$APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDisplayName</key><string>${NAME}</string>
  <key>CFBundleExecutable</key><string>launcher</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundleIdentifier</key><string>${BUNDLE_ID}</string>
  <key>CFBundleName</key><string>${NAME}</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
EOF
plutil -lint "$APP/Contents/Info.plist" >/dev/null

cp icon-src/AppIcon.icns "$APP/Contents/Resources/AppIcon.icns"
touch "$APP"

# ★ここが肝。登録しないとダブルクリックで開かない
"$LSREGISTER" -f "$APP"
echo "作りました: $APP"
echo "確認: open \"$APP\"  →  http://localhost:${PORT} が開けば成功"
