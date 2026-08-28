# ひよこ防衛軍 — App Store に出す手順

**2026-08-28 時点の状態: アーカイブと ipa の書き出しまで完了。残りは下の「★人にしかできないこと」だけ。**

| | |
|---|---|
| Bundle ID | `com.shinsei99.piyodefense`（Developer Portal に登録済み） |
| バージョン / ビルド | **1.0 / build 2** |
| アーカイブ | `~/Library/Developer/Xcode/Archives/2026-08-28/PiyoDefense-build2.xcarchive` |
| 書き出した ipa | `build/export-build2/App.ipa` |
| チーム | `773DPMVW7Q` |
| 最低OS | **iOS 15.0**（Capacitor 8 の既定。2027年春からの必須要件を満たしている） |
| 向き | iPhone=**縦のみ** ／ iPad=全方向 |

> **build 1 にしなかった理由**: App Store Connect の登録は 0 件なので 1 でも通るが、
> 6月に作った **build 1 のローカルアーカイブが残っていて**、Organizer で取り違える。
> `./ios-build-guard.sh piyo-defense --bump` が衝突を検出して 2 に上げた。

---

## ★人にしかできないこと（これをやらないと先へ進めない）

### 1. App Store Connect で「App 記録」を作る

**App Store Connect API では新規Appを作れない。** 実測した応答:

```
HTTP 403 FORBIDDEN_ERROR
The resource 'apps' does not allow 'CREATE'.
Allowed operations are: GET_COLLECTION, GET_INSTANCE, UPDATE
```

記録が無いまま `altool` を叩くと、次で止まる（color-gravity で実測済み）:

```
ERROR: Cannot determine the Apple ID from Bundle ID '...' and platform 'IOS'.
```

App Store Connect → マイApp → **＋ → 新規App** で、次のとおり作る:

| 欄 | 入れる値 |
|---|---|
| プラットフォーム | iOS |
| 名前 | **ひよこ防衛軍**（jp で完全一致0件を 2026-08-28 に実測。→ `store-text.md` 冒頭） |
| プライマリ言語 | 日本語 |
| バンドルID | **com.shinsei99.piyodefense**（登録済みなので一覧に出る） |
| SKU | `piyodefense` など任意（外部には出ない） |
| ユーザーアクセス | 制限なし |

### 2. 記録ができたら、こちらで残りを流し込める

作成後に声をかけてもらえれば、下は機械で入る（画面へ手で写さない）:

```bash
cd ~/piyo-defense
xcrun altool --validate-app -f build/export-build2/App.ipa -t ios \
  --apiKey 35U53KWY5J --apiIssuer e55bd1b7-1481-4ee1-9c7e-8caac82815b1
xcrun altool --upload-app  -f build/export-build2/App.ipa -t ios \
  --apiKey 35U53KWY5J --apiIssuer e55bd1b7-1481-4ee1-9c7e-8caac82815b1
python3 push-metadata.py --apply                                      # store-text.md を投入
python3 push-screenshots.py screenshots/upload/iphone --device iphone --apply
python3 push-screenshots.py screenshots/upload/ipad   --device ipad   --apply
```

**アップロード直後は ASC に出てこない**（処理に十数分）。
`python3 appstore_api.py com.shinsei99.piyodefense` で build 2 が並ぶまで待つ。

### 3. 最後にオーナーが画面でやること（APIでは設定できない欄）

- 価格（**無料**）
- **App のプライバシー** → 「データを収集しません」
- 年齢制限（**4+**）
- **審査へ提出**

---

## サポートURL・プライバシーURL

`store-text.md` は次を指している。**どちらも GitHub Pages に出ていないと審査に出せない。**

- https://shinsei99.github.io/project/piyo-defense/support.html
- https://shinsei99.github.io/project/piyo-defense/privacy.html

**2026-08-28 の時点では `piyo-defense` は gh-pages に存在しなかった**
（`git ls-tree origin/gh-pages` で確認。CLAUDE.md の「GitHub Pages」という記載は実態と違っていた）。

**オーナー判断で「ゲーム本体も一緒に公開する」に決定** → `.github/workflows/deploy.yml` の
`DEPLOY_FOLDERS` に **`piyo-defense` を追加済み**。**main へ push した時点で3つとも出る**:

- https://shinsei99.github.io/project/piyo-defense/ （ゲーム本体）
- https://shinsei99.github.io/project/piyo-defense/support.html
- https://shinsei99.github.io/project/piyo-defense/privacy.html

> `DEPLOY_FOLDERS` に足すフォルダは **`index.html` がコミット済みであること**が必須。
> 1つでも欠けるとデプロイがステップごと落ち、**他の全部も公開されなくなる**
> （2026-08-28 に `cyborg-defense/www` が未コミットで実際に起きた）。
> 追加したら次で全件を確認すること:
>
> ```bash
> for E in $(grep -o 'DEPLOY_FOLDERS="[^"]*"' .github/workflows/deploy.yml | cut -d'"' -f2); do
>   D="${E%%:*}"; S="${E#*:}"
>   if [ "$S" != "$E" ]; then SRC="$D/$S"; else SRC="$D"; fi
>   git cat-file -e HEAD:"$SRC/index.html" 2>/dev/null && echo "OK $SRC" || echo "NG $SRC"
> done
> ```

