# SESSION_LOG.md — デジタル書斎 作業ログ

新しい項目は上に追記する（上が新しい）。書式はルート `CLAUDE.md` の作業ルール参照。

---

## 2026-08-27（メインPC）— アイコンを差し替え、1.0.1 / build 2 を審査へ提出まで

### 完了したこと

- **1.0 は審査を通って「配信中」になっていた**（`appstore_api.py --review` で実測）。
  8/24時点の「審査待ち」から変わっていたので、`CLAUDE.md` と `TODO.md` の記載を直した。
  ついでに photo-remake も 1.1.0 が配信中になっていたので同じく直した
- **アイコンをオーナー支給の画像に差し替えた**（開いた本＋銀色の虫めがね・濃紺の地）。
  原本は `icon-src/source_2026-08-27.png` として git に入れた（1254×1254）
- `icon-src/make_icon.py` を「図案を描く」から「**支給画像を整える**」形に書き換え。
  出力は従来どおり `icon_1024/180/152/120/76/60.png`（RGB・アルファ無し）
- `ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-512@2x.png` を差し替え
- **`MARKETING_VERSION` 1.0.0 → 1.0.1 ／ `CURRENT_PROJECT_VERSION` 1 → 2**
  （`./ios-build-guard.sh digital-shosai --bump` ＋ 表示バージョンは手で）
- `npm run build` → `npx cap sync ios` → **Archive 成功**。Organizer に出るよう
  `~/Library/Developer/Xcode/Archives/2026-08-27/デジタル書斎 2026-08-27 1.0.1-build2.xcarchive`（22MB）へ配置
- **Archive の中身を目で確認**: `Info.plist` が 1.0.1 / build 2 / `com.shinsei.shosai`、
  `AppIcon60x60@2x.png`（iPhone）と `AppIcon76x76@2x~ipad.png`（iPad）が**新しい絵になっている**
- **App Store Connect へアップロード完了**（オーナー依頼で追加実施）。**Organizer を開かず
  コマンドだけで通した**（手順は `HANDOFF-APPSTORE.md` 冒頭にも同じものを置いた）

```bash
# ① 配布用に署名し直して .ipa を書き出す（Distribution 証明書は Xcode が持っている）
xcodebuild -exportArchive -archivePath build/App.xcarchive \
  -exportOptionsPlist ExportOptions.plist -exportPath build/export \
  -allowProvisioningUpdates \
  -authenticationKeyPath ~/.appstore/AuthKey_35U53KWY5J.p8 \
  -authenticationKeyID 35U53KWY5J -authenticationKeyIssuerID e55bd1b7-1481-4ee1-9c7e-8caac82815b1
# ② 検証 → ③ アップロード
xcrun altool --validate-app -f build/export/App.ipa -t ios \
  --apiKey 35U53KWY5J --apiIssuer e55bd1b7-1481-4ee1-9c7e-8caac82815b1
xcrun altool --upload-app   -f build/export/App.ipa -t ios \
  --apiKey 35U53KWY5J --apiIssuer e55bd1b7-1481-4ee1-9c7e-8caac82815b1
```

- `EXPORT SUCCEEDED` → `VERIFY SUCCEEDED` → `UPLOAD SUCCEEDED`
  （Delivery UUID `79457332-c9fd-49ea-801d-9270fc91d2a9`・**`.ipa` 10,941,582 バイト**を1.3秒で転送）
- `ExportOptions.plist` を**git に入れた**（`build/` は gitignore なので中に置くと消える）。
  要点: `method=app-store-connect` / `teamID=773DPMVW7Q` / `signingStyle=automatic` /
  **`manageAppVersionAndBuildNumber=false`**（true だと Xcode が版数を勝手に書き換える）
- **受理を確認**: `python3 appstore_api.py com.shinsei.shosai` で **`build 2 … VALID`**
  （アップロードの**約1分後**に処理完了。build 1 も VALID のまま並ぶ）
