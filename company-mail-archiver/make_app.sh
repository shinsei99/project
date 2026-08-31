#!/bin/bash
# Desktop/社内ツール の `.app`（ブラウザで画面を開くだけのランチャ）を作る。
#
#   ./make_app.sh
#
# ★作り方は「**macOS 自身に作らせる（osacompile）→ きれいな場所で直して署名 → 置く**」。
#   2026-08-31 に手作りの bundle で1時間はまった末に確定した手順。下の「はまり所」を必ず読むこと。
#
# ## はまり所（全部このアプリで実際に踏んだ）
#
# 1. **手で組み立てた .app は Finder のダブルクリックで開けないことがある。**
#    `mkdir` で Contents/MacOS/launcher を書いただけの bundle は、動いているアプリと
#    ファイル構成・権限・拡張属性・署名の有無まで一致していても失敗した。
#    → **osacompile に作らせる**。これは本物の Mach-O と署名を持つ正規の bundle。
#
# 2. **`ls -lO` を見ること。** 書き換えた Info.plist に `hidden` フラグ（UF_HIDDEN）が
#    付いていて LaunchServices が bundle を読めなかった。
#    `ls -l` にも `xattr` にも `codesign` にも出ない。
#
# 3. **こちらから試す起動は全部成功してしまう。**
#    `launcher` 直接実行 / `open` / `open -b` / AppleScript で Finder に開かせる、の4経路とも
#    成功するのに、利用者のダブルクリックだけ失敗した。**「開けた」を根拠にしない。**
#
# 4. **Desktop で codesign すると失敗する。**
#    `resource fork, Finder information, or similar detritus not allowed`。
#    Desktop は file provider 管理下で `com.apple.FinderInfo` が付く。
#    → **scratchpad で `xattr -cr` してから署名し、署名済みを ditto で置く。**
#
# 5. **osacompile の既定アイコンが勝つ。** `Assets.car` と `CFBundleIconName` があると
#    そちらが優先され、差し替えた `applet.icns` が出ない。両方外す。
#
# 6. 作り直しの最中は Finder が古い実体を掴んだままになる → `killall Finder`。
set -eu
cd "$(dirname "$0")"

# 名前とポートは差し替えられる（手順を捨て名で試すため。既定は本番）
NAME="${APP_NAME:-社内メールアーカイバ}"
PORT="${APP_PORT:-8538}"
BUNDLE_ID="${APP_BUNDLE_ID:-com.shinsei.company-mail-archiver-app}"
APP="$HOME/Desktop/社内ツール/${NAME}.app"
WORK="$(mktemp -d /tmp/mkapp.XXXXXX)"
BUILD="$WORK/${NAME}.app"
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"

[ -f icon-src/AppIcon.icns ] || /usr/bin/python3 icon-src/make_icon.py

# ① macOS に作らせる（正規の bundle。署名も付く）
osacompile -o "$BUILD" -e "do shell script \"open \\\"http://localhost:${PORT}\\\"\""

# ② アイコンと名前を入れる。既定アイコンが勝たないよう Assets.car と CFBundleIconName を外す
cp icon-src/AppIcon.icns "$BUILD/Contents/Resources/applet.icns"
[ -f "$BUILD/Contents/Resources/Assets.car" ] && mv "$BUILD/Contents/Resources/Assets.car" "$WORK/Assets.car.unused"
/usr/bin/python3 - "$BUILD" "$NAME" "$BUNDLE_ID" <<'PY'
import sys, os, plistlib
app, name, bid = sys.argv[1], sys.argv[2], sys.argv[3]
p = os.path.join(app, "Contents", "Info.plist")
d = plistlib.load(open(p, "rb"))
d["CFBundleName"] = d["CFBundleDisplayName"] = name
d["CFBundleIdentifier"] = bid
d["CFBundleIconFile"] = "applet"       # 差し替えた applet.icns を使う
d.pop("CFBundleIconName", None)        # アセットカタログ側の指定は消す
plistlib.dump(d, open(p, "wb"))
PY

# ③ きれいにしてから署名（Desktop 上でやると Finder情報で必ず失敗する）
xattr -cr "$BUILD"
chflags -R nohidden "$BUILD"
codesign --force --deep --sign - "$BUILD"
codesign -v "$BUILD"

# ④ 置く（既にあるものは退避。rm は使わない＝消す判断は人がする）
if [ -d "$APP" ]; then
  mv "$APP" "$WORK/previous.app"
fi
ditto "$BUILD" "$APP"
"$LSREGISTER" -f "$APP"
touch "$APP"
killall Finder 2>/dev/null || true

# ★隠しフラグは **置いた後に戻ることがある**（実測。Desktop は file provider 管理下で、
#   ditto / lsregister の直後に UF_HIDDEN が付き直る）。1回外すだけでは足りないので、
#   0件になるまで数回外して、最後に**必ず数える**。ここが0でないと Finder から開けない。
for _ in 1 2 3 4 5; do
  n=$(find "$APP" -flags +hidden 2>/dev/null | wc -l | tr -d ' ')
  [ "$n" = "0" ] && break
  chflags -R nohidden "$APP"
  sleep 1
done

echo "作りました: $APP"
echo "  署名   : $(codesign -dv "$APP" 2>&1 | grep Signature || echo '確認できず')"
HID=$(find "$APP" -flags +hidden 2>/dev/null | wc -l | tr -d ' ')
echo "  隠し   : ${HID} 件（0であること）"
if [ "$HID" != "0" ]; then
  echo "  ★隠しフラグが残っている。このままでは Finder から開けない:"
  find "$APP" -flags +hidden
  echo "  手で外す: chflags -R nohidden \"$APP\""
fi
echo "  退避先 : $WORK"
echo "★確認は必ず**Finderでダブルクリック**。open が通っても開けるとは限らない。"