---

## 出し直すとき（2回目以降）

**必ずビルド番号を +1 する。** 上げずに再アップすると、修正前のビルドが審査を通って
配信される（2026-07-22 に他アプリで実際に起きた事故）。

```bash
./ios-build-guard.sh piyo-defense --bump      # 衝突チェック＋自動 +1
cd ~/piyo-defense
cp index.html style.css game.js www/ && cp js/*.js www/js/ && cp assets/fonts/*.woff2 www/assets/fonts/
npx cap sync ios
xcodebuild -project ios/App/App.xcodeproj -scheme App -configuration Release \
  -destination "generic/platform=iOS" \
  -archivePath ~/Library/Developer/Xcode/Archives/$(date +%Y-%m-%d)/PiyoDefense-build3.xcarchive \
  -allowProvisioningUpdates archive
xcodebuild -exportArchive -archivePath <上のパス> \
  -exportOptionsPlist ExportOptions.plist -exportPath build/export-build3 \
  -allowProvisioningUpdates \
  -authenticationKeyPath ~/.appstore/AuthKey_35U53KWY5J.p8 \
  -authenticationKeyID 35U53KWY5J -authenticationKeyIssuerID e55bd1b7-1481-4ee1-9c7e-8caac82815b1
```

**`www/` へのコピーを忘れないこと。** Capacitor の `webDir` は `www` なので、
ルートを直しただけでは配信物に入らない。`assets/fonts/` を忘れると書体だけ落ちて豆腐になる。

---

## つまずいた所（2026-08-28 に実際に踏んだもの）

- **`ios/` は git に入る**（このアプリの `.gitignore` は `node_modules/` だけ）。
  color-gravity や nyanko-ice とはここが違う。作り直しは不要。

- **アイコンが Capacitor の既定のまま（青い×印）だった。**
  `python3 tools/make-icon.py` で、ゲーム本体と同じ `drawChick()` を使って描き直す。
  スプラッシュも同時に作る。**別の道具で描くと、ゲームの絵を直したときにアイコンだけ古くなる。**
  ※ **`drawChick` の `acc:'helmet'` はアイコンに使えない**。ヘルメットの縁が `y=-sz*0.3`
    にあり、目（`y=-sz*0.33`）を隠す。アイコン側で縁を `-sz*0.46` に上げて描いている。

- **App Store のアイコンはアルファチャンネルを持てない。**
  ブラウザが出す PNG は RGBA なので、`make-icon.py` の最後で PIL の `convert("RGB")` を通している。

- **`--headless=new --screenshot` の Chrome が戻ってこない**（このMacで実測）。
  アイコンもスクショも **Playwright** で撮るようにした（`va.sh` と同じ Chrome）。

- **iPad を縦だけにすると `All interface orientations must be supported unless the app
  requires full screen` の警告が出る**（マルチタスク要件）。`UIRequiresFullScreen` で
  黙らせる手もあるが Apple はその指定を廃していく方向なので、**iPad は全方向に戻した**。
  横向きでも `resize()` が高さに合わせるだけなので、左右が黒帯になって遊べる。

- **スクリーンショットの仕込みで、弾などの内部オブジェクトを手で作って配列に入れてはいけない。**
  足りないフィールドがあると `update()` が例外を投げ、**`requestAnimationFrame` の輪が切れて
  描画がその場で止まる**。撮ったつもりが直前のタイトル画面になる。
  `shoot.py` は状態だけ作って2〜3秒走らせ、**撮る前に `frame` が進んでいるか必ず確かめている**。

- **説明文の `■` は `【】` に置き換えた。** 絵文字は `INVALID_CHARACTERS` で 409 になる
  （にゃんこアイスで実測: `Description can't contain 🍦`）。`■` は絵文字ではないが、
  巻き込まれるのを避けた。もし 409 が出たら、まずここを疑う。

- **`altool` は `--apiKey` にパスを取らない。** `~/.appstoreconnect/private_keys/` しか見ない
  （同じ鍵がそこにコピー済み。実体は `~/.appstore/AuthKey_35U53KWY5J.p8`）。

- **このアプリは Capacitor 8＝SPM** なので `.xcworkspace` は無い。`-project` を使う。
  にゃんこアイス（Capacitor 6＝CocoaPods）は `-workspace` が要る。**アプリごとに違う**。

---

## スクリーンショットの撮り方

シミュレータは使わない。**このゲームは 390×844 の canvas を画面に合わせて拡大しているだけ**
なので、ブラウザを端末と同じ論理サイズ×倍率で開けば実機と同じ絵になる。

```bash
python3 -m http.server 8899          # 別の窓で（127.0.0.1 で配る）
python3 screenshots/shoot.py         # iPhone 6.5型・iPad 12.9型を5枚ずつ
```

- 書き出し寸法は **iPhone 1284×2778 / iPad 2048×2732**（最初から正しい寸法で撮るので `sips` 不要）
- 撮る5枚: `title / battle / tower / boss / bestiary`
- **配信物には細工が残らない**（ゲーム本体には1行も足していない。状態を外から作っているだけ）