- **オーナーが App Store Connect の画面で 1.0.1 を審査へ提出**（「このバージョンの最新情報」は
  `アプリアイコンを新しくしました。`）。API でも確認: **`配信中 1.0 ／ 審査中のもの 1.0.1 … 審査待ち`**

### 発生したエラーと解決策

- **支給画像をそのまま使うと、ホーム画面で角が白く欠ける** → 原因: 支給画像は
  「白背景の上に角丸の正方形アイコンが乗った」状態（周囲に約26pxの白余白）。iOS は自分で
  角丸マスクを掛けるので、渡す画像は**角まで塗った四角**でなければならない →
  直し方: `make_icon.py` で ①角丸正方形の本体だけ切り出し（暗い画素が縦横に600px以上連なる範囲）
  ②1024へ縮小 ③**角丸の外側を地色 `(23,32,45)` で塗り潰す**（半径239px＝iOSの約229pxより少し大きい）。
  iOSマスクを掛けた状態を画像で並べて目視し、白い縁が出ないことを確認した
- **Archive 内のアイコンPNGが PIL で開けない**（`broken data stream`） → 原因: Xcode が
  iOS向けにPNGを最適化する（CgBI形式）ため → 直し方:
  `xcrun -sdk iphoneos pngcrush -revert-iphone-optimizations` で戻してから見る
- **`altool` が `.p8` を見つけられない**（`Failed to load AuthKey file. (-43)`） → 原因:
  `altool` は `--apiKey` にパスを取らず、**決まった場所しか探さない**
  （`~/private_keys` / `~/.private_keys` / `~/.appstoreconnect/private_keys` ほか）。
  この環境の鍵は `~/.appstore/` にある（`appstore_api.py` はパスで読むので気づかない） →
  直し方: `~/.appstoreconnect/private_keys/` へコピー（`chmod 600`）。**鍵は増やさず同じもの**

### 次回への引き継ぎ事項・未解決の課題

**このアプリで今やることは無い。審査の結果を待つだけ。**

- **1.0.1 / build 2 は審査待ち**（2026-08-27 提出）。見るときは
  `python3 appstore_api.py --review com.shinsei.shosai`（審査状況）と
  `python3 appstore_api.py com.shinsei.shosai`（ビルド一覧）。
  **通ったら `CLAUDE.md` と直下 `TODO.md` を「1.0.1 が配信中」へ書き換える**
- **アイコンが App Store のページと端末で新しくなるのは、1.0.1 が配信されてから**。
  審査中はまだ旧アイコンが出る（不具合ではない）
- **もし差し戻されたら**: アイコンだけの変更なので中身の指摘は考えにくいが、
  出し直すときは**必ず build 3 へ**（`./ios-build-guard.sh digital-shosai --bump`）。
  Archive → アップロードは `HANDOFF-APPSTORE.md` 冒頭の3コマンドでGUIなしに通る
- **実機（iPhone）で1度通すのは依然として未了**（シミュレータのみ。手順は `HANDOFF-APPSTORE.md`）
- **PWA化（manifest / service worker）も未着手**。アプリ版には必須ではない

---

## 2026-08-24（メインPC）— 審査状況を API で確認（変化なし・待ち）

### 完了したこと

- `python3 appstore_api.py --review com.shinsei.shosai` で実測。
  **1.0 は `WAITING_FOR_REVIEW`（審査待ち）のまま。提出から5日経過（作成日 2026-08-19）。**
  build 1（2026-08-19 アップロード）は `VALID` ＝受理済みなので、こちらの作業は無い
- ルート `CLAUDE.md` と `TODO.md` の確認日を 2026-08-24 に更新

### 発生したエラーと解決策

- なし

### 次回への引き継ぎ事項・未解決の課題

- **審査結果を待つだけ。** 見るときは `python3 appstore_api.py --review com.shinsei.shosai`
- **実機で1度通すのは未了**（手順は `HANDOFF-APPSTORE.md`）

---

## 2026-08-19（メインPC）— iOSアプリとして包み、シミュレータで通し確認＋ストア用スクショ

### 完了したこと

