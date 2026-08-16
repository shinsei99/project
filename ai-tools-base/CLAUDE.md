# ai-tools-base（AIツールベース）— このアプリの決まり

## ★ 制作記録を1本増やしたら、Zenn と note にも同時に出す（2026-08-16決定）

**対象は `category: "realestate"` の公開記録だけ。** ツール・ゲーム分類は本体のみ。

本体だけ増やしても流入は増えない。**本体・Zenn・note の3点セットで1本**と数える。

手順（1本ぶん）:

1. `content/works/<slug>.json` を作る（`visibility` 必須）
2. `drafts/zenn/<zenn-slug>.md` … 症状 → 原因 → 直し方。**ファイル名がZennのURL**（12〜50字）
3. `drafts/note/<名前>.md` … 技術用語なしの物語版。末尾に本体とZennへの導線
   （ZennのURLは `https://zenn.dev/shinsei99/articles/<zenn-slug>` で公開前から確定できる）
4. **Zenn → note の順で公開**（noteからリンクを張るため）
   - Zenn: `drafts/zenn/*.md` をリポジトリ直下の `articles/` へコピーして push
   - note: `python3 drafts/note/md2html.py <名前>` → 本文欄で ⌘V → 見出し画像 → 投稿
5. `content/works/<slug>.json` の `links` に両方のURLを追記 → **`npx vercel --prod`**

**`npm run validate` が転載漏れを警告する。** 不動産カテゴリの公開記録に
`links` の Zenn / note が揃っていないと ⚠️ が出るので、それを消すまでが1本。

**全文コピーはしない。** 3媒体の書き分けは `drafts/README.md` にある。

## 忘れやすい点

- **Vercel は git 連携ではない。** push しても本番は変わらない。`npx vercel --prod` が要る
- **Zenn には「直近24時間の投稿数」でレート制限がある**（上限のロジックは非開示）。
  上限に達すると、その記事だけ**黙ってデプロイされない**（デプロイ自体は「成功」と表示され、
  お知らせ欄に「投稿数の上限に達したためデプロイされませんでした」と出る）。
  **時間が経っても自動では再試行されない。** 24時間空けて**もう一度 push**（空コミットで可）。
  → **1日に出すのは2本まで**にしておくのが安全。原因の切り分けは
  https://zenn.dev/dashboard/deploys のお知らせ欄を見るのが最短（要ログイン）
- Zenn の絵文字は**1コードポイント**のものを使う（`🛎️` のような異体字セレクタ付きは避ける）。
  ※これ自体がデプロイを止めた証拠は無い。上の上限が原因だった
- Zenn のデプロイは push が合図。**push しない限り反映されない**
- プロンプトは**体裁と語調だけ整えてよい。内容と粒度は変えない**（`src/lib/schema.ts` 参照）

@AGENTS.md
