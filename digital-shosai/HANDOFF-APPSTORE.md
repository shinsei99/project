# HANDOFF — デジタル書斎を App Store に出す（メインPCで実施）

サブPCで **Web版の中身は仕上がっている**（2026-08-17夜）。
**2026-08-19（メインPC）に Capacitor 化とシミュレータでの通し確認・スクショ取得まで済ませた。**
残りは App Store Connect の登録と Archive／提出（配信用証明書がメインPCにしか無い）。

このファイルだけ見れば提出まで進められるように書いた。分からない数字は実測値を添えている。

---

## 0. 追記（2026-08-27 メインPC）— **1.0 は配信中。いまは 1.0.1 のアップロード待ち**

- **1.0 / build 1 は審査を通って配信中**（`python3 appstore_api.py --review com.shinsei.shosai`）
- **アイコンをオーナー支給の画像に差し替え**、**1.0.1 / build 2** で **Archive まで済ませた**

```
~/Library/Developer/Xcode/Archives/2026-08-27/デジタル書斎 2026-08-27 1.0.1-build2.xcarchive
```

**残り（オーナーが手で行う）**: Xcode → Window → Organizer → 上のアーカイブを選ぶ →
Distribute App → App Store Connect → Upload → App Store Connect で 1.0.1 を作って build 2 を選び、
「このバージョンの新機能」に `アプリアイコンを新しくしました。` と書いて審査へ提出。

**アイコンの作り直し方は `icon-src/make_icon.py` の冒頭に書いた。**
支給画像は白背景に角丸アイコンが乗った形なので、**そのまま渡すとホーム画面で角が白く欠ける**。
スクリプトが「本体を切り出す → 1024へ → 角の外を地色で塗る」まで面倒を見る。

---

## 1. いまの状態（2026-08-19 メインPCで実測）

| | 状態 |
|---|---|
| Web版の機能 | **完成**。取り込み（索引だけ）／本棚（表紙）／読書（テキスト）／紙面表示／検索／書き出し・読み込み |
| ビルド | `npm run build` 成功（静的書き出し `out/`）。`npx tsc --noEmit` エラー0 |
| **Capacitor化** | **済**（2026-08-19）。`com.shinsei.shosai` / 表示名「デジタル書斎」/ 1.0.0 (build 1) |
| **シミュレータ確認** | **済**（iPhone 17 Pro Max・iOS 26.5）。取り込み→本棚→読書→紙面→検索まで通した |
| **アイコン** | **割り当て済**（`icon-src/icon_1024.png` → `ios/App/App/Assets.xcassets/AppIcon.appiconset/`。アルファ無し） |
| **スクリーンショット** | **済**。`store/screenshots/iphone-6.9/`（1290×2796・5枚）と `store/screenshots/ipad-12.9/`（2048×2732・5枚） |
| **iPad** | **対象にする**（2026-08-19 オーナー判断）。iPad Pro 13-inch シミュレータで同じ5画面を確認・撮影済み |
| **収録作品（同梱）** | **済**。`public/books/` に青空文庫4冊（著作権保護期間満了）。初回起動で自動的に書斎へ入る |
| **提出** | **済**（2026-08-19）。App Store Connect のアプリ登録・ストア情報・審査提出まで完了 |
| 未着手 | PWA化（manifest/service worker）、実機（iPhone）での確認 |

### 収録作品（同梱）について ― 審査で聞かれても答えられるように

`public/books/` に入れている4冊は**すべて著作権保護期間が満了した作品**（青空文庫より。
羅生門／走れメロス／銀河鉄道の夜／こころ）。テキストを整形して自前でPDF化したもので、
青空文庫のファイルをそのまま再配布しているわけではない。**自炊本は入っていない。**

- 初回起動時に蔵書が0冊なら自動で取り込む。印は localStorage（`shosai-bundled-loaded`）。
  **消した本は復活させない**（起動のたびに戻ってくると邪魔になるため）
- 取り込み画面の「収録作品を入れる」でいつでも入れ直せる
- 同梱本は原本がアプリの中にあるので、**紙面表示のときに原本PDFを選び直す必要がない**
  （`BookRecord.bundled` にファイル名を持たせ、読書画面が自分で開く）

**設計の要点（審査説明でもそのまま使える）**

- 取り込むのは**本文テキストだけ**。ページ画像は開いたときに作って貯める
- 原本PDFは**利用者の元の場所（クラウド等）に置いたまま**。アプリに複製を溜め込まない
- **外部送信ゼロ**。通信は一切しない（広告もアカウントも無い）

---

## 2. 前提（ここを外すと事故る）

- **配信用証明書はメインPCだけ**。サブPCには Apple Development しか無い（実測: Distribution 0件・プロビジョニングプロファイル0件）
- **再提出のときはビルド番号を必ず +1**。`./ios-build-guard.sh digital-shosai` で衝突を確認してから Archive
  （2026-07-22に build 1 のまま再アップして**修正前のビルドが審査を通った**事故がある）
