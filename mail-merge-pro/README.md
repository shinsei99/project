# Mail Merge Pro

macOS ネイティブの一斉メール送信アプリ（SwiftUI + MVVM）。
SMTP 設定不要で、**Apple Mail を AppleScript 経由で制御**して送信します。

## 主な機能
- CSV から宛先読込（`name,email` ＋任意の差し込み列）
- 件名・本文の差し込み（`{name}` など）、リアルタイムプレビュー
- 添付ファイル（複数・ドラッグ＆ドロップ）
- 送信元アカウント選択（Mail 登録アカウントから選択）
- テスト送信が成功するまで本番送信はロック
- 1通ごと1秒／50通ごと60秒（1分）待機のバッチ送信（スパム対策、`async/await`、キャンセル可）
- 送信後、専用フォルダ「Mail Merge Pro 送信済み」へ自動隔離（通常 Sent を汚さない）
- 送信完了画面＋結果 CSV エクスポート
- テンプレートの保存（JSON, Application Support）

## 必要環境
- macOS 14 以降
- Swift ツールチェーン（Xcode もしくは Command Line Tools: `xcode-select --install`）
- Apple Mail にアカウント設定済み

## 開発時の起動
```bash
swift run MailMergePro
```

## デスクトップにアプリ（.app）を作る
```bash
./scripts/make-app.sh
```
- ユニバーサルビルド（Apple Silicon + Intel）し、`~/Desktop/Mail Merge Pro.app` を生成
- アドホック署名するため、**ローカルビルドした Mac では Gatekeeper 警告なし**で起動可能
- アイコンを作り直す場合（PIL 必要）: `python3 scripts/make-icon.py && iconutil -c icns scripts/icon.iconset -o scripts/AppIcon.icns`

## 別の Mac でセットアップ
```bash
git pull
cd mail-merge-pro && ./scripts/make-app.sh
```
ローカルビルドなので隔離属性が付かず、警告なしでデスクトップから起動できます。
初回送信時に「Mail の操作を許可」ダイアログが出るので許可してください。

## 構成（MVVM）
- `Models/` … UI 非依存の純粋データ（Recipient / Template / Attachment / SendStatus / SendResult / MailAccount）
- `ViewModels/` … 状態管理（MailMergeViewModel / SendSettings）
- `Services/` … 永続化・インポート・送信・仕分け・差し込み（protocol で注入、テスト容易）
- `Views/` … NavigationSplitView 3ペイン UI

## 今後の拡張余地
- Excel(.xlsx) 読込（現状 CSV のみ。`RecipientImporter` に追加口あり）
- 設定画面（バッチ数・待機秒の UI 変更）
- HTML メール、予約送信
- App Store 配布（Sandbox 化＋ Apple Events entitlement、または Developer ID 公証）
