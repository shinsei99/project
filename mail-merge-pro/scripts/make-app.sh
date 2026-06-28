#!/bin/zsh
#
# make-app.sh
# MailMergePro を .app バンドル化してデスクトップに配置するスクリプト。
#
# やること:
#  1. リリースビルド（swift build -c release）
#  2. "Mail Merge Pro.app" のバンドル構造を作成
#  3. 実行ファイルと Info.plist を配置
#  4. アドホック署名（自動化許可を安定させるため、固定バンドルIDで署名）
#  5. デスクトップへ配置
#
set -e

APP_NAME="Mail Merge Pro"
BUNDLE_ID="com.shinsei.mailmergepro"
EXEC_NAME="MailMergePro"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEST_DIR="$HOME/Desktop"
APP_PATH="$DEST_DIR/$APP_NAME.app"

echo "▶ ユニバーサルビルド中（Apple Silicon + Intel）..."
cd "$PROJECT_DIR"
swift build -c release --arch arm64 --arch x86_64

# ユニバーサルビルドの成果物パスを解決（複数 --arch 指定時は apple/Products 配下）。
if [[ -f ".build/apple/Products/Release/$EXEC_NAME" ]]; then
  BUILT_BIN=".build/apple/Products/Release/$EXEC_NAME"
else
  BUILT_BIN=".build/release/$EXEC_NAME"
fi

echo "▶ アプリバンドルを作成: $APP_PATH"
rm -rf "$APP_PATH"
mkdir -p "$APP_PATH/Contents/MacOS"
mkdir -p "$APP_PATH/Contents/Resources"

# 実行ファイルを配置。
cp "$BUILT_BIN" "$APP_PATH/Contents/MacOS/$EXEC_NAME"

# アイコンがあれば配置（scripts/AppIcon.icns）。
if [[ -f "$PROJECT_DIR/scripts/AppIcon.icns" ]]; then
  cp "$PROJECT_DIR/scripts/AppIcon.icns" "$APP_PATH/Contents/Resources/AppIcon.icns"
  ICON_KEY="<key>CFBundleIconFile</key><string>AppIcon</string>"
else
  ICON_KEY=""
fi

# Info.plist を生成。
cat > "$APP_PATH/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key><string>$APP_NAME</string>
    <key>CFBundleDisplayName</key><string>$APP_NAME</string>
    <key>CFBundleIdentifier</key><string>$BUNDLE_ID</string>
    <key>CFBundleExecutable</key><string>$EXEC_NAME</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleVersion</key><string>1</string>
    <key>CFBundleShortVersionString</key><string>1.0</string>
    <key>LSMinimumSystemVersion</key><string>14.0</string>
    <key>NSHighResolutionCapable</key><true/>
    <key>NSPrincipalClass</key><string>NSApplication</string>
    <key>LSApplicationCategoryType</key><string>public.app-category.productivity</string>
    <key>NSAppleEventsUsageDescription</key><string>メールの作成・送信のために Apple Mail を操作します。</string>
    $ICON_KEY
</dict>
</plist>
PLIST

# アドホック署名（自動化許可・TCC を安定させる）。
echo "▶ アドホック署名..."
codesign --force --deep --sign - --identifier "$BUNDLE_ID" "$APP_PATH"

echo "✅ 完了: $APP_PATH"
