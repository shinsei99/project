# SESSION LOG — スクラップメモ（scrapmemo-petapeta）

## 2026-08-18（メインPC）

### 完了したこと
- **「スクラップ編集の上部が編集できない」不具合を修正**（`index.html` のみ・Web/iOS共通）
  - **Xcodeシミュレータ（iPhone 17 / iOS 26）でビルドして再現させた**。前回(2026-08-17)は
    Safari 390×844 だけで見ていたため、**キーボードが出ている間だけ起きる**この不具合を
    見逃していた
  - 修正は2点。① `.sh-box` の `max-height` を `96vh` → **`96%`**（親＝`.sheet-wrap` 基準）
    ② シート共通の `fitOpenSheets()` を追加し、`visualViewport` の resize/scroll で
    開いているシート全部の高さを追従させる（Web用に、キーボードが覆う分だけ
    `.sheet-wrap` の `padding-bottom` も足す）
  - `openMemo` / `openTodo` が個別に持っていた `maxHeight` 設定を `fitOpenSheets()` に集約。
    閉じるときは `clearSheetFit()` で戻す（3か所）
- 検証（すべて実測値）

  | | 修正前 | 修正後 |
  |---|---|---|
  | iOSシミュレータ・キーボードあり | box **-310**/538 h848 ／ memo-editor top **-222** | box **22**/538 h516 ／ memo-editor top **109** |
  | iOSシミュレータ・キーボードなし | — | box 1/840 h839（末尾のキャンセル/完了まで到達可） |
  | Chrome 390×844（Web版・キーボードなし） | — | box 34/844 h810 ／ 1行目から表示 |
  | Chrome（`visualViewport` を500に偽装＝Safariのキーボード想定） | — | padding-bottom 344px ／ box 20/500 h480 |

  画面でも確認: 修正前は**第9行目から**しか見えずヘッダーも画面外、修正後は
  **ヘッダー「スクラップ編集」＋第1行目**から表示される

### 完了したこと（続き・実タップでの最終確認）
- **アクセシビリティ（補助アクセス）を `ターミナル` に許可してもらい、シミュレータを実際に
  タップして確認できるようにした。** 座標変換とタップは `swiftc` で作った小さな CGEvent
  ツール（`tap.swift`）で行う。`osascript` の `click at` は `-25204` で使えない
- 実タップ＋実キーボードで確認: 40行のメモを開いて文字欄をタップ →
  **ヘッダー「スクラップ編集」＋第1行目から表示**（修正前は第9行目から・ヘッダーは画面外）。
  TODOシートも同じくキーボードの上に正しく収まることを確認
- **データ保管の実測（今回の追加調査）**
  - このWKWebViewの `localStorage` 上限は **5,100 KB（約5MB）**。超えると
    `QuotaExceededError: The quota has been exceeded.`
  - 写真は `addImageBlock` が **縮小も圧縮もせず元ファイルのまま dataURL(base64)** で保存する
    （base64は約1.37倍に膨らむ）。iPhoneの写真1枚（2〜4MB）で**上限に届く**
  - **`save()` が `catch(e){}` で例外を握りつぶしている**ため、上限超過が起きても
    画面上は貼れているように見え、**警告も出ないまま次回起動時に消える**。実測で確認:
    3.0MBの画像を足して `save()` → 保存済みデータに画像が入っていない／トーストも出ない

### 完了したこと（続き・写真の容量対策 その1）
- **写真を保存前に縮小するようにした**（`shrinkImageDataURL`）。長辺1600px・JPEG品質0.82。
  入口は2か所とも通す: `addPhotoToPage`（写真タブ）と `addImageBlock`（編集中に写真挿入）
  - もともと小さい画像（長辺1600px以下かつ400KB以下）は**触らない**（再エンコードで劣化させない）
  - JPEGは透明を持てないので白地を敷いてから描画。縮小後に**かえって増えたら元のまま**
  - 読めない画像は元のまま通す（写真を失わない方を優先）
