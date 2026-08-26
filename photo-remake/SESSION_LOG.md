# フォトリメイク（photo-remake）作業ログ

新しい日付の節を**先頭に追記**する（上書きしない）。見出しには必ず作業したPCを書く。

## 2026-08-26（メインPC）

### 完了したこと
- サブPCの 1.1.0 / build 4 を受領し、**Archive まで完了**。
  `~/Library/Developer/Xcode/Archives/2026-08-26/PhotoRemake 26-08-26, 13.30.xcarchive`
  （1.1.0 / build 4・`com.shinsei.photoremake`・Team `773DPMVW7Q`・iOS 16.0+・8.7MB）。
- 事前確認: `./ios-build-guard.sh photo-remake` → **衝突なし（build 4 > 既存最大 3）**、
  `appstore_api.py --review com.shinsei.photoremake` → **配信中 1.0.2 / 審査中なし**。
  `project.pbxproj` の **Debug / Release 両方**が 1.1.0 / build 4 であることも確認。
- `RELEASE.md` の著作権者名を **`SHINSEI PROPERTY MANAGEMENT.K.K.`** に訂正
  （「新誠プロパティマネジメント」は誤り。2026-08-19確定の表記 [[reference_developer_entity]]）。

### 発生したエラーと解決策
- **症状**: Archive するのに配布証明書が見つからない。`security find-identity -v -p codesigning` は
  **`Apple Development` の1本だけ**で、`Apple Distribution` / `iPhone Distribution` は
  キーチェーンに**0件**（`security find-certificate -a -c "Apple Distribution"` で確認）。
  **原因**: このMacの配布証明書は**クラウド署名（cloud-managed distribution certificate）**で、
  秘密鍵が Apple 側にあり**ローカルのキーチェーンには存在しない**。
  プロファイル `iOS Team Store Provisioning Profile: com.shinsei.photoremake`
  （Team `773DPMVW7Q`・2027-06-23まで有効）が参照している証明書は
  `Apple Distribution: shinichi washimi (773DPMVW7Q)` だが、**手元には無くて正常**。
  **直し方**: Archive は開発証明書で署名されるままでよい（**配布時に署名し直される**）。
  CLI から通すなら ASC の API キーで認証しながら叩く:
  ```bash
  set -a; . ~/.env.appstore; set +a
  xcodebuild archive -project PhotoRemake.xcodeproj -scheme PhotoRemake -configuration Release \
    -destination 'generic/platform=iOS' -archivePath "<パス>.xcarchive" -allowProvisioningUpdates \
    -authenticationKeyPath "${ASC_PRIVATE_KEY_PATH/#\~/$HOME}" \
    -authenticationKeyID "$ASC_KEY_ID" -authenticationKeyIssuerID "$ASC_ISSUER_ID" \
    DEVELOPMENT_TEAM=773DPMVW7Q CODE_SIGN_STYLE=Automatic
  ```
  **`-archivePath` は `~/Library/Developer/Xcode/Archives/<YYYY-MM-DD>/` の下に置く**こと。
  ここに置かないと Xcode の Organizer に出てこない＝ GUI から配布できない。
  なお `DEVELOPMENT_TEAM` を渡さないと個人チーム（`FWYY2U2N6P`）で署名されるので必ず指定する。

### 次回への引き継ぎ事項・未解決の課題
- **アップロード（Distribute App）と審査提出は未実施**。外部に出る操作なのでオーナーの判断待ち。
- **実機での動作確認も未実施**（`RELEASE.md` の「2. 実機で触る」）。今回の変更は
  図形の追加・移動・回転・色の付け外しと**全部が指の操作**なので、提出前に一度は触ること。

## 2026-08-25（サブPC）

### 完了したこと
- **「写真」ボタンの誤タップ対策**。上部左の「写真」（＝写真を選び直す）を押すと編集中の内容が
  すべて消えていたので、**編集内容があるときだけ確認ダイアログ**を出すようにした
  （`EditorState.hasEdits` ＝ 注釈がある / 補正が既定でない / Undo可 のいずれか）。
  何も編集していなければ従来どおり即座に選び直せる。
