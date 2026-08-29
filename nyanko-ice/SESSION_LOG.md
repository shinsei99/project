# にゃんこアイス — 作業ログ

## 2026-08-29（メインPC）— ネオン6本の共通の型に合わせた

`neon-blocks/NEON_STYLE.md`（6本で揃える決まり）に合わせて 書体を丸ゴシック→角ゴシック＋Orbitron へ、音ボタンを右下→右上へ、**タイトル画面を新設**、favicon を追加、BGM音量を 0.26 に（調は C のまま）。
経緯と検証は **`neon-blocks/SESSION_LOG.md` の同日分**にまとめてある。
音は人の耳で未確認。

## 2026-08-28（メインPC・午後）— 広告を全部外し、App Store の**提出直前まで**用意した

**残っているのは「審査へ提出」を押すことと、画面でしか設定できない3項目だけ**（下の「人にしかできないこと」）。

### 完了したこと

オーナー判断「他のアプリと同様に、アーカイブから提出できる寸前までやる。**広告は削除**。一旦、広告なしで出す」。

| | 内容 |
|---|---|
| **広告の全廃** | `www/index.html` の広告CSS・DOM・JS（98行）／`plugins.AdMob`／`@capacitor-community/admob`／`Info.plist` の `GADApplicationIdentifier` と `NSUserTrackingUsageDescription`／Podfile の `GoogleUserMessagingPlatform` を削除。**書き出したipaに広告SDKが入っていないことを実測**（Frameworks は Capacitor と Cordova の2つだけ） |
| ゲームオーバー | 「動画を見てコンテニュー」は**動画なしでそのまま再開**に。文言も `▶ つづきから` へ |
| 書体 | 文言が変わったのでサブセットを取り直した（漢字 20→5字・各29KB前後） |
| **iPadの見た目** | 盤面の上限が `max-width:470px` で、iPad(1032×1376pt)では**画面の半分以上が余白**だった。`width:min(100vw,62vh); max-width:720px` に変更。**iPhone の見え方は変えていない**（402pt幅では 100vw が最小のまま。前後のスクショを同座標で比較して一致を確認） |
| サポート/プライバシー | `www/support.html` `www/privacy.html` を新設 → gh-pages へ自動デプロイ → **どちらも 200 を実測** |
| ストア文言 | `store-text.md` に全文（名前・サブタイトル・プロモ・キーワード・説明・審査ノート）。**API で流し込み済み** |
| スクリーンショット | **iPhone 6.5型 5枚・iPad 12.9型 5枚**（`start / play / stack / clear / gameover`）。すべて `COMPLETE` |
| ビルド | **1.0 / build 2** を Archive → 検証 → アップロード → `VALID` → **バージョンにひも付け済み** |

**4.3(a) 対策として、先に App Store を実測した**（KeyTag の差し戻しの教訓）。
`にゃんこのアイス屋さん` は完全一致なしで空いていたが、**アイス×並べ替えパズルは量産アプリが多い棚**
（`Icecream Sort Puzzle` / `Ice Cream Sort` / `アイスクリームの並べ替え` ほか）。そこで文言は
**「広告なし・課金なし・通信なし」「絵は全部手描き」「ちゅうもんを作る店番ゲーム」**を前面に出し、
審査ノートにも 4.3 への説明とソースの公開先を明記した。根拠は `store-text.md` の冒頭。

### 発生したエラーと解決策

- **症状**: 撮影用ビルドが `unable to resolve module dependency: 'Capacitor'` で落ちる
  → **原因**: このアプリは **Capacitor 6＝CocoaPods**。`-project` で建てると Pods が繋がらない
  → **直し方**: **`-workspace ios/App/App.xcworkspace`** を使う。
    （KeyTag は Capacitor 8＝SPM で `.xcworkspace` が無く `-project` が正しい。**アプリごとに違う**）

- **症状**: 説明文の投入が HTTP 409 `INVALID_CHARACTERS`
  → **原因**: **App Store の説明に絵文字は入れられない**（`Description can't contain 🍦`）
  → **直し方**: 絵文字を外した。`store-text.md` にも注意書きを残した

- **症状**: カテゴリを PATCH しても、読み直すと `primaryCategory: null` のまま（PATCHは200）
  → **原因**: **`include=primaryCategory` を付けないと relationships に出てこない**だけで、
    実際には設定できていた。素の応答を見て「未設定」と誤認していた
  → **直し方**: `push-metadata.py` の現状読み取りを `include` 付きに変更。誤って毎回 PATCH しない

- **警告（対応不要・記録のみ）**: アップロード時に `MinimumOSVersion too low`（現在 13.0）。
  **2027年春以降は 15.0 以上でないとアップロードできない**。次に出すときに上げる

### 撮影のしかた（次回も使える）