- **著作権表記は `SHINSEI PROPERTY MANAGEMENT.K.K.`**（2026-08-19確定。他アプリも同じ表記。
  サポート／プライバシーページのフッターの日本語表記とは別物）
- **自炊した本（Dropboxの書籍フォルダ）は絶対に同梱しない。** 審査用は `samples/` の自作PDFだけ

---

## 3. 手順

> ①②③は 2026-08-19 に実施済み。**やり直す必要はない**（`ios/` を消したときだけ②から）。
> 実際に踏んだ手順と、そのとき直した不具合は「7. 2026-08-19 にやったこと」に書いた。

### ① PWA化（アプリ化の前に、Web版として動作を固める）

```bash
cd ~/digital-shosai
# public/manifest.webmanifest と アイコン（icon-src から 180/152/120 を public/ へ）
# app/layout.tsx の <head> に manifest とテーマカラーを追加
npm run build && npx serve out    # 端末のブラウザで「ホーム画面に追加」して確認
```

ホーム画面から起動すると保存の扱いが良くなる（iOSで実測: タブ起動だと申告上限1000MB）。

### ② Capacitor で包む

```bash
cd ~/digital-shosai
npm i -D @capacitor/cli && npm i @capacitor/core @capacitor/ios
npx cap init "デジタル書斎" com.shinsei.shosai --web-dir=out
npx cap add ios
npm run build && npx cap copy && npx cap open ios
```

- **`ios/` は .gitignore に入る**（他アプリと同じ作法）。`cap add ios` をやり直すとビルド番号が1に戻るので注意
- Xcode で: 表示名「デジタル書斎」／`CURRENT_PROJECT_VERSION` を 1 →（再提出時は +1）／
  `MARKETING_VERSION` 1.0.0 ／ アイコンに `icon-src/icon_1024.png` を割り当て
- 向き: 縦のみで良い（読書アプリ）。iPad 対応は任意（対応するならスクショも必要）

### ③ 動作確認（実機かシミュレータ）

1. `samples/デジタル書斎-サンプル.pdf` を「ファイル」アプリ経由で取り込む → 4ページ・検索できる
2. Dropbox のPDFを選んで取り込む（**Dropboxアプリが入っていること**が前提）
3. 本棚に表紙が出る → 開く → 本文が読める → 「紙面を見る」で画像が出る
4. アプリを再起動しても蔵書が残る（保存が効いている）

### ④ App Store Connect

下の「5. 登録内容の案」をそのまま使えるように用意した。スクリーンショットは
**iPhone 1284×2778／iPad 2048×2732** に `sips` で合わせる（新しいシミュレータの解像度は弾かれる）。

### ⑤ 提出

`./ios-build-guard.sh digital-shosai` → Archive → Upload → **今上げたビルド番号が選択肢に出ることを確認**してから提出。

---

## 4. iOS で分かっている制約（実機で測った事実。実装は既に対応済み）

| 事実 | 対応 |
|---|---|
| **WebP を書き出せない**（`toDataURL("image/webp")` がPNGで返る。1ページ583〜670KB） | 画像は **WebP→JPEG→PNG** の順に試して、実際に書き出せた形式を使う（実装済み） |
| **フォルダ指定ができない**（`showDirectoryPicker`・`showOpenFilePicker` とも false） | `<input type="file" multiple>` で「ファイル」アプリから複数選択（実装済み）。**フォルダ指定を入れるなら Swift の自作プラグインが必要**（v1では不要） |
| **プライベートブラウズだと保存が失敗**（エラー内容 null・上限1000MB） | 起動時に1KB書いて判定し、理由を画面に出す（実装済み）。アプリ版では起きないが警告は残す |
| 1ページの描画＋圧縮 **60〜110ms** | 体感の問題なし |
| Chrome/Edge も中身は Safari（`vendor: Apple`） | iOSでは全ブラウザ同じ挙動として扱う |

**未確認**: Capacitor（WKWebView）の中での IndexedDB の上限。アプリ扱いで緩くなる見込みだが実測していない。
③の動作確認で、10冊ほど入れて `本棚` の使用量表示を見ておくとよい。

---

## 5. App Store Connect に実際に登録した内容（2026-08-19時点）

**案ではなく、いま入っている値。** 次のバージョンでも基本はこれを踏襲する。