- **入れ物についての実測（重要）**
  - `localStorage` の上限は **5,100KB**。これは**WebKitが掛けている固定の制限**で、
    **iPhone本体の空き容量とは無関係**（設定やCapacitorのオプションでは広げられない）
  - 保存場所自体はiPhone本体: アプリのサンドボックス内
    `Library/WebKit/com.shinsei99.scrapmemo/…/LocalStorage/localstorage.sqlite3`（SQLite1個）
  - **同じ端末で `navigator.storage.estimate()` は quota = 9,830 MB（約9.6GB）** を返す。
    ＝ IndexedDB 側なら「本体の容量が上限」に近い。**入れ物を替えれば広げられる**
- 縮小の効果（4032×3024の画像3種で実測。JPEGは中身で大きく変わるため幅で示す）

  | 画像の性質 | 元 | 無加工base64 | 縮小後 | 5MBに入る枚数 |
  |---|---|---|---|---|
  | 細かいノイズ（最悪） | 8.21MB | 10.95MB | 2,391KB | 約2枚 |
  | 写真に近い | 2.37MB | 3.17MB | 921KB | 約5枚 |
  | なめらか（最良） | 1.69MB | 2.26MB | 256KB | 約19枚 |

  → **1枚で上限だったのが5〜19枚まで延びた**が、**根本解決ではない**。
  写真を本格的に使うなら画像だけ IndexedDB へ移すのが本筋

### 発生したエラーと解決策
- 症状: iOSでスクラップ編集を開いてキーボードが出ると、**シートの上部（ヘッダーとメモの先頭
  8行ほど）が画面の上へはみ出して触れなくなる**。スクロールしても戻せない
  → 原因: iOS(WKWebView)はキーボードが出ると**WebView自体が縮む**（`innerHeight` 874→538）。
  ところが `.sh-box{max-height:96vh}` の **`vh` は縮まない**うえ、`openMemo` が開いた瞬間に
  `visualViewport.height*0.97`（＝キーボード前の848px）を**インラインで焼き付けて**いて、
  以後**更新されなかった**。親 `.sheet-wrap` は538pxなのに子が848px、かつ
  `align-items:flex-end` なので、あふれた310pxは**下ではなく上へ**出る。
  はみ出した分はスクロール対象にならないため到達不能になる
  → 直し方: 上記の `96%` 化 ＋ `visualViewport` の resize/scroll への追従（`fitOpenSheets`）
- 症状: シミュレータでソフトキーボードが出ない（文字欄をタップしてもキャレットは動くが無反応に見える）
  → 原因: **I/O → Keyboard → Connect Hardware Keyboard が ON のまま**だった。
  ONだと本来は入力補助バーだけが出るが、このアプリは `setAccessoryBarVisible(false)` で
  **そのバーを消している**ので、結果として何も出ない。
  → 直し方: **メニューから外す**（`⇧⌘K`）。`defaults write com.apple.iphonesimulator
  ConnectHardwareKeyboard -bool false` は**効かなかった**（メニューの✓は付いたまま）。
  確認は System Events で `AXMenuItemMarkChar` を読むのが確実
- 症状: `osascript`（System Events）でシミュレータを操作できない
  → 原因: このMacで osascript に**補助アクセス（アクセシビリティ）が未許可**。`-1719` が出る。
  → 迂回: `simctl` には tap が無いので、**シミュレータに入った `.app` の `public/index.html` に
  一時的なテスト用スクリプトを差し込んで**（40行のメモを作る→`openMemo`→`focus()`＋`click()`）
  自動で状態を作り、`simctl io screenshot` で撮った。測定値は `position:fixed;bottom:0` の
  緑の小さいオーバーレイに出して読んだ（WKWebViewの `console.log` は `log stream` に出ない）。
  **リポジトリ側のファイルには入れていない**（md5一致で確認済み）
