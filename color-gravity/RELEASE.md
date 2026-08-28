# カラー・グラビティ — App Store に出す手順

**2026-08-28 時点の状態: アーカイブとipaの書き出しまで完了。残りは下の「★人にしかできないこと」だけ。**

| | |
|---|---|
| Bundle ID | `com.shinsei99.colorgravity` |
| バージョン / ビルド | **1.0 / build 1** |
| アーカイブ | `~/Library/Developer/Xcode/Archives/2026-08-28/ColorGravity-build1.xcarchive` |
| 書き出した ipa | `build/export-build1/App.ipa`（1.58 MB） |
| チーム | `773DPMVW7Q` |
| 最低OS | **iOS 15.0**（Capacitor 8 の既定。2027年春からの必須要件を満たしている） |

---

## ★人にしかできないこと（これをやらないと先へ進めない）

### 1. App Store Connect で「App 記録」を作る

**App Store Connect API では新規Appを作れない**（`POST /v1/apps` が無い）。画面での作成が要る。
これが無いと `altool` は次のエラーで止まる（実測）:

```
ERROR: Cannot determine the Apple ID from Bundle ID 'com.shinsei99.colorgravity' and platform 'IOS'.
```

App Store Connect → マイApp → **＋ → 新規App** で、次のとおり作る:

| 欄 | 入れる値 |
|---|---|
| プラットフォーム | iOS |
| 名前 | **カラー・グラビティ**（jp・us とも完全一致なしを 2026-08-28 に実測） |
| プライマリ言語 | 日本語 |
| バンドルID | **com.shinsei99.colorgravity**（アーカイブ時に自動登録済み。一覧に出るはず） |
| SKU | `colorgravity` など任意（外部には出ない） |
| ユーザーアクセス | 制限なし |

### 2. 記録ができたら、こちらで残りを流し込める

作成後に声をかけてもらえれば、下の3つは機械で入る（画面へ手で写さない）:

```bash
cd ~/color-gravity
xcrun altool --validate-app -f build/export-build1/App.ipa -t ios \
  --apiKey 35U53KWY5J --apiIssuer e55bd1b7-1481-4ee1-9c7e-8caac82815b1
xcrun altool --upload-app  -f build/export-build1/App.ipa -t ios \
  --apiKey 35U53KWY5J --apiIssuer e55bd1b7-1481-4ee1-9c7e-8caac82815b1
python3 push-metadata.py --apply        # store-text.md を流し込む
python3 push-screenshots.py screenshots/upload/iphone --device iphone --apply
python3 push-screenshots.py screenshots/upload/ipad   --device ipad   --apply
```

**アップロード直後は ASC に出てこない**（処理に十数分）。
`python3 appstore_api.py com.shinsei99.colorgravity` で build 1 が並ぶまで待つ。

### 3. 最後にオーナーが画面でやること（APIでは設定できない欄）

- 価格（**無料**）
- **App のプライバシー** → 「データを収集しません」
- 年齢制限（**4+**）
- **審査へ提出**

---

## 出し直すとき（2回目以降）

**必ずビルド番号を +1 する。** 上げずに再アップすると、修正前のビルドが審査を通って
配信される（2026-07-22 に他アプリで実際に起きた事故）。

```bash
./ios-build-guard.sh color-gravity --bump     # 衝突チェック＋自動 +1
cd ~/color-gravity && npx cap sync ios
xcodebuild -project ios/App/App.xcodeproj -scheme App -configuration Release \
  -destination "generic/platform=iOS" \
  -archivePath ~/Library/Developer/Xcode/Archives/$(date +%Y-%m-%d)/ColorGravity-build2.xcarchive \
  -allowProvisioningUpdates archive
xcodebuild -exportArchive -archivePath <上のパス> \
  -exportOptionsPlist ExportOptions.plist -exportPath build/export-build2 \
  -allowProvisioningUpdates \
  -authenticationKeyPath ~/.appstore/AuthKey_35U53KWY5J.p8 \
  -authenticationKeyID 35U53KWY5J -authenticationKeyIssuerID e55bd1b7-1481-4ee1-9c7e-8caac82815b1
```

---

## つまずいた所（2026-08-28 に実際に踏んだもの）

- **`ios/` は git に入らない**（`.gitignore`）。別PCで作り直すときは
  `npm install` → `npx cap add ios` → **下の2つを入れ直す**。忘れるとビルドが通らない/審査に響く。
  1. `project.pbxproj` に `DEVELOPMENT_TEAM = 773DPMVW7Q;` と `CODE_SIGN_STYLE = Automatic;`
     （無いと `Signing for "App" requires a development team` でアーカイブが落ちる）
  2. `Info.plist` の **iPhone は縦のみ**（`UISupportedInterfaceOrientations` を Portrait だけに）
  3. アイコンは `python3 tools/make-icon.py` で描き直せる
  ※ **`npx cap add ios` をやり直すとビルド番号が 1 に戻る。** 必ず `ios-build-guard.sh` で確認する

- **`xcodebuild -exportArchive` が `No Accounts` / `No signing certificate "iOS Distribution" found`**
  → このMacの xcodebuild には Apple ID が入っていない。**API キーを渡せば通る**
  （`-authenticationKeyPath` / `-authenticationKeyID` / `-authenticationKeyIssuerID`）。
  鍵の実体は `~/.appstore/AuthKey_35U53KWY5J.p8`

- **`altool` は `--apiKey` にパスを取らない。** `~/.appstoreconnect/private_keys/` など
  決まった場所しか見ない（同じ鍵がそこにコピー済み）

- **このアプリは Capacitor 8＝SPM** なので `.xcworkspace` は無い。`-project` を使う。
  にゃんこアイス（Capacitor 6＝CocoaPods）は `-workspace` が要る。**アプリごとに違う**

- **App Store の説明文に絵文字は入れられない**（`INVALID_CHARACTERS` で 409）。
  `store-text.md` の説明はすべて絵文字なしで書いてある

---

## 配信物の実測（build 1・2026-08-28）

| 見たこと | 結果 |
|---|---|
| Frameworks | **Capacitor と Cordova の2つだけ**（広告SDK・解析SDKは無い） |
| 画像ファイル | アイコン2枚のみ（ゲームの絵はすべて実行時に描いている） |
| 通信 | HTMLに外部URLなし（`http://www.w3.org/2000/svg` はSVGの名前空間で通信しない） |
| 撮影用の細工 | **0件**（`shotSetup` がipaに残っていないことを確認） |
| MinimumOSVersion | **15.0** |
| 向き | iPhone=縦のみ／iPad=全方向 |
| サイズ | 1.58 MB |