| 項目 | 値 |
|---|---|
| 名前 | デジタル書斎 |
| サブタイトル | PDFを本棚へ。全文検索できる書斎 |
| カテゴリ | プライマリ **ブック** ／ セカンダリ **ビジネス** |
| 著作権 | `SHINSEI PROPERTY MANAGEMENT.K.K.` |
| サポートURL | https://shinsei99.github.io/project/digital-shosai-support/ |
| プライバシーポリシーURL | https://shinsei99.github.io/project/digital-shosai-support/privacy.html |
| Apple ID / SKU | 6803002980 ／ `com.shinsei.shosai` |
| キーワード | 自炊,電子書籍,青空文庫,読書,資料,検索,OCR,オフライン,ドキュメント,ビューア,論文,教科書,マニュアル,蔵書,参考書,勉強,書類,索引 |
| プロモーション用テキスト | 青空文庫の名作4冊（羅生門・走れメロス・銀河鉄道の夜・こころ）を収録。開いてすぐ「全文検索して読む」を試せます。手持ちのPDFを足せば、そのまま自分専用の書斎に。取り込むのは本文の文字だけなので軽く、通信は一切行いません。 |

**スクリーンショットは3サイズ用意してある**（`store/screenshots/`）。
バージョン1.0の枠が要求したのは **6.5インチ（1284×2778）**。6.9インチ（1290×2796）と
iPad 12.9インチ（2048×2732）も同じ5画面で揃えてある。

- **年齢**: 4+
- **説明文（登録済みのものは下より詳しい。要点は同じ）**

> 手持ちのPDFを取り込むと、本文をまるごと検索できる「自分専用の書斎」になります。
>
> ・取り込むのは本文の文字だけ。保存はわずかで、何百ページの本でも軽く扱えます
> ・本棚に表紙が並び、開くとテキストで読めます。文字の大きさ・行間・書体を調整できます
> ・図や表を見たいときは、その場でページの紙面を表示します
> ・調べたい語を入れると、どの本の何ページに書かれていたかがすぐ分かります
> ・原本のPDFは、いま置いている場所（クラウドのフォルダなど）に置いたままで構いません
>
> すべて端末の中だけで動きます。通信は一切せず、外部のサーバーへ何も送りません。
> 広告もアカウント登録もありません。
>
> ※ 文字が埋め込まれていないPDF（スキャンしただけのもの）は検索できません。先にOCRしてください。

- **プライバシー**: 収集するデータ **なし**（トラッキングなし・第三者提供なし）
- **サポート／プライバシーページ**: gh-pages の `digital-shosai-support/`（2026-08-19作成）。
  直すときは gh-pages ブランチを触る。反映まで1分ほどかかる
- **審査への備考（App Review Notes）案** ※2026-08-19 に実物に合わせて書き直した

> このアプリは利用者自身のPDFを読み込んで、本文を全文検索して読む道具です。
> 初回起動時に、著作権保護期間が満了した作品（青空文庫より・羅生門／走れメロス／
> 銀河鉄道の夜／こころ）が自動的に書斎へ入ります。動作確認はそのままお試しいただけます。
> 「検索」で「友」と入力すると、どの本の何ページにあるかが一覧で表示されます（39件）。
> 本棚で表紙をタップすると本文が読め、「紙面を見る」でそのページの実際の紙面が出ます。
> 通信は行いません。アカウント登録も不要で、収集するデータはありません。

> **旧案の誤り（残しておく）**: 以前の案は「同梱のサンプルPDFを取り込み、
> 『オフライン』で検索」と書いていたが、**サンプルPDFは同梱されておらず**、
> その語も本文に無いため**検索結果は0件**だった（2026-08-19にシミュレータで確認）。
> 審査ノートに書く操作は、必ず実機／シミュレータでなぞってから書く。

---

## 6. やらないこと（方針として決めてある）

- **広告を入れない**（2026-08-17に全撤去。再検討するなら AdMob＋別途判断）
- **外部送信しない**（バックアップもファイル書き出し方式。クラウドに上げない）
- **自炊本を同梱しない**（私的複製の範囲を超える）
- OCRのLLM補正は**既定オフの任意機能としてのみ**検討（外部送信になるため）

---

## 7. 2026-08-19（メインPC）にやったこと ― Capacitor化とシミュレータ確認

`npx cap add ios`（Capacitor 8.5.0・**CocoaPodsではなく Swift Package Manager**）で包み、
iPhone 17 Pro Max（iOS 26.5）のシミュレータで**取り込み→本棚→読書→紙面→検索**まで通した。
そこで見つけて直した不具合を残す（**どれも画面を見なければ気づけなかったもの**）。