- 注意: 差し込んだ `focus()` だけではソフトキーボードは出ない。**`focus()` の直後に `click()`**
  を呼ぶと出る。またシミュレータは `defaults write com.apple.iphonesimulator
  ConnectHardwareKeyboard -bool false` ＋ **Simulator再起動**でソフトキーボードが出る状態になる

### 次回への引き継ぎ事項・未解決の課題

**この節だけ読めば明日そのまま続けられるようにしてある（2026-08-18 20:50 時点／メインPC）。**

#### 状態

- **コードの変更は `index.html` の1ファイルだけ。まだコミットしていない。**
  `npm run sync` 済みなので `www/` と `ios/App/App/public/` にも同じものが入っている（md5一致）
- 変更は2件だけ:
  1. シートの高さをキーボードに追従させる（`.sh-box{max-height:96%}` ＋ `fitOpenSheets()`）
  2. 写真を保存前に縮小する（`shrinkImageDataURL()`）
- **どちらもシミュレータ（iPhone 17）で実測確認済み。** バージョンは 1.0.3(7) のまま**上げていない**
- シミュレータには**素の修正版が入って起動している**（テスト用コードは全部剥がしてある。
  `public/index.html` に `99999;background:#0f0` が0件であることを確認済み）

#### 明日やると決めたこと（本人と合意済み・優先順）

1. **画像だけ IndexedDB へ移す**（＝「入れ物を大きくする」）。
   localStorage 5,100KB は WebKit 固定で広げられないが、**同じ端末で IndexedDB は quota 9,830MB**。
   作業の中身: 画像を別ストアに置きメモ側は id だけ持つ／表示時に読み出す（**非同期になる**）／
   既存写真の引っ越し／削除時の後始末。Web版(GitHub Pages)でも同じ仕組みが使える
2. **`save()` が `QuotaExceededError` を握りつぶしているのを直す**（`index.html` の `save()`。
   今は `catch(e){}`。上限に当たっても画面上は貼れて見え、**警告も出ないまま次回起動で消える**）
3. 余力があれば: 書き出し／取り込み（バックアップ）

#### 決めていない・人の判断が要ること

- **再配信するか。** 配信するなら iOSのルール上 **1.0.4 / build 8 へ+1して再Archive→ASCへ再アップ**
  が必要（[[feedback-ios-build-bump]]）。1.0.3/build7 は既にアップ済みなので**同じ番号では上げられない**
- **ASCで1.0.3/build7の審査提出まで進んだかは依然として未確認**（前回からの持ち越し）
- Web版（GitHub Pages）は push すれば反映される（バージョン番号は不要）

#### 環境まわりの注意（次回ハマらないように）

- シミュレータでソフトキーボードを出すには **I/O → Keyboard → Connect Hardware Keyboard の✓を外す**。
  `defaults write` は効かない。今はオフにしてある
- シミュレータのタップは `swiftc` で作った CGEvent ツール経由（`osascript` の `click at` は不可）。
  ただし**ネイティブの写真ピッカー（Photo Library / Choose File のメニュー）は合成クリックに反応しない**
- ターミナルに**補助アクセス（アクセシビリティ）を許可済み**。次回もそのまま使える

#### 未確認・仕様上の注意

- **未確認**: 実機（iPhone実物）でのキーボード時の挙動。シミュレータでは直っている
- 仕様上の注意（前回から継続）: 「完了」を押さずにシート外をタップすると**編集は破棄**される


## 2026-08-17

### 完了したこと
- スクラップ編集シートの改良2点（`index.html` のみ・Web/iOS共通）
  - **開いたときにメモの一番上が表示されない**のを修正
  - **「キャンセル」「完了」の画面下固定をやめ、編集内容の一番下（スクロール末尾）へ移動**