- **Capacitor化**（Capacitor 8.5.0 / **SPM方式**・CocoaPods不要）。`com.shinsei.shosai`・
  表示名「デジタル書斎」・**1.0.0 (build 1)**。`ios/` は gitignore（`digital-shosai/ios/` を追加）
- **アイコンを割り当て**（`icon-src/icon_1024.png` → `AppIcon.appiconset`。アルファ無しを確認）
- **iPhone 17 Pro Max（iOS 26.5）のシミュレータで通し確認**:
  「ファイル」アプリからPDF取り込み → 本棚（表紙）→ 読書 → 紙面（その場で描画）→ 検索（ハイライト）
- **収録作品を同梱した**（オーナー判断「著作権切れならデフォルトで入れておいて」）。
  青空文庫の**著作権保護期間が満了した4作品**（羅生門／走れメロス／銀河鉄道の夜／こころ）を
  自前でPDF化して `public/books/` に置き（5.7MB）、**初回起動時に自動で書斎へ入る**。
  実測: **4冊352ページ・本文22万字 → 索引 679KB**（原本5.7MBに対して約12%）。
  消した本は復活させない（印は localStorage `shosai-bundled-loaded`）。
  同梱本は `BookRecord.bundled` を見て**紙面表示でも原本を選び直さずに開ける**
- **ストア用スクショ**（本棚・読書・検索・紙面・取り込み）:
  `store/screenshots/iphone-6.9/`（**1290×2796**・5枚）と
  `store/screenshots/ipad-12.9/`（**2048×2732**・5枚）
- **iPadも対象にする**（オーナー判断）。iPad Pro 13-inch (M5) のシミュレータで同じ5画面を確認。
  `TARGETED_DEVICE_FAMILY` は既定の `1,2` のままでよい
- **シミュレータ操作の道具をリポジトリに置いた**（`simtap.py`）。次のiOSアプリでも使える
- **Archive を作成**（17:36）。`~/Library/Developer/Xcode/Archives/2026-08-19/デジタル書斎 …xcarchive`。
  1.0.0 (build 1)・19MB。中身（アイコン・収録作品4冊・版数）を確認済み。
  署名は Apple Development＋ワイルドカードのプロファイルで、**Distribute時に配布用へ署名し直される**
- `HANDOFF-APPSTORE.md` を実物に合わせて更新（審査ノートの誤りも訂正）

### 発生したエラーと解決策

- **見出しが時計・電池と重なる** → WKWebViewは画面いっぱいに描くのに safe-area を避けていなかった
  → `viewport-fit=cover` ＋ `header { padding-top: env(safe-area-inset-top) }`
- **ページを送るたびに本文の枠が伸縮し、前/次ボタンが動く**（オーナー指摘）→ 枠の高さが中身任せだった
  → 読書画面を縦3段（見出し／枠／ページ送り）にし、**枠だけ高さ固定＋中身をスクロール**。
  高さは `getBoundingClientRect().top` から実測して決める（env() の計算に頼らない）
- **ページ番号の入力欄を触ると画面ごと拡大してずれ、閉じても戻らない** → iOSは**16px未満の入力欄**で
  自動拡大する。さらに変換候補バーで**横**にもずれる → 入力欄を16pxに（`input/select/textarea` にも
  下限を引いた）＋入力中でなければ `window.scrollTo(0,0)` して測り直す
- **審査ノート案の検索語「オフライン」が0件** → サンプルPDFにその語が無く、そもそも**同梱もされていなかった**
  → ノートを実際の操作（収録作品を「友」で検索＝39件）に書き直した
- **本棚の「読みやすさ35%」が取り込み画面の「100%」と食い違う** → 前者は素のひらがな率、後者は正規化値。
  同じ言葉を使っていたのが原因 → 本棚を「ひらがな率」表記に
- シミュレータにはタップ操作のAPIが無い → Quartz でマウスイベントを送る `tap.py`/`drag.py` を用意。
  **日本語入力は `keystroke` だと化ける**ので `xcrun simctl pbcopy` → ⌘V で入れる

### 提出まで完了（本人が実施・2026-08-19）