- **図形注釈を新設（12種）**：四角 / 角丸 / 丸 / 三角 / ひし形 / 五角形 / 六角形 / 星 / ハート /
  吹き出し / 十字 / バツ。下部パレット「図形」→ シートで種類を選んで追加。
  本体ドラッグ＝移動、右下ハンドル＝大きさ、右上ハンドル＝回転。
  - 新規: `Sources/Support/ShapeGeometry.swift`（種類とパス）/ `Sources/Views/ShapeLayer.swift`
    （キャンバス）/ `Sources/Views/ShapeStylePanel.swift`（パネルと選択シート）
  - `ImageExporter` に書き出しを追加。**プレビューと書き出しは同じ `ShapeGeometry.path` を使う**
  - 切り抜き時に図形の半サイズ・線の太さも座標変換する（`applyCrop`）
- **色は「塗り＝colorHex / 枠線＝strokeColorHex」に固定**し、パネルの「色」タブで
  枠線・塗りを選んでパレット左端の「なし」でその側を消せるようにした
  （**オーナー指摘：色を付けたあと色なしに戻せない**への対応。最初の実装は
  「枠線だけのときは colorHex を枠線色に流用」する作りで、塗りだけ消す手段が無かった）。
  両方なしにはならない（片方を消すともう片方が必ず残る）。
- 版を **1.1.0 / build 4** へ繰り上げ（1.0.2/build3 が配信中）。`./ios-build-guard.sh photo-remake`
  で「衝突なし」を確認済み。**提出はしていない**（人の判断）。

- **矢印を「図形」に統合**（オーナー要望）。図形パレット／ピッカー／「種類」タブの一覧を
  `AnnotationTool`（矢印 + ShapeKind 12種）に統一し、**下部パレットの「矢印」ボタンは廃止**
  （上部「追加」メニューには残してある）。**種類タブで矢印⇄図形を入れ替えられる**
  （`EditorState.convertSelected(to:)`。中点・長さ・向きを引き継ぎ、Undo可）。
  実体は矢印のまま（両端ドラッグの操作を残すため）。

### 発生したエラーと解決策
- **症状**: 新しく足した図形ピッカーのシートがまったく出ない（初期値 true でも未表示）。
  **原因**: `EditorView` に `.sheet(isPresented:)` を2つ積んでいた（ヘルプと図形ピッカー）。
  同一ビューに複数のシート modifier を重ねると後から足したほうが無視されることがある。
  **直し方**: `ActiveSheet` 列挙型を作り `.sheet(item:)` **1本**で出し分ける形にした。
  → シートを増やすときは modifier を足さず `ActiveSheet` に case を足すこと。
- **症状**: シミュレータをクリックして確認できない（`osascript` に補助アクセスが無く -1719）。
  **直し方**: 確認したい画面を DEBUG の初期値で開く／`PM_SAMPLE=1`・`PM_EXPORT=1` の環境変数で
  サンプル起動＋書き出し保存 → `simctl io screenshot` と `get_app_container` で回収した。
  手順は `README.md`「動作確認のしかた」に残した。

- **注意**: 矢印⇄図形の角度・長さは**正規化座標のままでは計算できない**（x と y でスケールが違う）。
  `originalImage.size` を掛けてピクセルに直してから atan2 / hypot する。シミュレータで
  変換後の値（p 0.41,0.51＝元の矢印の中点・向きも一致）を画面に出して確認した。

### 次回への引き継ぎ事項・未解決の課題
- **★メインPCへ引き継いだ（App Store 提出のため）。** 手順は **`photo-remake/RELEASE.md`**
  にまとめてある（実機チェックリスト・Archive・提出・新機能の文案）。直下の `HANDOFF.md` 先頭と
  `TODO.md`（担当PC＝メイン）にも同じことを書いた。**提出は未実施。**
  - 配信中 1.0.2 / build 3・**審査中のものは無い**（2026-08-25 に `appstore_api.py --review` で確認）
  - **`xcodegen generate` は実行しないこと**（`.xcodeproj` はコミット済み。走らせると Signing の
    Team 選択が消える）
- 図形の線を破線にする選択肢、番号バッジ（①②③）、Redo は未実装（`TODO.md`）。
- 確認ダイアログ・図形ピッカー・色タブは**シミュレータの画面で目視済み**
  （`.see/` に撮ってあるが gitignore。コミットしていない）。実機では未確認。
