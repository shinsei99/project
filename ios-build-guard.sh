#!/bin/bash
# iOS App Store 再配信のビルド番号 衝突チェック（再発防止）
#
# 2026-07-22の事故対策：修正版を build 番号を上げずに再アーカイブすると
# App Store Connect が「build は既存」で弾き、古いビルドが配信されてしまう。
# このスクリプトは、対象アプリのプロジェクト上の CURRENT_PROJECT_VERSION と、
# ローカルの既存 Xcode アーカイブ（＝過去にアップロードした可能性のあるビルド）を比較し、
# 「現在の番号 <= 既存の最大番号」なら衝突リスクとして警告する。
#
# 使い方:
#   ./ios-build-guard.sh <app-folder>          # チェックのみ
#   ./ios-build-guard.sh <app-folder> --bump   # 衝突していたら最大+1へ自動更新
#
# 例:
#   ./ios-build-guard.sh photo-remake
#   ./ios-build-guard.sh neon-blocks --bump

set -euo pipefail

APP="${1:-}"
BUMP="${2:-}"
if [[ -z "$APP" ]]; then
  echo "usage: $0 <app-folder> [--bump]" >&2
  exit 2
fi

ROOT="/Users/apple"
DIR="$ROOT/$APP"
[[ -d "$DIR" ]] || { echo "❌ フォルダなし: $DIR" >&2; exit 2; }

# pbxproj を探す（ネイティブ or Capacitor）
PBX=""
for cand in "$DIR"/*.xcodeproj/project.pbxproj "$DIR"/ios/App/App.xcodeproj/project.pbxproj; do
  [[ -f "$cand" ]] && PBX="$cand" && break
done
[[ -n "$PBX" ]] || { echo "❌ project.pbxproj が見つからない（$DIR）" >&2; exit 2; }

# バンドルIDと現在のビルド番号（複数configの最大）
BUNDLE=$(grep -Eo 'PRODUCT_BUNDLE_IDENTIFIER = [^;]+;' "$PBX" | head -1 | sed -E 's/PRODUCT_BUNDLE_IDENTIFIER = //; s/;//; s/ //g' || true)
CUR=$(grep -Eo 'CURRENT_PROJECT_VERSION = [0-9]+' "$PBX" | grep -Eo '[0-9]+' | sort -n | tail -1 || echo "")
MKT=$(grep -Eo 'MARKETING_VERSION = [^;]+;' "$PBX" | head -1 | sed -E 's/MARKETING_VERSION = //; s/;//; s/ //g' || echo "?")

echo "アプリ:      $APP"
echo "pbxproj:     $PBX"
echo "Bundle ID:   ${BUNDLE:-(不明)}"
echo "表示バージョン: $MKT"
echo "現在のbuild番号: ${CUR:-(不明)}"

if [[ -z "${CUR:-}" || -z "${BUNDLE:-}" ]]; then
  echo "⚠ ビルド番号かBundle IDを取得できず。手動で確認してください。" >&2
  exit 1
fi

# 既存アーカイブから同じBundle IDの最大build番号を集計
ARCH_DIR="$HOME/Library/Developer/Xcode/Archives"
MAX_ARCH=0
FOUND=0
if [[ -d "$ARCH_DIR" ]]; then
  while IFS= read -r plist; do
    id=$(/usr/libexec/PlistBuddy -c "Print :ApplicationProperties:CFBundleIdentifier" "$plist" 2>/dev/null || echo "")
    [[ "$id" == "$BUNDLE" ]] || continue
    b=$(/usr/libexec/PlistBuddy -c "Print :ApplicationProperties:CFBundleVersion" "$plist" 2>/dev/null || echo "")
    [[ "$b" =~ ^[0-9]+$ ]] || continue
    FOUND=$((FOUND+1))
    (( b > MAX_ARCH )) && MAX_ARCH=$b
  done < <(find "$ARCH_DIR" -name Info.plist -path '*.xcarchive/Info.plist' 2>/dev/null)
fi

echo "既存アーカイブ: ${FOUND}件（同Bundle ID）／最大build番号: $MAX_ARCH"
echo "----------------------------------------"

if (( CUR > MAX_ARCH )); then
  echo "✅ 衝突なし: 現在build $CUR > 既存最大 $MAX_ARCH。このままArchive可能。"
  exit 0
fi

echo "🚨 衝突リスク: 現在build $CUR <= 既存最大 $MAX_ARCH"
echo "   → このままアーカイブ/アップロードすると弾かれ、古いビルドが配信されたままになります。"
NEXT=$((MAX_ARCH + 1))

if [[ "$BUMP" == "--bump" ]]; then
  # pbxproj 内の全 CURRENT_PROJECT_VERSION を NEXT に更新
  /usr/bin/sed -i '' -E "s/CURRENT_PROJECT_VERSION = [0-9]+/CURRENT_PROJECT_VERSION = $NEXT/g" "$PBX"
  # project.yml があれば併せて更新（xcodegen運用）
  YML="$DIR/project.yml"
  [[ -f "$YML" ]] && /usr/bin/sed -i '' -E "s/CURRENT_PROJECT_VERSION: \"?[0-9]+\"?/CURRENT_PROJECT_VERSION: \"$NEXT\"/g" "$YML"
  echo "🔧 build番号を $CUR → $NEXT に自動更新しました（pbxproj${YML:+ / project.yml}）。"
  echo "   MARKETING_VERSION（表示バージョン）は必要に応じて手動で上げてください。"
  exit 0
else
  echo "   対処: build番号を $NEXT 以上に上げてください（自動なら: $0 $APP --bump）。"
  exit 1
fi