**App Store へ審査提出済み（1.0.0 / build 1）。** Apple ID 6803002980。
アプリ登録は**既に存在していた**ため、`DistributionAppRecordProviderError` の原因は
Xcode のキャッシュのみだった（Xcode再起動で解消）。App ID もアーカイブ時に自動登録されていた。

このセッションで入れたストア情報:

| 項目 | 内容 |
|---|---|
| サブタイトル | PDFを本棚へ。全文検索できる書斎 |
| プロモーション用テキスト | 収録作品4冊を先に出し「すぐ試せる」を強調（111字） |
| 概要 | 機能・収録作品・原本は置いたまま・完全オンデバイス・未OCRの注意（約570字） |
| キーワード | 自炊,電子書籍,青空文庫,読書,資料,検索,OCR,オフライン,ドキュメント,ビューア,論文,教科書,マニュアル,蔵書,参考書,勉強,書類,索引（72字） |
| サポートURL | https://shinsei99.github.io/project/digital-shosai-support/ ← **ママカウンターのURLが入っていたのを差し替え** |
| プライバシーポリシーURL | 同 `/privacy.html`（gh-pages に新規作成） |

**スクショの寸法は3種類用意した**（`store/screenshots/`）。バージョン1.0の枠が要求したのは
**6.5インチ（1284×2778）**で、最初に作った6.9インチ（1290×2796）だけでは足りなかった。

### 分かったこと（次の提出でも効く）

- **配布証明書は `security find-identity` に出てこない**が、Xcodeは持っている。
  Xcode 14以降は署名鍵を**データ保護キーチェーン**に置くのでCLIからは見えないだけ
  （過去の提出はこのMacから通っている）。「証明書が無い」と早合点しない
- **Archive後に `ios-build-guard.sh` を叩くと必ず「衝突リスク」と出る**（作ったばかりの
  アーカイブ自身を数えるため）。**判定はArchiveの前に行う**
- `-archivePath` に別の場所を指定すると **Organizer の一覧に出ない**。
  `~/Library/Developer/Xcode/Archives/<日付>/` へ移すこと

### 次回への引き継ぎ事項・未解決の課題

- **審査結果の確認**（通ったら CLAUDE.md と一覧を「配信済み」へ）
- **実機（iPhone）では未確認**。シミュレータのみ
- ~~著作権欄の表記~~ → **`SHINSEI PROPERTY MANAGEMENT.K.K.` が既定**で決着（2026-08-19オーナー判断）。
  他アプリも同じ表記。メモリ [[reference_developer_entity]] の「新誠プロパティマネジメント」は誤りだったので訂正済み
- PWA化（manifest/service worker）は未着手。アプリ版には必須ではない
- 同梱PDFで5.7MB増える。アプリサイズを抑えたいなら「こころ」(3.0MB) を外す選択もある

---

## 2026-08-17（夜・サブPC）— 索引方式へ作り替え、本棚と読書画面を作った

### 完了したこと
- **設計変更**: 取り込みは**本文テキストだけ**（テキスト抽出は1ページ1ms／画像化は60〜110ms）。
  ページ画像は**開いたときに作ってキャッシュ**。114ページの本で端末内 **248KB**（従来方式なら約17MB）
- **表紙だけは取り込み時に作る**（幅480px・1冊30〜60KB）→ `/library` を**本棚**（表紙のグリッド）に
- **`/read`（読書画面）を新設**: 明朝/ゴシック・文字サイズ・行間、しおり、前後ページ、←→キー、
  検索語のハイライト、「紙面を見る」で原本から都度描画（原本が無ければその場で選ぶ・端末には保存しない）
- **索引の書き出し／読み込み**（バックアップ兼、端末間の受け渡し）
- **保存できない状態の検知**（起動時に1KB書く。プライベートブラウズだと無言で失敗していた）
- **複数ファイルの一括取り込み**（1冊ずつ確定・重複は飛ばす・未OCRは弾く）
- IndexedDB を v4 へ（`pageText` / `pageImage` / `cover`。v1・v2 のデータは自動移行）

