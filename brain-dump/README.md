# 🧠 Brain Dump

頭の中を殴り書きすると、AI（Gemini）が **タスク / アイデア / 感情ログ** に自動分類してくれる、スマホ向けの自分専用アプリ。
本や記事を **カメラ撮影 → 自動要約・スクラップ** する機能つき。

## 技術スタック

- Next.js 16（App Router, TypeScript）+ Tailwind CSS v4
- `@google/generative-ai`（Gemini 2.5 Flash／環境変数で変更可）
- スマホ最適化・ダークモード・PWA対応（ホーム画面に追加可能）

## セットアップ

```bash
cp .env.example .env.local   # 値を自分用に編集
npm install
npm run dev                  # http://localhost:3000
```

`.env.local` に設定する値:

| 変数 | 説明 |
|---|---|
| `GEMINI_API_KEY` | Gemini APIキー（必須・コミット禁止） |
| `GEMINI_MODEL` | 使用モデル（既定 `gemini-2.5-flash`） |
| `ACCESS_CODE` | 起動時に入力する合言葉。これと一致しないとAPIを叩けない |

## 仕組み

- **認証**: 画面でアクセスコードを入力 → `localStorage` に保存し、各APIリクエストの
  `x-access-code` ヘッダで送信。サーバー側で `ACCESS_CODE` と照合し、不一致なら 401。
- **テキスト解析**: `POST /api/analyze` … 殴り書きを構造化JSONで分類。
- **画像解析**: `POST /api/analyze-image` … 画像（縮小済みdata URL）をOCR＋要約。
  スマホでは `capture="environment"` でカメラが1タップ起動。

## 機能拡張のヒント

- 結果を `localStorage` やDBに保存して履歴化
- PWAアイコン（`public/icon.svg`）をPNG各サイズに差し替え
- モデルを `gemini-3-flash-preview` 等に変更（`GEMINI_MODEL`）
