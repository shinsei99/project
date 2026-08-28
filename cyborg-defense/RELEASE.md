# サイボーグ防衛軍 — App Store へ出す（2026-08-28 メインPCで実施）

**現在の状態: 提出直前まで完了。残りは「App 記録を作る」だけ**（人にしかできない）。

| | 状態（2026-08-28 実測） |
|---|---|
| iOSアプリ化 | **済**。Capacitor 8（SPM）・`com.daikyo.cyborgdefense`・1.0 (build 1) |
| バンドルID | **登録済み**（Archive 時に自動登録。API で確認） |
| アイコン・起動画面 | **済**（`icon-src/make_icon.py` で生成・差し込み済み。アルファ無し） |
| シミュレータ確認 | **済**（iPhone 17 Pro Max / iPad Pro 13）。タイトル→ゲート→戦闘→ボス→ゲームオーバー |
| スクリーンショット | **済**。iPhone 6.9型 1290×2796 ×6 / iPad 12.9型 2048×2732 ×6（`screenshots/upload/`） |
| サポート／プライバシー | **済**（`www/support.html` `www/privacy.html`。gh-pages へは main の push で出る） |
| ストア文言 | **済**（`store-text.md`。4.3(a) 対策の調査つき） |
| **ipa の書き出し** | **済**。`build/export/App.ipa`（2.0MB・Apple Distribution 署名・MinimumOSVersion 15.0） |
| **アップロード** | **未**。App 記録が無いため弾かれる（下記） |

---

## ★ 人にしかできないこと（オーナー・5分）

**App 記録の新規作成は API では行えない。** 2026-08-28 に実測して確認した:

```
POST /v1/apps → 403 "The resource 'apps' does not allow 'CREATE'.
                 Allowed operations are: GET_COLLECTION, GET_INSTANCE, UPDATE"
```

そのため `xcrun altool --validate-app` は次で止まる（これは想定どおりの状態）:

```
ERROR: Cannot determine the Apple ID from Bundle ID 'com.daikyo.cyborgdefense' and platform 'IOS'. (19)
```

App Store Connect の「マイApp」→「＋」→「新規App」で、次を入れて作成してください。

| 項目 | 値 |
|---|---|
| プラットフォーム | iOS |
| 名前 | `サイボーグ防衛軍` |
| プライマリ言語 | 日本語 |
| バンドルID | `com.daikyo.cyborgdefense`（一覧に出る） |
| SKU | `cyborgdefense2026` |
| ユーザーアクセス | 制限なし |

---

## 記録を作ったあと（機械でできる。3コマンド＋2コマンド）

```bash
cd ~/cyborg-defense

# ① 検証（ここで落ちればアップロードしても弾かれる）
xcrun altool --validate-app -f build/export/App.ipa -t ios \
  --apiKey 35U53KWY5J --apiIssuer e55bd1b7-1481-4ee1-9c7e-8caac82815b1

# ② アップロード
xcrun altool --upload-app -f build/export/App.ipa -t ios \
  --apiKey 35U53KWY5J --apiIssuer e55bd1b7-1481-4ee1-9c7e-8caac82815b1

# ③ 反映を待つ（十数分。build 1 が並べばOK）
python3 ../appstore_api.py com.daikyo.cyborgdefense

# ④ 文言を流し込む（store-text.md が正。画面へ手で写さない）
python3 push-metadata.py --apply

# ⑤ スクリーンショット
python3 push-screenshots.py screenshots/upload/iphone --device iphone --apply
python3 push-screenshots.py screenshots/upload/ipad   --device ipad   --apply
```

**`altool` は `--apiKey` にパスを取らない。** `~/.appstoreconnect/private_keys/AuthKey_35U53KWY5J.p8`
に鍵がある必要がある（このMacはコピー済み）。

`--device iphone` は **6.9型（APP_IPHONE_67・1290×2796）** に入れる。もし寸法で弾かれたら
`--device iphone65` に切り替える（`screenshots/upload/iphone65/` に 1284×2778 を用意してある）。

そのあと画面でしか設定できないもの（オーナー）:

- 価格（無料）
- App のプライバシー → **データを収集していません**
- 年齢制限 → 暴力表現は「まれ／軽度の漫画・ファンタジー」、ほかは「なし」（4+想定）
- ビルドの選択（build 1）→ **審査へ提出**

---

## 作り直すときの手順（ipa をもう一度作る）

```bash
cd ~/cyborg-defense
./ios-build-guard.sh cyborg-defense --bump      # ★ビルド番号を必ず +1（再配信の事故防止）
npx cap sync ios
xcodebuild -project ios/App/App.xcodeproj -scheme App -configuration Release \
  -destination "generic/platform=iOS" -archivePath build/App.xcarchive archive \
  -allowProvisioningUpdates -authenticationKeyPath ~/.appstore/AuthKey_35U53KWY5J.p8 \
  -authenticationKeyID 35U53KWY5J -authenticationKeyIssuerID e55bd1b7-1481-4ee1-9c7e-8caac82815b1
xcodebuild -exportArchive -archivePath build/App.xcarchive \
  -exportOptionsPlist ExportOptions.plist -exportPath build/export \
  -allowProvisioningUpdates -authenticationKeyPath ~/.appstore/AuthKey_35U53KWY5J.p8 \
  -authenticationKeyID 35U53KWY5J -authenticationKeyIssuerID e55bd1b7-1481-4ee1-9c7e-8caac82815b1
```

**このアプリは Capacitor 8＝SPM** なので `-project`（`.xcworkspace` は存在しない）。
にゃんこアイスは Capacitor 6＝CocoaPods で `-workspace` が要る。**アプリごとに違う。**

**配布用の証明書は `security find-identity` に出てこない**（Xcode のクラウド管理証明書）。
それでも `xcodebuild` は見つけるので、上のコマンドはそのまま通る。

## スクリーンショットの撮り直し

```bash
./screenshots/shoot.sh title gate battle boss combo over
DEVICE=ipad ./screenshots/shoot.sh title gate battle boss combo over
```

- タップを使わず、**状態を作る細工を差し込んだビルド**を1画面ずつ作って撮る
  （このMacのターミナルには「アクセシビリティ」権限が無く、シミュレータへタップを送れない）
- 細工は `screenshots/shot-boot.js`。**撮る直前に構図を作って `G.running=false` で止める**。
  起動直後に作ると、撮影までの十数秒でゲートも敵も流れて別の絵になる（実際にそうなった）
- 撮影後、`ios/App/App/public/index.html` は `www/index.html` で自動的に戻る
  （**配信物に細工を残さない**）。Archive 前に `grep -n shotSetup ios/App/App/public/index.html` が
  空であることを確かめると確実

## ios/ は git に入らない

`.gitignore` で `cyborg-defense/ios/` と `node_modules/` を除外している（他PCで作り直す前提）。
**作り直したら Info.plist の設定が消える**ので、次を入れ直すこと:

| 設定 | 値 | 理由 |
|---|---|---|
| `UISupportedInterfaceOrientations` | Portrait のみ（iPad は Portrait + UpsideDown） | 盤面が 9:16 |
| `UIRequiresFullScreen` | true | 向きを縦だけにするなら必要 |
| `UIStatusBarHidden` / `UIViewControllerBasedStatusBarAppearance` | true / false | 没入感 |
| `ITSAppUsesNonExemptEncryption` | false | 毎回の暗号化申告を出さない |
| `DEVELOPMENT_TEAM` | `773DPMVW7Q` | 自動署名 |
| アイコン・起動画面 | `python3 icon-src/make_icon.py` | 生成し直せる |