`screenshots/shoot.sh` … シミュレータで**タップを使わずに**撮る。`screenshots/shot-boot.js` を
**`www/index.html` の IIFE の中**（末尾の `})();` の直前）へ差し込んだビルドを画面ごとに作り、
`simctl` で撮って、最後に `public/index.html` を `www/` で戻す。**配信物には細工が残らない**
（Archive 前に `AdMob|shotSetup` の grep が0件であることを確認済み）。

```bash
./screenshots/shoot.sh start play stack clear gameover              # iPhone 17 Pro Max
DEVICE=ipad ./screenshots/shoot.sh start play stack clear gameover  # iPad Pro 13
# 寸法を直してから投入（シミュレータの素の解像度は弾かれる）
sips -z 2778 1284 …  /  sips -z 2732 2048 …
python3 push-screenshots.py screenshots/upload/iphone --device iphone --apply
python3 push-screenshots.py screenshots/upload/ipad   --device ipad   --apply
```

### 提出まで完了（同日・本人実施）

オーナーが App Store Connect の画面で、価格・App のプライバシー・年齢制限を設定して**提出**。
**API で `1.0 … 審査待ち`（`WAITING_FOR_REVIEW`）を確認済み。** これが**このアプリの初提出**。

**音は未試聴のまま提出した。** 気に入らなければ、素材を置いて `USE_FILES=true` にし、
次のビルド（build 3）で出し直せばよい → https://shinsei99.github.io/project/nyanko-ice/

### 次回への引き継ぎ事項

- **広告を戻すときはコミット `3d637897` の1つ前（`942174fe`）を見る。** 消した箇所がすべて揃っている
- 出し直すときは **必ず build 3 へ**（`./ios-build-guard.sh nyanko-ice --bump`）
- **Android プロジェクトはそもそも存在しない**（`android/` フォルダ無し。`package.json` に
  `@capacitor/android` の依存だけがある状態）。将来 `npx cap add android` するときは、
  広告を外した後の `capacitor.config.json` から作られるので、広告IDは入らない

## 2026-08-28（メインPC）— Web版(gh-pages)へ反映。以後は push で自動になった

### 完了したこと

8/27 の作り替え（明るい店内・Zen Maru Gothic・音）が**公開版に入っていなかった**。
原因は `.github/workflows/deploy.yml` の `DEPLOY_FOLDERS` が
`scrapmemo-petapeta mom-counter` の2本しか見ておらず、**このアプリは手で置きに行く運用**だったこと。

- `DEPLOY_FOLDERS` を **`公開先:取り出し元`** の書き方に対応させ、**`nyanko-ice:www`** を追加
  （このアプリはフォルダ直下に `index.html` が無く、中身は `www/` にあるため）
- あわせて `realestate-calc` も追加（同じ理由で公開版が古かった）
- **以後、main を push すれば公開版も一緒に更新される**

**検証**（CLAUDE.md の「静的HTML」の最低ライン）: 公開URLを実際に開いて確認。
`https://shinsei99.github.io/project/nyanko-ice/` … 書体 woff2 **2本とも 200**、
Console のエラーは `favicon.ico` の 404 **1件のみ**（ゲーム由来は0件）、
画面は新しい店内の絵（ネコ店長・ショーケース・丸ゴシック）で表示。

### 発生したエラーと解決策

- **症状**: ワークフローに `[ "$SUB" != "$ENTRY" ] && SRC="$DEST/$SUB"` と書きかけた
  → **原因**: GitHub Actions の `run` は **`bash -e`** で走る。`:` を書かない行
    （`mom-counter` など）ではこの `&&` リスト全体が非0で終わり、**ステップごと落ちる**
  → **直し方**: `if … else … fi` で書く。push 前に `bash -e -c` で同じ分岐をローカルに流し、
    4本とも解決して最後まで到達することを確認した

### 次回への引き継ぎ事項・未解決の課題

- **音は未試聴のまま**（こちらでは聴けない）。合成音で鳴ることは確認済み
- **App Store へ出すなら、先に `www/support.html` と `www/privacy.html` を作る。**
  Apple はサポートURLとプライバシーポリシーURLを必須にしているが、
  このアプリは**どちらも未登録**（2026-08-28 に API で確認）。雛形は `mom-counter/support.html`。
  **`www/` の中に置くこと**（デプロイの取り出し元が `www` のため）

## 2026-08-27（メインPC）— 見た目を「アイス屋の店内」に作り替え、書体と音を入れた

### 完了したこと

**きっかけ**: 「フリー素材とか活用して、もっと魅力的にできないか」（オーナー）。
最初に `./va.sh shot` で撮って現状を見たところ、魅力を削いでいたのは素材の不足ではなく次の4点だった。