| 症状 | 原因 | 直し方 |
|---|---|---|
| 見出しと「検索／本棚」が**時計・電池と重なる** | WKWebViewは画面いっぱいに描くのに、safe-area を避けていなかった | `viewport-fit=cover`（`layout.tsx` の `viewport`）＋ `header { padding-top: env(safe-area-inset-top) }`（`globals.css`） |
| ページを送るたびに**本文の枠が伸び縮みし、前/次のボタンが動く** | 枠の高さが中身任せだった | 読書画面を「見出し／枠／ページ送り」の縦3段にし、**枠だけ高さ固定＋中身をスクロール**（高さは実測して決める） |
| ページ番号の入力欄を触ると**画面ごと拡大してずれ、閉じても戻らない** | iOSは**16px未満の入力欄**に触れると自動で拡大する。加えて変換候補バーで**横にも**ずれる | 入力欄を `text-base`（16px）に。`input/select/textarea { font-size: max(16px,1em) }` を保険で追加。入力中でなければ `window.scrollTo(0,0)` して測り直す |
| 本棚の「読みやすさ 35%」が取り込み画面の「読みやすさ 100%」と食い違う | 本棚は**素のひらがな率**、取り込みは0〜100%に正規化した値。同じ言葉を使っていた | 本棚の表記を「ひらがな率」に変えた（数字はどちらも正しい） |

**シミュレータの操作の仕方（次回のために）**: `xcrun simctl` にはタップが無いので、
Quartz でマウスイベントを送る小さなスクリプト（`tap.py` / `drag.py`）を作って操作した。
日本語入力は `keystroke` では化けるので **`xcrun simctl pbcopy` → ⌘V** で入れる。

## 8. Archive は作ってある（2026-08-19 17:36）

```
~/Library/Developer/Xcode/Archives/2026-08-19/デジタル書斎 2026-08-19 17.36.xcarchive
```

- **1.0.0 (build 1)** / `com.shinsei.shosai` / Team `773DPMVW7Q` / 19MB
- アイコン（iPhone・iPad）と**収録作品4冊**が中に入っていることを確認済み
- 署名は `Apple Development`＋ワイルドカードのプロファイル。**これでよい**。
  Organizer の「Distribute App」が配布用に**署名し直す**（配布証明書は Xcode が持っている。
  `security find-identity` には出てこないが、Xcode 14以降は
  **データ保護キーチェーン**に鍵を置くのでCLIからは見えないだけ）
- 作り直すコマンド:

```bash
cd ~/digital-shosai && npm run build && npx cap copy
xcodebuild -project ios/App/App.xcodeproj -scheme App -configuration Release \
  -destination 'generic/platform=iOS' -archivePath ~/digital-shosai/build/App.xcarchive \
  archive DEVELOPMENT_TEAM=773DPMVW7Q CODE_SIGN_STYLE=Automatic -allowProvisioningUpdates
# ★Organizerに出すには ~/Library/Developer/Xcode/Archives/<日付>/ へ移すこと（別の場所だと一覧に出ない）
```

**注意: アーカイブを作った後に `./ios-build-guard.sh digital-shosai` を叩くと必ず「衝突リスク」と出る。**
いま作ったアーカイブ自身を数えるため。**判定はArchiveの前に行う**（前に叩いたときは「衝突なし」だった）。

### 次にやること（Distribute の前に必要）

1. **App Store Connect でアプリを登録する**（名前・SKU・バンドルID `com.shinsei.shosai`）。
   登録前に Distribute すると `DistributionAppRecordProviderError error 0` で落ちる
   （KeyTag で実際に踏んだ。登録後も古いキャッシュが残るので**Xcodeを再起動**する）
2. Organizer → Distribute App → App Store Connect → Upload
3. アップロード後、App Store Connect でスクショ・説明文・プライバシーを埋めて審査へ提出

## 9. 提出前チェックリスト

- [x] `npm run build` が通る／`npx tsc --noEmit` が0件
- [x] `npx cap copy` 済み（`out/` の最新が `ios/` に入っている）
- [ ] `CURRENT_PROJECT_VERSION` が既存アーカイブより大きい（`./ios-build-guard.sh digital-shosai`）
      ※初回提出なので build 1 のまま。**2回目以降は必ず +1**
- [x] アイコン割り当て済み（`icon-src/icon_1024.png`・アルファなしを確認済み）
- [x] 収録作品が初回起動で入る（シミュレータで確認。4冊352ページ・索引 679KB）
- [x] シミュレータで「取り込み→本棚→読書→紙面→検索」を確認
- [x] スクリーンショット（`store/screenshots/iphone-6.9/`・1290×2796・5枚）
- [x] **iPadも対象にする**（2026-08-19判断）。`store/screenshots/ipad-12.9/`・2048×2732・5枚。
      `TARGETED_DEVICE_FAMILY` は既定の `1,2` のまま（変更不要）
- [ ] 実機（iPhone）で1度は通す
- [ ] プライバシーポリシーのURLが開ける
- [x] 著作権表記は `SHINSEI PROPERTY MANAGEMENT.K.K.`（他アプリと同じ既定）
- [ ] 提出後、`digital-shosai/SESSION_LOG.md` に結果を追記（ビルド番号と提出日を残す）
