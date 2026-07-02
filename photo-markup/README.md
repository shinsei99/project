# 写真マークアップ（photo-markup）

写真に**文字・矢印**を入れて注釈し、**明るさ・コントラスト・鮮やかさ・シャープ・ノイズ除去**などの軽補正もできる iOS ネイティブアプリ。App Store 提出前提（iPhone / iPad ユニバーサル）。

- **技術**: SwiftUI（iOS 16+）＋ Core Image（CIFilter）
- **非破壊編集**: 元画像・補正値・注釈レイヤーを別管理し、保存時にフル解像度で合成
- **座標は画像正規化（0..1）**: プレビューと書き出しが必ず一致（WYSIWYG）

## 機能
- 写真を選ぶ / その場で撮影（カメラ）
- 文字注釈：色 / 書体 / 大きさ / 縁取り（色・太さ・透過度）/ 影
- 矢印注釈：色 / 長さ / 太さ
- 移動＝ドラッグ、拡大・回転＝2本指ピンチ／回転
- 調整：明るさ・コントラスト・鮮やかさ・飽和・鮮明度・シャープ・ノイズ除去（リセット可）
- 保存：フル画質のままカメラロールへ

## ビルド / 実行

プロジェクトは [XcodeGen](https://github.com/yoneycom/xcodegen) の `project.yml` が正。`.xcodeproj` も同梱しているので **そのまま Xcode で開けます**。

```bash
# 構成（ファイル追加・設定変更）を変えたら再生成
brew install xcodegen      # 未導入なら
cd photo-markup
xcodegen generate

# もしくはコマンドラインでシミュレータ確認
open PhotoMarkup.xcodeproj
# Xcode で Signing（自分のTeam）を設定 → 実機/シミュレータで実行
```

- Bundle ID: `com.shinsei.photomarkup`（Xcode で自分のものに変更可）
- 署名 Team は Xcode の Signing & Capabilities で設定してください。

## App Store 提出メモ
- Info.plist は `GENERATE_INFOPLIST_FILE` 方式。カメラ／写真追加の利用目的文言は `project.yml` の `INFOPLIST_KEY_*` に記載済み。
- プライバシーマニフェスト `Resources/PrivacyInfo.xcprivacy` 同梱（データ収集・トラッキングなし）。
- アプリアイコンは `scripts/gen-icon.swift` で 1024px を生成（`Resources/Assets.xcassets/AppIcon.appiconset/icon-1024.png`）。差し替え可。
- 対応端末：iPhone / iPad（`TARGETED_DEVICE_FAMILY = 1,2`）。

## 構成
```
Sources/
  PhotoMarkupApp.swift        エントリ
  Models/     Adjustments / Annotation / EditorState
  Services/   ImageProcessor(Core Image) / ImageExporter(合成) / PhotoSaver
  Views/      RootView / EditorView / AnnotatedImageView / 各パネル
  Support/    ColorHex / ImageUtils / ArrowGeometry / DebugSample(DEBUG)
Resources/    Assets.xcassets / PrivacyInfo.xcprivacy
scripts/gen-icon.swift        アイコン生成
```

## 開発メモ
- DEBUG時 `PM_SAMPLE=1` の環境変数で、サンプル画像＋注釈でエディタを直接起動（動作確認用。リリースには含まれない）。
- 未実装（次の拡張候補）：**トリミング（切り抜き・アスペクト比・回転補正）**、取り消し/やり直し、テキストの複数行整列。
