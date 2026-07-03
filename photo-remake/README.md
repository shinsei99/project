# フォトリメイク（photo-markup）

写真に**文字・矢印・モザイク**を入れて注釈し、**明るさ・コントラスト・鮮やかさ・シャープ・ノイズ除去**などの軽補正やトリミングもできる iOS ネイティブアプリ。App Store 提出前提（iPhone / iPad ユニバーサル）。表示名は「フォトリメイク」。

- **技術**: SwiftUI（iOS 16+）＋ Core Image（CIFilter）
- **非破壊編集**: 元画像・補正値・注釈レイヤーを別管理し、保存時にフル解像度で合成
- **座標は画像正規化（0..1）**: プレビューと書き出しが必ず一致（WYSIWYG）

## 機能
- 写真を選ぶ / その場で撮影（カメラ）
- **文字**：色 / 書体 / 大きさ / 縁取り（色・太さ・透過度）/ 影 / 縦書き。1本指=移動、右下ハンドル=拡大、右上ハンドル=回転、2本指ピンチ=拡大
- **矢印**：色 / 太さ。両端の○をドラッグで向き・長さ、本体ドラッグで移動
- **モザイク**：矩形で車のナンバー・表札等を隠す。粗さ調整、移動・サイズ変更
- **調整**：明るさ・コントラスト・鮮やかさ・飽和・鮮明度・シャープ・ノイズ除去（リセット可）
- **トリミング**：四隅ハンドル / 移動 / 比率プリセット（1:1〜9:16）
- **取り消し（Undo）**：上部バーの↩︎で1手ずつ戻す
- 保存：フル画質のままカメラロールへ

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
- DEBUG時 `PM_SAMPLE=1` の環境変数で、サンプル画像＋注釈（文字/矢印/モザイク）でエディタを直接起動（動作確認用・リリース非搭載）。シミュレータへは `SIMCTL_CHILD_PM_SAMPLE=1 xcrun simctl launch ...` で渡す。
- 実装上の要点：テキストは `StrokeTextLabel`(UILabel) を使うため `.contentShape(Rectangle())` が無いとタップ選択できない。`binding(for:)` はインデックス固定禁止（id で都度検索、削除時の範囲外クラッシュ回避）。各注釈は自分の bbox に収める（TextLayer/ArrowLayer/MosaicLayer）ことで選択の干渉を防ぐ。
- 未実装（次の拡張候補）：やり直し(Redo)、図形（丸・四角）＋番号バッジ、傾き・台形補正、共有ボタン。
