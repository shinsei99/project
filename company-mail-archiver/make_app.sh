#!/bin/bash
# Desktop/社内ツール の `.app`（ブラウザで画面を開くだけのランチャ）を作り直す。
#
#   ./make_app.sh
#
# ★作り方は「**動いている .app を丸ごと複製して、3か所だけ書き換える**」（2026-08-31 に確定）。
#
#   ゼロから mkdir で組み立てた bundle は、**中身が既存アプリと1バイト単位で同じ構成**
#   （ファイル一覧・権限・拡張属性・未署名まで一致）でも、**Finder のアイコンから開けなかった**。
#   `open` はシェルからだと成功するのに、Finder のダブルクリックだけ通らない状態。
#   原因を特定しきれなかったので、**確実に動いているものを ditto で複製する**方法に変えた。
#   （Desktop は file provider 管理下にあるので、その辺りの都合と推測。深追いしない）
#
# ★書き換えるのは3か所だけ:
#     Contents/MacOS/launcher     … 開くURL（ポート）
#     Contents/Info.plist         … 表示名と CFBundleIdentifier
#     Contents/Resources/AppIcon.icns … アイコン
#
# ★CFBundleIdentifier は **launchd のラベルと別にする**（`-app` を付ける）。
#   紛らわしさを避けるためで、これ自体が不具合の原因だった証拠は無い。
#
# ★最後に `lsregister -f` を叩くまでが「アプリを作る」作業。
#   叩かないと Finder に登録されず、`open` は error -10810 で落ちる（これも実際に踏んだ）。
set -eu
cd "$(dirname "$0")"

NAME="社内メールアーカイバ"
PORT=8538
BUNDLE_ID="com.shinsei.company-mail-archiver-app"
TOOLS="$HOME/Desktop/社内ツール"
APP="$TOOLS/${NAME}.app"
SRC="$TOOLS/メールアーカイバ.app"          # 確実に動いている見本
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"

[ -d "$SRC" ] || { echo "見本が無い: $SRC"; exit 1; }
[ -f icon-src/AppIcon.icns ] || /usr/bin/python3 icon-src/make_icon.py

# 既にあるものは退避（rm は使わない。消す判断は人がする）
if [ -d "$APP" ]; then
  mv "$APP" "${APP%.app}.old-$(date +%H%M%S).app"
fi

ditto "$SRC" "$APP"

printf '#!/bin/zsh\nopen "http://localhost:%s"\n' "$PORT" > "$APP/Contents/MacOS/launcher"
chmod +x "$APP/Contents/MacOS/launcher"

/usr/bin/python3 - "$APP" "$NAME" "$BUNDLE_ID" <<'PY'
import sys, os, plistlib
app, name, bid = sys.argv[1], sys.argv[2], sys.argv[3]
p = os.path.join(app, "Contents", "Info.plist")
d = plistlib.load(open(p, "rb"))
d["CFBundleDisplayName"] = d["CFBundleName"] = name
d["CFBundleIdentifier"] = bid
plistlib.dump(d, open(p, "wb"))
PY

cp icon-src/AppIcon.icns "$APP/Contents/Resources/AppIcon.icns"
touch "$APP"
"$LSREGISTER" -f "$APP"

echo "作りました: $APP"
open -b "$BUNDLE_ID" && echo "確認: バンドルIDで起動できた（Finderのダブルクリックと同じ経路）"
echo "※ Finder のアイコンが古いままなら、いったんフォルダを閉じて開き直す（または killall Finder）"
