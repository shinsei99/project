# SESSION_LOG.md — AIツールラボ 作業ログ

新しい項目は上に追記する（上が新しい）。

---

## 2026-08-16（続き）— Vercel公開・Zenn/note展開の準備

### 完了したこと
- **Stage 2 完了**: `/tools` `/tools/[slug]` `/works` `/works/[slug]` `/articles`
  `/articles/[slug]` `/history` を作成。**404が全て解消**
- **Vercel公開**: https://ai-tools-lab-psi.vercel.app （全ページ200確認）
- ヒーローを2カラム化し、右にターミナル画面のビジュアルを配置。
  h1はサイト名（AIツールラボ）、標語はサブタイトルへ降格（階層が逆転していた）
- **プロンプトの掲載方針を確定**: 体裁と語調は整えてよいが、
  **内容と粒度は変えない**（一言の指示を長い依頼に書き直さない）。型のコメントに明記
- Zenn/note用の原稿4本を `drafts/` に作成（photo-inpainter / agent-platform 素材）
- リポジトリ直下に `articles/` を作成（ZennのGitHub連携の参照先）

### 発生したエラーと解決策
- **Zennに記事が出ない（公開0件・404）** → 原因は **Zenn の GitHub App が
  未インストール**（github.com/settings/installations に無い）。
  連携が途中で終わっていた。**Appのインストールはブラウザでの承認が必須で、
  CLIからは実行できない**
- Zennは**pushを合図にデプロイする**ため、連携前のpushは取り込まれない。
  連携後に一度pushし直す必要がある（空コミットでよい）
- `articles/` に frontmatter の無い README を置いていたので退避した

### 次回への引き継ぎ事項・未解決の課題
- **⚠️ Claude in Chrome 拡張を入れたが、このセッションでは認識されない。**
  ブラウザツールは**セッション起動時に読み込まれる**ため、
  **拡張導入後に起動したセッションでないと使えない**。要セッション再起動
- 再起動後にやること:
  1. Zenn の GitHub App をインストール（`shinsei99/project` を許可）
  2. 空コミット＋pushでデプロイを起動 → 記事2本が公開される
  3. note のアカウント作成と投稿（原稿は `drafts/note/` に2本）
  4. 公開後、`drafts/PUBLISH.md` にURLを記入し、本体から相互リンクを張る
- ブラウザ操作を使わない場合は `drafts/zenn/paste/*.txt` を貼れば1本1分で出せる
- Zenn ID は **shinsei99**（アカウント作成済み・記事はまだ0件）

## 2026-08-16 — 新規プロジェクト立ち上げ（アーキテクチャ＋トップページ）

### 完了したこと
- `create-next-app` で雛形生成（Next.js 16.3.1 / React 19.2.8 / Tailwind v4 / TS / ESLint / src / App Router）
- **設計を4点で固定**: ①コンテンツはファイル ②読み出しは `source.ts` の1箇所 ③zodスキーマ1本
  ④制作記録は `visibility` 必須で `public` 以外を返さない
- 型定義 `src/lib/schema.ts`（Tool / Article / Work / Category）と読み出し層3本
- コンテンツ: ツール9件・記事4本・制作記録11本（公開9／社内2）
- トップページ: Hero／特徴4枚／**比較テーブル（検索・カテゴリ・無料枠・並べ替え）**／制作記録／記事カード
- フリー写真の取り込み（`npm run photos`）とクレジット表示の仕組み
- `npm run validate`（コンテンツ検証。slug不一致・visibility欠落・個人情報の混入を検査）
- 本番ビルド成功（約9秒）、開発サーバー `127.0.0.1:3004` で HTTP 200 を確認

### 発生したエラーと解決策
- **CC BY / BY-SA の写真は出典表示が義務** → 表示を消した瞬間に違反になる構造が危ういと判断し、
  Openverse の絞り込みを `license_type=commercial` から **`license=cc0,pdm`** へ変更。
  取り直して全5枚が CC0 / パブリックドメインになった（表示義務なし）
- 検証スクリプトの敬称チェックが「仕**様**」に誤反応 → 一般語（仕様・同様・様々…）を先に除去してから判定。
  誤検知を放置すると本物の警告まで無視されるようになるため潰した

### 次回への引き継ぎ事項・未解決の課題
- **Stage 2 が未着手**: `/tools`・`/tools/[slug]`・`/articles`・`/articles/[slug]`（MDX本文の描画）・
  `/history`・`/works`・`/works/[slug]`。現在リンク先が存在しないのはトップからの導線のみ
- MDXは **frontmatter しか読んでいない**（本文の描画は Stage 2）
- ツール4件（v0 / bolt / devin / windsurf）が `review`（評価の根拠）未記入。**根拠のない点数は載せない**方針なので、
  実際に触ってから書くか、点数を下げるか判断する
- 未決: 公開先（Vercel想定でよいか）／独自ドメイン／収益の形（アフィリエイト・有料ツール・両方）
