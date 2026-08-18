#!/bin/bash
# KeyTag の iOS プロジェクトを作り直す。
#
# ★なぜスクリプトにするか
#   ios/ は gitignore（Xcodeの生成物で巨大なため）。よって `npx cap add ios` で
#   作り直すことになるが、そのままでは **NFCのエンタイトルメントもATS例外も付かず、
#   実機でタグを読んだ瞬間に必ず失敗する**。手順書に書くだけだと読み落とすので、
#   設定を全部ここに入れて一発で揃うようにしてある。
#
# 使い方:  cd ~/keyline/keytag && ./setup-ios.sh

set -euo pipefail
cd "$(dirname "$0")"

TEAM_ID="773DPMVW7Q"          # 既存6本と同じ Apple Developer チーム
BUNDLE_ID="com.shinsei99.keytag"

echo "── 依存を入れる ──"
[ -d node_modules ] || npm install

echo "── iOSプロジェクト ──"
if [ -d ios ]; then
  echo "   すでにあります（設定だけ当て直します）"
else
  npx cap add ios
fi
npx cap sync ios

echo "── Info.plist / エンタイトルメント / 署名設定 ──"
/usr/bin/python3 - "$TEAM_ID" "$BUNDLE_ID" <<'PY'
import plistlib, pathlib, re, sys
team, bundle = sys.argv[1], sys.argv[2]

# --- Info.plist ---
p = pathlib.Path("ios/App/App/Info.plist")
d = plistlib.loads(p.read_bytes())
d["CFBundleDisplayName"] = "KeyTag"

# NFCを使う理由。App Store のレビューでもここが見られる
d["NFCReaderUsageDescription"] = (
    "鍵に貼ったNFCタグを読み書きして、どの鍵かを確認できるようにするために使用します。")

# 社内サーバー（平文HTTP・プライベートIP）へ繋げるようにする。
# ★NSAllowsArbitraryLoads は使わない。全HTTPを開けてしまい、審査でも理由を問われる
d["NSAppTransportSecurity"] = {"NSAllowsLocalNetworking": True}

# iOS14以降、同一LAN内の機器へ通信するには利用者の許可が要る
d["NSLocalNetworkUsageDescription"] = (
    "同じWi-Fi内にある鍵管理システムへ接続するために使用します。"
    "連携を設定していない場合は使用しません。")

# 縦画面のみ。片手で鍵を持ちながら操作するため
d["UISupportedInterfaceOrientations"] = ["UIInterfaceOrientationPortrait"]
p.write_bytes(plistlib.dumps(d))
print("   ✅ Info.plist")

# --- エンタイトルメント ---
# ★TAG が無いと、まっさらな（NDEF未フォーマットの）タグのUIDを掴めない
ent = {"com.apple.developer.nfc.readersession.formats": ["TAG", "NDEF"]}
pathlib.Path("ios/App/App/App.entitlements").write_bytes(plistlib.dumps(ent))
print("   ✅ App.entitlements（TAG + NDEF）")

# --- Xcodeプロジェクト ---
q = pathlib.Path("ios/App/App.xcodeproj/project.pbxproj")
s = q.read_text()

def ensure(key, value):
    """ビルド設定を入れる（無ければ PRODUCT_BUNDLE_IDENTIFIER の隣に足す）。"""
    global s
    if f"{key} = " in s:
        s = re.sub(rf"{key} = [^;]*;", f"{key} = {value};", s)
        return "更新"
    s = re.sub(r"(\n(\t+)PRODUCT_BUNDLE_IDENTIFIER = )",
               rf"\n\2{key} = {value};\1", s)
    return "追加"

for k, v in [("CODE_SIGN_ENTITLEMENTS", "App/App.entitlements"),
             ("DEVELOPMENT_TEAM", team)]:
    print(f"   ✅ {k} を{ensure(k, v)}")
s = re.sub(r"PRODUCT_BUNDLE_IDENTIFIER = [^;]*;", f"PRODUCT_BUNDLE_IDENTIFIER = {bundle};", s)
q.write_text(s)
print(f"   ✅ Bundle ID {bundle}")
PY

echo ""
echo "── アイコン ──"
if [ -f icon-src/crop_icon.py ] && [ ! -f ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-512@2x.png ]; then
  /usr/bin/python3 icon-src/crop_icon.py || echo "   ⚠️ 元画像が見つかりません。手動で1024pxのPNGを置いてください"
else
  echo "   すでにあります"
fi

echo ""
echo "── 確認 ──"
grep -oE "MARKETING_VERSION = [^;]+|CURRENT_PROJECT_VERSION = [^;]+|DEVELOPMENT_TEAM = [^;]+|PRODUCT_BUNDLE_IDENTIFIER = [^;]+|CODE_SIGN_ENTITLEMENTS = [^;]+" \
  ios/App/App.xcodeproj/project.pbxproj | sort -u | sed 's/^/   /'
echo ""
echo "✅ 完了。次は RELEASE.md の手順に従って Xcode で Archive してください:"
echo "   npx cap open ios"
