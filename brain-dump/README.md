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

## 録音（音声入力）のはまりどころ — iOS Safari

**症状**: iPhone Safari で 1分ほど録音して停止すると「録音が空でした」になり、
文字起こしされない。短い録音では成功する。（2026-08-25 に対処）

**原因は 1 つではなく、iOS 側の 2 つの事情が重なる。**

1. **`ondataavailable` が `onstop` より後に届くことがある。**
   仕様上は `dataavailable` → `stop` の順だが、iOS Safari では逆転する場合がある。
   `rec.start()` を **timeslice なし**で呼ぶと録音データは停止時の 1 回にまとめて渡されるため、
   `onstop` の中で Blob を作ると **0 バイト**になる。録音が長いほど（データが大きいほど）起こりやすい。
2. **画面が消えるとマイクが止まる。** iPhone の自動ロック（設定によっては 1 分）や着信で
   トラックが `ended` になり、録音がそこで切れる。

**対処（`app/page.tsx`）**

- `rec.start(1000)` … **timeslice を指定**して 1 秒ごとに chunk を受け取る。
  途中で中断されても、それまでの分が手元に残る。
- `finishRecording()` で **chunk が届くまで最大 3 秒待ってから** Blob 化する。
  待っている間は `stream` を止めない（`cleanupStream()` を Blob 生成の後ろへ移した）。
- **Screen Wake Lock** を録音中だけ取得し、自動ロックで画面が消えるのを防ぐ（iOS 16.4+）。
- 音声トラックの `onended` で自動停止 → そこまでの録音を文字起こしへ回す。

**測った値**（2026-08-25・サブPC）

- 59秒の音声（AAC 32kbps）= **250KB**、data URL 化して **334KB**。
  送信上限 `MAX_AUDIO_BYTES` 3.5MB・Vercel の本文上限 4.5MB のどちらにも遠く、
  **サイズ超過が原因ではなかった**。
- ローカルの `/api/transcribe` は 59秒の音声を **9秒**で処理（`maxDuration = 60` に十分収まる）。
  → タイムアウトでもなかった。
- Chrome（仮想マイク）で実測: 5秒の録音中に chunk が **4個**到着し、停止後に最後の1個が届く。
  timeslice が効いていることと、停止後に届く分を拾えていることを確認済み。

**注意**: この不具合は **iOS Safari 固有**で、Mac の Chrome では再現しない
（Chrome は `dataavailable` → `stop` の順序を守る）。直したかどうかの最終確認は **iPhone 実機**で行う。