1. 画面の Y=280〜580 がまるごと空白（一番目立つ場所に何も無い）
2. 全体が濃紺で暗く、アイス屋＋ネコという題材と合っていない
3. 書体が OS 標準の sans-serif（日本語がヒラギノ）＝かわいさが出ない
4. ネコが顔だけで宙に浮いている／アイスがただの球／音がオシレータのビープのみ

**やったこと**

| # | 内容 |
|---|---|
| 1 | 画面を3層に作り替え。**0〜112 木の看板（HUDの下地）／112〜344 明るい店内（丸窓・ペンダントライト・腰壁・ネコ店長）／344〜706 冷凍ショーケース／706〜760 カウンター** |
| 2 | **Zen Maru Gothic（Google Fonts・SIL OFL）を同梱**。`tools/fetch-font.py` で「画面に出る文字だけ」に絞る |
| 3 | ネコ店長に**体・エプロン・リボン・コック帽**をつけ、**前足をケースの縁に乗せた**。名前は文字幅を測って**エプロンの名札**に載せる |
| 4 | アイスにスクープの筋とスプリンクルを追加。コーンを丸みのある形にし、カウンターに影を落とした |
| 5 | **音を作り直した**。オシレータ直打ちの `blip()` を全廃し、名前付きの効果音10種＋ペンタトニックのBGMループに。**音のオン/オフボタン**を画面下に追加（localStorage に保存） |
| 6 | ヒントをキャンバスの外へ出した（中に置くとコーンに重なって読めなかった） |

**検証**（CLAUDE.md の「静的HTML」の最低ライン）: `./va.sh` で開いて **ゲーム由来の Console エラー0件**
（出る404は `favicon.ico` のみ）。選択→移動、ステージクリア、ゲームオーバーの3画面を目視。
書体の読み込みは `document.fonts` で `Zen Maru Gothic:500:loaded / :900:loaded` を実測。

### 発生したエラーと解決策

- **症状**: フォントを取ったら woff2 が 92KB×2 になった（漢字306字）
  → **原因**: `fetch-font.py` がソース全体を走査し、**日本語のコメントまで文字集合に入れていた**
  → **直し方**: HTMLのテキストとJSの文字列リテラルだけを拾うようにした（`screen_text()`）。
    漢字20字・**32KB×2** に収まった。行コメントを落とす正規表現は `(^|[^:])//` にして
    `https://` を巻き込まないようにしてある

- **症状**: `file://` で開くと書体が当たらない（`http://` では当たる）
  → **原因**: Chrome は file:// のフォント取得を止めることがある
  → **直し方**: 検証は `python3 -m http.server` 経由で行う。**実運用は影響なし**
    （Capacitor は独自スキームのHTTP、GitHub Pages もHTTP）。README の確認手順を書き換えた

- **症状**: 店長の名前「ロシアンブルー てんちょう」が腕の毛に重なって読めない
  → **原因**: 文字幅（約145px）がエプロンの幅（約116px）を超えていた
  → **直し方**: `measureText` で幅を測り、その幅の名札を敷いてから文字を載せる。
    猫種が変わって名前の長さが変わっても崩れない

- **症状**: ショーケースを暗くしたら「また画面が暗い」に戻りかけた
  → **原因ではなく設計判断**: アイスは全部淡い色（バニラ `#FFF6E0` など）なので、
    明るい地に置くと輪郭が消える。**アイスが乗る場所だけを冷たい紺**にして、
    上半分は明るいままにした。暗いのは装飾ではなくコントラストの都合であることを
    コードのコメントに残してある

### 次回への引き継ぎ事項・未解決の課題

- **★音は耳で確かめていない。** 合成音なので鳴ることは確実だが、**心地よいかどうかは未確認**
  （こちらでは音を聴けない）。**オーナーが一度聴いて、気に入らなければ効果音ラボの素材に差し替える**のが早い。
  差し替え手順は `www/index.html` の `USE_FILES` の直上に書いてある（**ファイルを置いて `true` にするだけ**）
- **★Web版（GitHub Pages）はまだ更新していない。** `gh-pages` の `nyanko-ice/index.html` は古いまま。
  更新するなら **`index.html` だけでなく `www/assets/fonts/` も一緒に置く**こと（書体が無いと豆腐になる）。
  **外部公開なのでオーナーの指示を待つ**
- **★iOSアプリは未提出のまま**（1.0が「提出準備中」・登録ビルド0件）。出すときは
  `./ios-build-guard.sh nyanko-ice` → `npx cap sync` → Archive。
  `www/assets/` が増えたので **`npx cap sync` を忘れると書体が入らない**
- Android用 AdMob ID は未取得（テストIDのまま）
- `TESTING = true` のまま。**リリース直前に `false`** にする（README のとおり）
