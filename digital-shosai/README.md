# デジタル書斎 — 自分専用ナレッジベース（完全オンデバイス版）

OCR済みPDFを取り込み、ページごとに **テキスト抽出＋画像化** して **端末内（IndexedDB）** に保存。
高速な部分一致検索で、ヒットページの **テキスト** と **元PDF画像** を左右に並べて閲覧できるパーソナル書斎アプリ。

> 🔒 **データはダウンロードした本人の端末内にのみ保存され、外部サーバーには一切送信されません。**
> クラウド不要・サーバー不要・ログイン不要で動作します。

将来は **Capacitor** で iOS アプリ化して App Store 配布する想定（静的書き出し `out/` をそのまま利用）。
収益化用に3種の広告枠（バナー／インタースティシャル／動画リワード）と冊数制限ロジックを実装済み。

## 技術スタック

- Next.js (App Router, `output: "export"` 静的書き出し) + Tailwind CSS + lucide-react
- **PDF処理: pdf.js (pdfjs-dist)** — ブラウザ内でテキスト抽出＆ページ画像化（サーバー処理なし）
- **保存: IndexedDB (`idb`)** — 本・ページ・画像Blobをすべて端末内に格納

## セットアップ・起動

```bash
cd digital-shosai
npm install
npm run dev -- --hostname 127.0.0.1 --port 3001   # ★ hostname を明示する
```

環境変数もSupabaseもデータベースサーバーも不要です（`.env` は要りません）。

> ⚠️ **`--hostname 127.0.0.1` を必ず付ける。** Next.js の dev サーバーは既定で `0.0.0.0` に
> バインドし、**社内LANから見える状態になる**（2026-08-17に実測して確認）。このアプリはツール分類＝
> 社内共有しない決まりなので、常に自分の端末だけに出す。
（`predev`/`prebuild` で pdf.js のワーカーを `public/` に自動コピーします）

## 画面 / 機能

| 画面 | パス | 内容 |
|------|------|------|
| 取り込み | `/` | D&D取込 → pdf.jsでページ毎にテキスト＋画像化 → IndexedDB保存。蔵書と端末容量のメーター、進捗バー、文字層が無いPDFの確認パネル |
| 検索 | `/search` | `pageText` を**複数語のAND**で部分一致検索。本で絞り込み、ヒット件数と所要ms、ハイライト付きプレビュー、左右2カラム詳細ビューア |
| 蔵書 | `/library` | 取り込んだ本の一覧（ページ数・容量・形式・取込日時）と削除（画面内で確認） |

**冊数の制限は無い。** 広告（バナー／インタースティシャル／動画リワード）と本棚スロット制限は
2026-08-17 に全削除した（自分専用の道具で冊数を人為的に絞る意味がないため）。

## データ構造（IndexedDB: `digital-shosai`）

**v2（2026-08-17）**

- `books` … 本のメタ（id, title, uploadedAt, pageCount, **imageBytes**, **imageMime**）
- `pages` … **画像専用**（id, bookId, pageNumber, image=WebP/PNG Blob）／`byBook` インデックス
- `pageText` … **検索専用の軽いレコード**（id, bookId, pageNumber, text, lower）／`byBook` インデックス

**なぜ分けたか（再実装しないこと）**: v1 は `pages` にテキストと画像Blobが同居していて、
検索のたびに**画像を抱えたレコードを全件カーソル走査**していた。蔵書が増えるほど重くなる。
v2 は検索を `pageText` だけで済ませ、画像は詳細を開いたときに1件だけ読む。
v1 のデータは初回起動時の `upgrade` で自動移行する（テキストを写し、本ごとの容量を集計）。
※ v1 で書かれた `pages.content` は残るが、新規保存では書かない（本文を二重に持たない）。

## ページ画像の形式（WebP優先・2026-08-17）

`canvas.toBlob` を **ロスレスWebP → 品質90のWebP → PNG** の順に試し、**返ってきた Blob の
`type` を確認**して実際に使える形式を1枚目で確定する（要求した形式が無視されて別形式で返ることが
あるため。Safari の WebP 書き出し対応は端末次第）。取り込み後に「画像は WEBP」と画面に出る。

同じPDFの同じページを同倍率（1190×1684）で書き出した実測:

| 形式 | サイズ | PNG比 |
|---|---|---|
| PNG（v1の固定形式） | 41.4 KB | 100% |
| **WebP ロスレス（現在）** | **11.8 KB** | **28.5%** |
| WebP 品質90 | 18.5 KB | 44.7% |

容量が下がったので `RENDER_SCALE` を **1.5 → 2.0** に上げた（1.5は約108dpi相当で小さい字が読みづらかった）。
写真スキャンのような階調の多い画像では、ここまでの圧縮率にはならない。

## App Store（Capacitor）化の流れ（将来）

```bash
npm run build                       # out/ に静的書き出し
npm i -D @capacitor/cli @capacitor/core @capacitor/ios
npx cap init digital-shosai com.example.shosai --web-dir=out
npx cap add ios
npx cap copy && npx cap open ios    # Xcode でビルド・申請
```

IndexedDB は iOS WebView 内に永続化されるため、各ユーザーのデータはその端末内に保持されます。

## 補足・本番化メモ

- 蔵書一覧・削除は `/library` に実装済み（2026-08-17）。**削除してもブラウザの報告する使用量は
  すぐには縮まないことがある**（IndexedDBが領域を再利用するため。実測で 64.9KB → 70.9KB のまま）。
- **バックアップ手段がまだ無い。** 端末内だけに保存する設計なので、**端末が壊れると全部消える**。
  外部送信しない方針を守ったまま、ファイルへ書き出す仕組みが次の課題（`TODO.md`）。
- 画像解像度は `src/lib/constants.ts` の `RENDER_SCALE`（既定1.5）で調整可能。大きいほど高精細だが端末の保存サイズが増える。
- スキャンしただけ（OCR未処理）のPDFはテキストが空になり検索に乗りません。**OCR済み（テキスト層あり）PDF前提**です。
  - 取り込み時に文字データがほぼ無いPDFを検知すると警告し、「画像として保存だけするか」を確認します（無言で空保存しない）。
  - 未OCRのPDFは Acrobat / ScanSnap / Googleドライブ等で先にOCRしてから取り込んでください。

## 日本語PDFのテキスト抽出について

pdf.js で日本語（CIDフォント）のテキストを正しく抽出するには **cMap** と **標準フォント** データが必要です。
本プロジェクトは `scripts/copy-pdf-worker.js` でこれらを `public/cmaps` `public/standard_fonts` に同梱し、
`processPdf()` 内で `cMapUrl` / `cMapPacked` / `standardFontDataUrl` を指定しています（オフライン動作）。
これが無いと日本語が文字化け・欠落します。
