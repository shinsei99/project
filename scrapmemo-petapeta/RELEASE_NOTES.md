# リリースノート（App Store Connect「このバージョンの新機能」に貼るもの）

> 審査提出時にそのままコピーして使う。技術用語は書かない（利用者が読む欄のため）。

---

## 1.0.5 / build 9（2026-08-28 **アップロード済み**）

```
長い文章を書いても、保存に困らないようにしました。

・「完了」と「キャンセル」を編集画面の上（タイトルの右）へ移しました。
  これまでは文章の一番下にあったため、長い文章を入れると何画面もスクロール
  しないと押せず、届かないまま画面の外をタップして保存されない、ということが
  ありました。これからはいつでもすぐ押せます。
・文字数の表示をタイトルの横にまとめ、そのぶん書く場所を広げました。
```

### 中身（1.0.4 / build 8 からの差分・1コミット）

| コミット | 日付 | 内容 |
|---|---|---|
| `928ffced` | 08/27 | 完了／キャンセルを編集シートのヘッダーへ移した（`makeMemoFootDOM` と `sh-foot.in-scroll` は廃止）／字数をタイトル横へ畳んだ／`#memo-editor` の下余白 6px→26px |

**なぜ出すか**: オーナー報告「長文をペーストすると途中までしか入らない」の調査で、
**アプリは文字を切っていない**（iOS実機エンジンで7,091字が無傷）ことが分かった一方、
**長文だと「完了」に指が届かない**という別の欠陥が見つかった（実測 2,454字＝約3,300px、
7,091字＝9,620px）。届かずに枠外をタップすると保存せずに閉じるため、
「貼ったのに消えた」が普通に起こりうる経路だった。経緯は `SESSION_LOG.md` の 2026-08-27。

---

## 1.0.4 / build 8（2026-08-19 **審査へ提出済み**）

```
写真をたくさん保存できるようになりました。

・保存できる写真の枚数を大幅に増やしました。これまでは写真を数枚
  貼ると保存できなくなることがありましたが、端末の空き容量まで
  使えるようになりました。
・写真が保存されないまま消えてしまう不具合を修正しました。保存
  できなかった場合は、その場でお知らせします。
・写真を貼るときに、自動で見やすいサイズへ調整するようにしました。
・キーボードを表示したままスクラップを編集すると、見出しや先頭の
  行が画面の外に隠れて操作できなくなる不具合を修正しました。
```

### 中身（1.0.3 / build 7 からの差分・2コミット）

| コミット | 日付 | 内容 |
|---|---|---|
| `4b717e5` | 08/18 | キーボード表示中に編集シート上部が触れない不具合を修正／写真を保存前に縮小 |
| `814e3d7` | 08/19 | 画像を IndexedDB へ移して保存容量の問題を根本解決／`save()` の握りつぶしを解消／孤児画像の掃除 |

**利用者から見た変化**: 写真1枚で保存できなくなっていたのが、実測で
**30枚・合計77.3MB でも保持**できるようになった（localStorage 5,100KB → IndexedDB quota 9,830MB）。
技術的な経緯は `SESSION_LOG.md` の 2026-08-18 / 2026-08-19 の節にある。

---

## 1.0.3 / build 7（2026-08-17 アップロード済み・**提出せず**）

※ 1.0.4 / build 8 を提出したので、この build 7 は使わない。
スクラップ編集シートの改良（開いたときに先頭が出ない／ボタンを末尾へ）。

---

## 出し方（Xcode の画面を開かずに通す・2026-08-28 に実際に通した手順）

```bash
cd ~/scrapmemo-petapeta
npm run sync                                        # ← 必須。cap sync 単体では www が作られない
cd ~ && ./ios-build-guard.sh scrapmemo-petapeta --bump   # build 番号を +1（衝突チェック込み）
# 表示バージョンを上げるときは pbxproj の MARKETING_VERSION を手で直す（Debug/Release の2か所）

cd ~/scrapmemo-petapeta
xcodebuild -project ios/App/App.xcodeproj -scheme App -configuration Release \
  -destination 'generic/platform=iOS' -archivePath build/App.xcarchive archive \
  -allowProvisioningUpdates \
  -authenticationKeyPath ~/.appstore/AuthKey_35U53KWY5J.p8 \
  -authenticationKeyID 35U53KWY5J -authenticationKeyIssuerID e55bd1b7-1481-4ee1-9c7e-8caac82815b1
xcodebuild -exportArchive -archivePath build/App.xcarchive \
  -exportOptionsPlist ExportOptions.plist -exportPath build/export -allowProvisioningUpdates \
  -authenticationKeyPath ~/.appstore/AuthKey_35U53KWY5J.p8 \
  -authenticationKeyID 35U53KWY5J -authenticationKeyIssuerID e55bd1b7-1481-4ee1-9c7e-8caac82815b1
xcrun altool --validate-app -f build/export/App.ipa -t ios \
  --apiKey 35U53KWY5J --apiIssuer e55bd1b7-1481-4ee1-9c7e-8caac82815b1
xcrun altool --upload-app -f build/export/App.ipa -t ios \
  --apiKey 35U53KWY5J --apiIssuer e55bd1b7-1481-4ee1-9c7e-8caac82815b1

# ASC 側（バージョン作成・最新情報・build のひも付け）。提出はしない
python3 push-version.py              # 下見
python3 push-version.py --apply
```

**つまずく所**

- **`.xcworkspace` は無い。** Capacitor 8 は SPM（`ios/App/CapApp-SPM`）なので
  `-project ios/App/App.xcodeproj` を使う（`-workspace` は `does not exist` で落ちる）
- **`altool` は `--apiKey` にパスを取らない。** 鍵は `~/.appstoreconnect/private_keys/` に置く
  （このMacには配置済み。実体は `~/.appstore/`）
- **表示バージョンを据え置くと弾かれる。** 直前の版が `READY_FOR_SALE` のときは
  `MARKETING_VERSION` も上げること（build 番号だけでは新バージョンを作れない）
- build は**アップロードから数分で `VALID`** になる（2026-08-28 は 11:09 アップ → 11:1x で VALID）