- 長いメモで textarea が内部スクロールしていたのをやめ、内容に合わせて伸びるようにした（`autoSize`）
- Safari（幅390×高844＝iPhone相当）で実画面を撮って確認。
  40行のメモで **1行目から表示・40行すべて表示・末尾にボタン**、短いメモでもボタンは末尾。
  保存（`saveMemo`）・ブロック追加の並び順（フッターは常に最後）も確認済み
- `npm run sync` 済み（`www` 再生成＋ios public 反映）。**バージョンは 1.0.2(6) のまま**

### 発生したエラーと解決策
- 症状: スクラップ編集を開くと**メモの先頭が画面外**にある。
  原因は2つ重なっていた。
  1. `makeBlockDOM` の textarea `focus` ハンドラが「textarea の**下端**が見えるように」
     `#memo-editor` をスクロールしていた。`.block-textarea` は `min-height:480px` で
     編集エリア（実測 clientHeight 681px、実機ではさらに低い）より高くなり得るため、
     開くたびに必ず下へずれて先頭が隠れた
  2. 長いメモでは textarea 自身が内部スクロールし、`setSelectionRange(末尾)` で
     さらに下へ送られていた
  → 直し方: ①focusハンドラは **textarea が編集エリアより高いときは下端合わせをしない**
  （上端が隠れているときだけ上へ戻す）②`.block-textarea` を `flex:1 0 auto` + `overflow:hidden`
  にし、`autoSize()` を text ブロックにも掛けて**内容の高さまで伸ばす**（内部スクロール廃止）
  ③`openMemo` で `#memo-editor.scrollTop = 0` を明示。
  カーソルは従来どおり末尾に置く（続きが書ける）。`focus({preventScroll:true})` は
  2026-07-30の盤面上ずれ対策なので**外していない**
- 症状: Safari の `do JavaScript` が無言で失敗（結果が返らない）。
  原因未特定だが、`try{...}catch(e){"ERR:"+e.message}` で包むと原因が見えるので、
  以後の確認はこの形で実行するとよい

### 完了したこと（続き・同日夕方）
- **1.0.3 / build 7 で再配信の準備まで完了**
  - `CURRENT_PROJECT_VERSION` 6→7 / `MARKETING_VERSION` 1.0.2→1.0.3（Debug/Release両方）
  - `npm run sync` → `xcodebuild ... archive` で **ARCHIVE SUCCEEDED**
    （`~/Library/Developer/Xcode/Archives/2026-08-17/scrapmemo-1.0.3-7.xcarchive`。
    bundleId・1.0.3・build7・同梱`public/index.html`に修正が入っていることを検証済み）
  - commit f47056c を push。**Web版（GitHub Pages）も同じ修正が公開済み**（Actions success）
  - ユーザーが Organizer から **App Store Connect へアップロード完了**（本人申告）

### 次回への引き継ぎ事項・未解決の課題
- **App Store の審査提出が完了したかは未確認。** ASCで「新バージョン1.0.3を作成 → ビルド7を選択 →
  『このバージョンの最新情報』を記入 → 審査へ提出」まで進んだかを次回まず確認する。
  審査通過後、`CLAUDE.md` のアプリ一覧（現在「1.0.3 build7 アップロード待ち」）と
  メモリ `project_scrapmemo.md` を「1.0.3 配信済み ✅」へ更新すること
- 次に出すときは build 8 から（[[feedback-ios-build-bump]]）
- **未確認**: iOS 実機／シミュレータでの確認はしていない（今回は Safari で確認）。
  特に**ソフトキーボードが出た状態**での見え方は未確認
- 仕様上の注意: 「完了」を押さずにシート外（オーバーレイ）をタップすると**編集は破棄**される。
  ボタンが画面下固定でなくなった分、押さずに閉じる事故が起きやすくなった可能性がある。
  必要なら「変更があるときは閉じる前に確認」を足す
- 未着手の大きい課題（`TODO.md` 参照）: localStorage 5MB上限リスクとバックアップ機能なし、
  タグ・分類なし、Web版とiOS版でデータが行き来しない
