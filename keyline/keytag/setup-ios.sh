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

echo "── Info.plist / エンタイトルメント / 署名設定 / 版数 ──"
/usr/bin/python3 - "$TEAM_ID" "$BUNDLE_ID" <<'PY'
import json, plistlib, pathlib, re, sys
team, bundle = sys.argv[1], sys.argv[2]

# --- Info.plist ---
p = pathlib.Path("ios/App/App/Info.plist")
d = plistlib.loads(p.read_bytes())
d["CFBundleDisplayName"] = "KeyTag"

# NFCを使う理由。App Store のレビューでもここが見られる
d["NFCReaderUsageDescription"] = (
    "鍵に貼ったNFCタグを読み書きして、どの鍵かを確認できるようにするために使用します。")

# 輸出コンプライアンス。これが無いと、アップロードした build が
# **MISSING_EXPORT_COMPLIANCE で止まり TestFlight に一切出てこない**
# （2026-08-26 に build 3 で実際に踏んだ。API で回答を入れて解除した）。
# このアプリは暗号を使わない（通信は社内LANの平文HTTPのみ）ので False が正しい。
d["ITSAppUsesNonExemptEncryption"] = False

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
# ★TAG が無いと、まっさらな（NDEF未フォーマットの）タグのUIDを掴めない。
#   そして **NDEF は入れてはいけない**。新しいSDKでは廃止されており、
#   App Store へのアップロードが次のエラーで弾かれる（2026-08-18に実際に踏んだ）:
#     code 90778 / "NDEF is disallowed"
#   TAGセッションからNDEFの読み書きもできるので、機能は落ちない。
ent = {"com.apple.developer.nfc.readersession.formats": ["TAG"]}
pathlib.Path("ios/App/App/App.entitlements").write_bytes(plistlib.dumps(ent))
print("   ✅ App.entitlements（TAG のみ。NDEFは入れない）")

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

# ★iPhone専用にする（既定は "1,2" で iPad も対象になる）。
#   iPadにはNFCリーダーが無く、このアプリの主機能が動かない。
#   iPad対応のままだと審査で「主要機能が動作しない」と見られるうえ、
#   App Store で iPad用スクリーンショットまで要求される。
for k, v in [("CODE_SIGN_ENTITLEMENTS", "App/App.entitlements"),
             ("DEVELOPMENT_TEAM", team),
             ("TARGETED_DEVICE_FAMILY", "1")]:
    print(f"   ✅ {k} を{ensure(k, v)}")
s = re.sub(r"PRODUCT_BUNDLE_IDENTIFIER = [^;]*;", f"PRODUCT_BUNDLE_IDENTIFIER = {bundle};", s)

# --- 版数（★これが無いと事故る） ---
# `npx cap add ios` で作り直すと **CURRENT_PROJECT_VERSION が 1 に戻る**。
# ios/ は gitignore なので、別のPCで作り直したときに build 1 のまま再アーカイブし、
# 「古いビルドが審査を通って配信される」事故になる（2026-07-22に photo-remake と
# neon-blocks で実際に起きた）。→ git に残る version.json を正として当て直す。
# **既にプロジェクト側が大きいときは下げない**（メインPCで上げた直後に消さないため）。
ver = json.loads(pathlib.Path("version.json").read_text())
have = max([int(m) for m in re.findall(r"CURRENT_PROJECT_VERSION = (\d+)", s)] or [0])
build = max(int(ver["build"]), have)
ensure("MARKETING_VERSION", ver["marketing_version"])
s = re.sub(r"CURRENT_PROJECT_VERSION = [0-9]+", f"CURRENT_PROJECT_VERSION = {build}", s)
print(f"   ✅ 版数 {ver['marketing_version']} / build {build}"
      + (f"（version.json は {ver['build']}。プロジェクト側が大きいので下げなかった）"
         if build > int(ver["build"]) else ""))

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
