# にゃんこ大脱出 — App Store へ出す（2026-08-28 メインPCで実施）

> ## 🛑 いまは提出しない（2026-08-29〜）
>
> **2026-08-29 に他の3本が Guideline 4.3(a)（スパム）でまとめてリジェクトされた。**
> アカウント全体の出し方を見られている状態なので、**このアプリの App 記録を作ってはいけない**。
> 下の手順は、再開してよくなってから使うこと。経緯と再開条件は直下 `TODO.md` の冒頭。

**現在の状態: 提出直前まで完了。残りは「App 記録を作る」だけ**（人にしかできない）。

| | 状態（2026-08-28 実測） |
|---|---|
| iOSアプリ化 | **済**。Capacitor 8（SPM）・`com.daikyo.nekoescape`・1.0 (build 1) |
| アイコン・起動画面 | **済**（`icon-src/make_icon.py`。本編と同じネコの顔・**アルファ無し**・角丸なし） |
| セーフエリア | **済**（`viewport-fit=cover` ＋ `env(safe-area-inset-*)`。無いとヘッダーが Dynamic Island に潜る） |
| スクリーンショット | **済**。iPhone 1290×2796 ×5 / 1284×2778 ×5 / iPad 2048×2732 ×5（`screenshots/upload/`） |
| サポート／プライバシー | **済**（`www/support.html` `www/privacy.html`。gh-pages へは main の push で出る） |
| ストア文言 | **済**（`store-text.md`。4.3(a) 対策の調査つき） |
| **ipa の書き出し** | **済**。`build/export/App.ipa`（870KB・MinimumOSVersion 15.0） |
| 配信物の実測 | Frameworks は **Capacitor と Cordova だけ**／外部URLは SVG の名前空間のみ＝**通信なし**／撮影用の細工は残っていない |
| **アップロード** | **未**。App 記録が無いため弾かれる（下記） |
| 記録ができた後の自動化 | **済**。`finish-release.py` が検証→アップロード→処理待ち→ビルドのひも付け→文言→スクショまで1コマンド |

---

## ★ 人にしかできないこと（オーナー・5分）

**App 記録の新規作成は API では行えない**（`POST /v1/apps` → 403
`The resource 'apps' does not allow 'CREATE'`。他アプリで実測済み）。
そのため `xcrun altool --validate-app` は次で止まる（**これは想定どおりの状態**）:

```
ERROR: Cannot determine the Apple ID from Bundle ID 'com.daikyo.nekoescape' and platform 'IOS'. (19)
```

App Store Connect の「マイApp」→「＋」→「新規App」で、次を入れて作成してください。

| 項目 | 値 |
|---|---|
| プラットフォーム | iOS |
| 名前 | `にゃんこ大脱出` |
| プライマリ言語 | 日本語 |
| バンドルID | `com.daikyo.nekoescape`（Archive 時に自動登録されるので一覧に出る） |
| SKU | `nekoescape2026` |
| ユーザーアクセス | 制限なし |

## 記録を作ったあと（**1コマンド**）

```bash
cd ~/neko-escape
python3 finish-release.py            # 何をするかだけ表示（変更しない）
python3 finish-release.py --apply    # 検証→アップロード→処理待ち→ひも付け→文言→スクショ
```

**App 記録が無いうちに叩いても安全**（作るための値を出して止まるだけ）。

そのあと ASC の画面で次を入れて **審査へ提出**（これも人）:

- 価格 → **無料**
- App のプライバシー → **データを収集していません**（通信しないため）
- 年齢制限 → すべて「なし」（**4+ 想定**。ロボットは穴に落ちるだけで破壊・流血の描写なし）
- ビルドの選択（build 1）→ **審査へ提出**

---

## 作り直すときの手順（ipa をもう一度作る）

```bash
cd ~/neko-escape
../ios-build-guard.sh neko-escape --bump      # ★ビルド番号を必ず +1（再配信の事故防止）
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

### ★ここで踏んだ落とし穴（同じことをする人へ）

- **`npx cap add ios` は `DEVELOPMENT_TEAM` を書かない。** そのままだと Archive が
  `Signing for "App" requires a development team` で落ちる。
  `ios/App/App.xcodeproj/project.pbxproj` の `CODE_SIGN_STYLE = Automatic;` の隣に
  `DEVELOPMENT_TEAM = 773DPMVW7Q;` を2か所入れる（**`ios/` は git に入れていないので、
  作り直すたびに必要**）。
- **`-exportArchive` は API キーを渡さないと落ちる**（`No Accounts` /
  `No signing certificate "iOS Distribution" found`）。配布用の証明書は
  `security find-identity` にも出てこない（Xcode のクラウド管理証明書）。
  上のコマンドのように `-authenticationKeyPath` を付ければ通る。
- **このアプリは Capacitor 8＝SPM** なので `-project`（`.xcworkspace` は無い）。
  にゃんこアイスは Capacitor 6＝CocoaPods で `-workspace` が要る。**アプリごとに違う。**
- **アプリの本体は `www/`**。`deploy.yml` の `DEPLOY_FOLDERS` も `neko-escape:www` になっている。
  **本体を動かすときは、同じ push で deploy.yml も直すこと**（片方だけ push すると
  gh-pages のデプロイがステップごと落ち、**他のアプリの公開まで止まる**）。

## スクリーンショットの撮り直し

```bash
./screenshots/shoot.sh title board gimmick clear select
DEVICE=ipad ./screenshots/shoot.sh title board gimmick clear select
# 仕上げ（App Store の寸法へ）
sips -z 2796 1290 screenshots/shots/title.png --out screenshots/upload/iphone/1-title.png
sips -z 2732 2048 screenshots/shots-ipad/title.png --out screenshots/upload/ipad/1-title.png
```

- タップは使わない（このMacのターミナルに「アクセシビリティ」権限が無く、シミュレータへ
  タップを送れない）。**画面の状態をコードで作る細工**（`screenshots/shot-boot.js`）を
  `boot();` の直後へ差し込んだビルドを、1画面につき1回作って撮る
- 撮影後 `ios/App/App/public/index.html` は `www/index.html` で自動的に戻る
  （**配信物に細工を残さない**。ipa を展開して `__SHOT__` が0件であることを確認済み）
- **ステータスバーは `simctl status_bar override` で 9:41 に固定**している。
  やらないと「◀ 前のアプリ名」や実時刻が写り込む（実際に写った）

## このアプリの前提（審査で聞かれること）

- 広告SDK・課金・通信・第三者SDK **すべて無し**。機内モードで全機能が動く
- 保存しているのは `localStorage` の2つだけ（クリア状況と★／音のオン・オフ）
- 画面は canvas に自前描画。外部の画像素材ゼロ。書体は Zen Maru Gothic（SIL OFL・再配布可）
