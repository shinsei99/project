# フォトリメイク（photo-markup）

写真に**文字・図形・矢印・モザイク**を入れて注釈し、**明るさ・コントラスト・鮮やかさ・シャープ・ノイズ除去**などの軽補正やトリミングもできる iOS ネイティブアプリ。App Store 提出前提（iPhone / iPad ユニバーサル）。表示名は「フォトリメイク」。

- **技術**: SwiftUI（iOS 16+）＋ Core Image（CIFilter）
- **非破壊編集**: 元画像・補正値・注釈レイヤーを別管理し、保存時にフル解像度で合成
- **座標は画像正規化（0..1）**: プレビューと書き出しが必ず一致（WYSIWYG）

## 機能
- 写真を選ぶ / その場で撮影（カメラ）
- **文字**：色 / 書体 / 大きさ / 縁取り（色・太さ・透過度）/ 影 / 縦書き。1本指=移動、右下ハンドル=拡大、右上ハンドル=回転、2本指ピンチ=拡大
- **図形**：**矢印**＋四角 / 角丸 / 丸 / 三角 / ひし形 / 五角形 / 六角形 / 星 / ハート / 吹き出し / 十字 / バツ の全13種（矢印も「図形」パレットの中にある）。**塗りの色と枠線の色を別々に指定でき、それぞれ「なし」にできる**（塗りなし＝枠線だけ／枠線なし＝塗りだけ。両方なしにはならない）。線の太さ・塗りの透け具合も調整可。本体ドラッグ=移動、右下ハンドル=大きさ、右上ハンドル=回転
- **矢印**：色 / 太さ。両端の○をドラッグで向き・長さ、本体ドラッグで移動。**「種類」タブで矢印⇄図形を入れ替えられる**（位置・長さ・向きを引き継ぐ）
- **モザイク**：矩形で車のナンバー・表札等を隠す。粗さ調整、移動・サイズ変更
- **調整**：明るさ・コントラスト・鮮やかさ・飽和・鮮明度・シャープ・ノイズ除去（リセット可）
- **トリミング**：四隅ハンドル / 移動 / 比率プリセット（1:1〜9:16）
- **取り消し（Undo）**：上部バーの↩︎で1手ずつ戻す
- 保存：フル画質のままカメラロールへ
- 上部「写真」（＝写真を選び直す）は、**編集内容があるときだけ確認ダイアログ**を出す（誤タップで消えないように）

## ビルド / 実行