### 本文の読みやすさ（実データで測って直した）
- 縦書きのページは1文字ずつ拾われる → 座標から列を復元。**崩れたページ 3/25 → 22/25 が読める形**に
- **柱とノンブルは段落連結の前に落とす**。順序が逆だと「1泊2食付」の「1」を削ってしまう（実際に踏んだ）
- ページ先頭の短い行は**見出しとして独立**させる（本文と繋げると「…戦略策定魔されないようにしていた」になる）
- 本ごとの読みやすさ（ひらがな率）とページ単位の崩れ検知を表示 → 崩れている所は「紙面を見る」へ誘導
- **本ごとの品質差の実測**: 690ページの本 41%（文字で読める）／382ページ 24%／114ページ 22%（図解多め）

### OCR補正の検討（ご要望「文脈で補正できないか」への回答）
- ルールベース（NFKC正規化・同形異字 `工`→`エ` 等）: ひらがな率 19.8% → **21.1%**、
  ゴミ行 7,861 → 6,705。**効果は小さいが副作用も小さい**ので入れる余地あり（未実装）
- ブラウザ内の再OCR（tesseract.js）: 日本語縦書きに弱く1ページ数秒・言語データ20MB超 → **保留**
- LLMでの文脈補正: 精度は最も高い見込みだが**外部送信が必須**。完全オンデバイス方針と衝突するため
  **既定オフの任意機能としてのみ**検討
- **規則で直せない例**: 「邪魔されない」→「魔されない」の脱字、図解の `ｎ工シ万弐` のような誤認

### 発生したエラーと解決策
- **症状**: 自動操作でPDFを選べない（`set_input_files` がタイムアウト）。
  **原因**: `<input type="file">` が `class="hidden"` で隠されていた。
  **直し方**: 一時的に表示状態へ戻してから渡す（`visual_agent.py` の upload を修正）。
- **症状**: 236MBの本を自動操作で流せない（`Cannot transfer files larger than 50Mb`）。
  **原因**: Playwright の制限（アプリ側の制限ではない）。**直し方**: 60ページの抜粋を作って検証した。
- **症状**: 本文の先頭が「企業レベルの戦略策定魔されないようにしていた。」になる。
  **原因**: 柱（章題）を本文と連結していた。**直し方**: 先頭の短い行を見出しとして独立させた。

### 次回への引き継ぎ事項・未解決の課題
- **App Store 提出はメインPC**（配信用証明書がそちらにしか無い）。手順は `HANDOFF-APPSTORE.md`。
  アイコン（`icon-src/icon_1024.png`）と審査用サンプルPDF（`samples/`）は用意済み
- PWA化（manifest＋service worker）は未着手。iPhone運用の前提なので提出前にやる
- 文字の正規化（上記ルールベース）は未実装
- Capacitor（WKWebView）内での保存上限は**未測定**
- Dropboxフォルダの一括指定は**アプリ版で Swift の自作プラグインが必要**（v1では不要）

---

## 2026-08-17（サブPC）— 広告を撤去し、容量・検索・蔵書管理を作り直した

### 完了したこと

- **広告と本棚スロット制限を全撤去**。`BannerAd` / `InterstitialAd` / `RewardedAd` /
  `ShelfMeter` を削除し、`profile` ストア・`addSlot()`・`FREE_BOOK_SLOTS`・`LIMIT_REACHED` も廃止。
  **冊数の上限は無くなった**（自分専用の道具で人為的に絞る意味がない）
- **ページ画像を WebP に**（`image/png` 固定 → ロスレスWebP → 品質90 → PNG の順に試し、
  返ってきた Blob の `type` で実際に使えた形式を確定）。同じPDFの同ページ・同倍率で実測:
  **PNG 41.4KB → ロスレスWebP 11.8KB（28.5%）**。容量が下がったので `RENDER_SCALE` を
  **1.5 → 2.0** に上げた（1.5は約108dpi相当で小さい字が読みづらかった）