プロジェクトは [XcodeGen](https://github.com/yoneycom/xcodegen) の `project.yml` が正。`.xcodeproj` も同梱しているので **そのまま Xcode で開けます**。

```bash
# 構成（ファイル追加・設定変更）を変えたら再生成
brew install xcodegen      # 未導入なら
cd photo-remake
xcodegen generate

# もしくはコマンドラインでシミュレータ確認
open PhotoRemake.xcodeproj
# Xcode で Signing（自分のTeam）を設定 → 実機/シミュレータで実行
```

- Bundle ID: `com.shinsei.photoremake`（Xcode で自分のものに変更可）
- 署名 Team は Xcode の Signing & Capabilities で設定してください。

## 調べて分かったこと（はまりどころ）

### `.sheet` を複数積むと出ないことがある
`EditorView` に `.sheet(isPresented:)` を2つ並べたところ、**あとから足したほう（図形ピッカー）が
まったく出なかった**（2026-08-25 実測。シミュレータで初期値 true にしても未表示）。
`.sheet(item:)` 1本に `ActiveSheet` 列挙型で出し分ける形へ変えたら出るようになった。
**シートを増やすときは modifier を増やさず、`ActiveSheet` に case を足す。**

### 矢印は「図形」に見た目だけ統合してある（実体は別の注釈のまま）
矢印は**2点（尾・先端）で持つ**ので、中心＋半サイズ＋回転で持つ図形とはデータが違う。
両端の○をドラッグして向きと長さを決める操作が矢印の使いやすさなので、**実体は `Annotation.kind == .arrow`
のまま**にして、入口（`AnnotationTool` ＝ 矢印 + ShapeKind 12種）と「種類」タブだけを共通にした。
種類を入れ替えたときは `EditorState.convertSelected(to:)` が
**中点＝position / 長さ＝shapeHalfW×2 / 角度＝rotation** に読み替える（Undoできる）。
角度と長さは**正規化座標のままでは求まらない**（x と y でスケールが違う）ので、
`originalImage.size` を掛けてピクセルに直してから計算している。

### 図形の色は「塗り＝colorHex / 枠線＝strokeColorHex」で固定
最初は「枠線だけのときは colorHex を枠線色に流用」する作りにしたが、**塗ったあとに塗りだけ消せない**
（色を外す手段が無い）と指摘を受けて作り直した。いまは意味を固定し、`shapeDrawStyle`
（stroke / fill / both）は**どちらの色が使われているか**を表すだけにしてある。パネルの「色」タブで
枠線・塗りを選び、パレット左端の「なし」でその側を消す（消した側を色でタップすると復活）。

### 図形はプレビューと書き出しで同じパスを使う
`ShapeGeometry.path(_:in:)` が唯一の定義で、SwiftUI 側は `AnnotationShape`（`Shape` 準拠）、
書き出し側は `CGContext.addPath` で同じ `CGPath` を描く。線の太さは**画像の短辺に対する割合**
（`shapeLineWidthRatio`）なので、プレビュー(`min(fitted.width, fitted.height)`)と
書き出し(`min(imageSize.width, imageSize.height)`)で同じ見た目になる。

### 動作確認のしかた（シミュレータ・タップ不要）
`osascript` に補助アクセスが無く、シミュレータをクリック操作できない。代わりに DEBUG 用の
環境変数で確認した。

```bash
xcrun simctl boot "iPhone 16"
xcodebuild -project PhotoRemake.xcodeproj -scheme PhotoRemake -sdk iphonesimulator \
  -destination 'platform=iOS Simulator,name=iPhone 16' -configuration Debug build CODE_SIGNING_ALLOWED=NO
xcrun simctl install booted <BUILT_PRODUCTS_DIR>/PhotoRemake.app
SIMCTL_CHILD_PM_SAMPLE=1 SIMCTL_CHILD_PM_EXPORT=1 xcrun simctl launch booted com.shinsei.photoremake
xcrun simctl io booted screenshot .see/shot.png                     # 画面
cp "$(xcrun simctl get_app_container booted com.shinsei.photoremake data)/Documents/export.png" .see/   # 書き出し結果
```

- `PM_SAMPLE=1` … サンプル画像＋注釈（文字・矢印・モザイク・図形3つ）でエディタを開く
- `PM_EXPORT=1` … 起動直後に `renderFinalImage()` を Documents/export.png へ保存。
  **プレビューと書き出しがズレていないかはこれで見る**（画面だけ見ても書き出しは分からない）

## App Store 提出メモ
- Info.plist は `GENERATE_INFOPLIST_FILE` 方式。カメラ／写真追加の利用目的文言は `project.yml` の `INFOPLIST_KEY_*` に記載済み。
- プライバシーマニフェスト `Resources/PrivacyInfo.xcprivacy` 同梱（データ収集・トラッキングなし）。
- アプリアイコンは `scripts/gen-icon.swift` で 1024px を生成（`Resources/Assets.xcassets/AppIcon.appiconset/icon-1024.png`）。差し替え可。
- 対応端末：iPhone / iPad（`TARGETED_DEVICE_FAMILY = 1,2`）。

## 構成
```
Sources/
  PhotoRemakeApp.swift        エントリ
  Models/     Adjustments / Annotation / EditorState(Undo含む)
  Services/   ImageProcessor(Core Image/pixellate) / ImageExporter(合成) / PhotoSaver
  Views/      RootView / EditorView / AnnotatedImageView
              TextLayer / ArrowLayer / MosaicLayer / CropView / AdjustPanel / 各StylePanel / Handles
  Support/    ColorHex / ImageUtils / ArrowGeometry / TextRendering / DebugSample(DEBUG)
Resources/    Assets.xcassets / PrivacyInfo.xcprivacy
scripts/gen-icon.swift        アイコン生成
```

## 開発メモ
- DEBUG時 `PM_SAMPLE=1` の環境変数で、サンプル画像＋注釈（文字/矢印/モザイク/図形）でエディタを直接起動（動作確認用・リリース非搭載）。`PM_EXPORT=1` を足すと書き出し結果も保存する。シミュレータへは `SIMCTL_CHILD_PM_SAMPLE=1 xcrun simctl launch ...` で渡す。
- 実装上の要点：テキストは `StrokeTextLabel`(UILabel) を使うため `.contentShape(Rectangle())` が無いとタップ選択できない。`binding(for:)` はインデックス固定禁止（id で都度検索、削除時の範囲外クラッシュ回避）。各注釈は自分の bbox に収める（TextLayer/ArrowLayer/MosaicLayer/ShapeLayer）ことで選択の干渉を防ぐ。図形の当たり判定は `.contentShape(AnnotationShape(kind:))` ＝図形そのもの。
- 未実装（次の拡張候補）：やり直し(Redo)、番号バッジ、傾き・台形補正、共有ボタン、図形の「線を破線に」。