- **検索を軽くした（IndexedDB v2）**。テキスト専用ストア `pageText` を新設し、`pages` は画像専用に。
  v1 は検索のたびに**画像を抱えたレコードを全件走査**していた。v1データは `upgrade` で自動移行
  （テキストを写し、本ごとの `imageBytes` / `imageMime` を集計）
- **検索の質**: 空白区切りの**複数語AND**、**本で絞り込み**（`/search?book=<id>` にも対応）、
  ヒット件数と**所要ms**の表示、ハイライトを複数語対応に
- **蔵書画面 `/library` を新設**（一覧＝ページ数・容量・形式・取込日時／削除）。
  `listBooks()` / `deleteBook()` は前からあったが画面が無く、**消す手段が存在しなかった**
- **`window.confirm` / `alert` を廃止**し、画面内の確認パネル・通知に置き換え
  （文字層の無いPDFの確認、PDF以外を選んだときの通知、本の削除確認）
- 蔵書メーターを**実際の使用容量**表示に変更（`navigator.storage.estimate()`。取れない環境は
  保存時に記録した `imageBytes` の合計で代替）
- 削除ボタンに `aria-label` を付けた（読み上げ対応と、自動操作からの指定のため）

### 検証したこと（実測・2026-08-17）

- `npm run build` 成功（静的書き出し）／`npx tsc --noEmit` エラー0
- **実際にブラウザで通した**（`./va.sh` で `127.0.0.1:3010`）:
  テストPDF（3ページ・日本語テキスト層あり）を取り込み → 「3ページ・53.1 KB・画像は WEBP」と表示 →
  AND検索「減価償却 木造」で**1件・13ms**・正しく2ページ目 → 詳細ビューアで
  左に両語のハイライト・右にWebP画像が表示 → `/library` に一覧 → 削除 → 0冊になる
- UI崩れ検出（3画面）: 横スクロール・はみ出し・文字の重なり・小さすぎる文字・壊れた画像は**すべて0**。
  Console エラーは新規0件
- 小さいタップ領域が `/`=1件 `/library`=2件（ヘッダのナビ等・高さ20px）。**未対応**

### 発生したエラーと解決策

- **症状**: `npm run build` が型エラーで失敗。`db.objectStoreNames.contains("profile")` の
  `"profile"` が型に無いと言われる。
  **原因**: v2 のスキーマ定義から `profile` を消したので、型の上では存在しない名前になった。
  ただし**既存の端末には実体が残っている**ので、名前で消す必要がある。
  **直し方**: `DOMStringList` として受けて `contains` し、削除は `IDBDatabase` に落として呼ぶ。
- **症状**: `npm run dev` が `*:3010`（LAN公開）で待ち受けた。
  **原因**: Next.js の dev サーバーは**既定で `0.0.0.0`**。Streamlit と同じ罠。
  **直し方**: `--hostname 127.0.0.1` を明示。READMEにも書いた。ツール分類は社内共有しない決まり。
- **症状**: 自動操作で「削除」をクリックしたら、ボタンではなく**メーターの説明文**（「…不要な本を
  削除してください」）に当たり、確認パネルが出なかった。
  **原因**: テキスト一致のセレクタが本文に先にマッチした。
  **直し方**: 削除ボタンに `aria-label` を付け、そちらを指定して操作。UI側の改善にもなった。

### 次回への引き継ぎ事項・未解決の課題

- **バックアップ（書き出し／読み込み）が無い。** 端末内だけの設計なので**端末が壊れると全消失**。
  外部送信しない方針のまま、ファイルへ書き出す仕組みが最優先の残件
- 削除しても `navigator.storage.estimate()` の使用量は**すぐに縮まない**（実測 64.9KB → 70.9KB）。
  IndexedDBが領域を再利用するためで異常ではないが、ユーザーには誤解を与えうる
- 小さいタップ領域（24px未満）が3件。ヘッダのナビを含むので、直すならレイアウト側
- PWA化（オフライン起動）、未OCR PDFのブラウザ内OCR（tesseract.js）、Capacitor化は未着手。
  **iOS配信用の証明書はメインPCにしかない**
