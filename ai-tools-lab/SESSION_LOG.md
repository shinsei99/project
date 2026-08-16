# SESSION_LOG.md — AIツールラボ 作業ログ

新しい項目は上に追記する（上が新しい）。

---

## 2026-08-16（続き3）— 在庫を揃える方針・集客基盤・Zennのレート制限

### 完了したこと
- **転載の方針を確定**: 本体の**不動産カテゴリの公開記録**と Zenn / note の本数を揃える。
  ツール・ゲーム分類は本体のみ。**制作記録を1本増やしたら Zenn・note も同時に出す**
  （`ai-tools-lab/CLAUDE.md` に常駐。`npm run validate` が転載漏れを ⚠️ で出す）
- **psa-collection を本体からも外した**（`visibility: internal`。削除ではない）。
  他社サイトの内部APIを叩く手順の公開になるため
- **不動産の残り3本ぶんの原稿を Zenn・note とも作成**（計6本）
  - Zenn: `ai-agent-always-on` / `launchd-restart-loop` / `llm-pdf-split-gaps`
  - note: `ai-always-on` / `silent-failure` / `scanned-pile`
- **集客の基盤を入れて本番反映**（ここが全く無かった）
  - 全ページに OGP / Twitterカード、`metadataBase`、canonical
  - `works/[slug]/opengraph-image.tsx` で**記事ごとのOG画像を自動生成**（日本語表示も確認済み）
  - `sitemap.xml` / `robots.txt`（どちらも404だった）
  - URLは `src/lib/site.ts` の1箇所に集約（独自ドメイン移行はここだけ直す）

### 発生したエラーと解決策
- **Zennに3本pushしても反映されない** → 原因は **Zennの投稿レート制限**（記事は
  直近24時間の投稿数で判定。上限ロジックは非開示）。今日すでに2本出していたため弾かれた。
  **デプロイ履歴は「デプロイ成功」と表示され、お知らせ欄にだけ
  「投稿数の上限に達したためデプロイされませんでした」と出る**ので気づきにくい。
  → **原因の切り分けは https://zenn.dev/dashboard/deploys のお知らせ欄が最短**（要ログイン）
- **最初は絵文字（異体字セレクタ付き `🛎️` `✂️`）を疑ったが外れ。** 1コードポイントに
  直して再pushしても反映されなかった。修正自体は無害なので残してある
- Zennは**時間が経っても自動で再試行しない**。上限解除後にもう一度 push が要る
- 「booksディレクトリが見つかりません」の警告も出るが、本を出さないなら無視でよい

### 次回への引き継ぎ事項・未解決の課題
- **⚠️ 明日やること（順番厳守）**
  1. 空コミット push → Zenn 3本（`ai-agent-always-on` / `launchd-restart-loop` /
     `llm-pdf-split-gaps`）が公開されるのを API で確認
     （`curl -s "https://zenn.dev/api/articles?username=shinsei99&order=latest"`）
  2. note 3本を投稿（`python3 drafts/note/md2html.py <名前>` → 本文欄で ⌘V →
     見出し画像は「記事にあう画像を選ぶ」）。**note原稿にはZennのURLが埋めてある**ので
     Zennを先に出すこと
  3. `content/works/*.json` の `links` に両方のURLを追記 → `npx vercel --prod`
  4. `npm run validate` の転載漏れ警告が消えることを確認
- **Google Search Console に未登録**（sitemapができたので登録すると初期のインデックスが早い）。
  登録はブラウザ操作＝本人の作業
- 有料化（noteの有料記事）は**当面やらない**と判断。まず無料で流入を作る。
  やるならプロンプト単体ではなく「運用の型一式」か「1本ぶんの全ログ」で、
  本命は内蔵ツールのSaaS化（Stage 3）

## 2026-08-16（続き2）— Zenn公開2本・本体からの相互リンク

### 完了したこと
- **Zenn の GitHub連携が開通**（`shinsei99/project`）。ご本人がブラウザで App を承認 →
  こちらから空コミットを push（`34971fb`）→ **記事2本が公開**
  - https://zenn.dev/shinsei99/articles/photo-inpainter
  - https://zenn.dev/shinsei99/articles/gemini-api-traps
- **相互リンクの器を実装**: `workSchema` に `links`（`label` / `url` / `note`）を追加し、
  `/works/[slug]` に「この記録から書いた記事」ブロックを表示。
  `photo-inpainter` / `agent-platform` の2件にZennのURLを記入
- `drafts/PUBLISH.md` を更新（Zenn欄にURL記入、投稿手順を**GitHub連携前提**に書き換え）
- **note の原稿2本を投稿できる状態まで仕上げた**（投稿自体はブラウザ操作なので未実施）
  - 懸案だった「品質が低い原因を突き止めてほしい」の鍵カッコを**外して地の文にした**。
    実際の文面が不明なまま引用の体裁で載せられないため。趣旨（改善ではなく原因究明を頼んだ）は保持
  - 末尾の Zenn リンクを実URLへ差し替え。`ai-generated-building.md` には
    制作記録（`/works/agent-platform`）への導線を追加
  - `drafts/note/make_paste.py` を追加 → `drafts/note/paste/*.txt` を生成
- **note に2本公開**（Chrome拡張で投稿まで実施）
  - https://note.com/shinsei99/n/nad3f0dce2889 （半年あきらめていた開発が、2日で終わった話）
  - https://note.com/shinsei99/n/n0388b9c81b5f （AIが、実際には存在しない建物を描いてきた話）
  - 見出し画像は note の**みんなのフォトギャラリー**から設定（クレジットは note が自動表示）
  - `content/works/*.json` の `links` に note のURLを追記

### 発生したエラーと解決策
- **ブラウザ拡張はこのセッションでも未接続**（`Browser extension is not connected`）。
  前回「セッション再起動で使える」と書いたが**再起動しても繋がらなかった**。
  → **GitHub App の承認はご本人にブラウザで実施してもらった**。以後もこの承認系は代行できない
- **Zenn の公開状況はブラウザ無しで確認できる**: `zenn.dev/api/articles?username=<id>&order=latest`
  （公開JSON。0件なら連携が効いていない）。プロフィールHTMLの `__NEXT_DATA__` には
  記事一覧が入っていないので、そちらを見ても分からない
- `gh api /user/installations` は **403**（GitHub App 経由のトークンでないと一覧できない）。
  連携の有無を CLI から確認する用途には使えない
- **note の投稿は「HTMLをクリップボードに載せて貼る」のが最短**（`drafts/note/md2html.py`）。
  noteのエディタは**クリップボードの text/html を読む**ので、h2 / blockquote / ul / a が
  そのまま見出し・引用・箇条書き・リンクになる。**プレーンテキストで貼ると1行ずつ
  画面で見出し指定する羽目になり、実際に途中で断念した**。
  macOSは `pbcopy` がプレーンテキストしか置けないため、AppleScript の
  `set the clipboard to «data HTML…»`（16進）を使う。pyobjc は未導入で使えない
- **noteのMarkdownショートカット（行頭に `# `）は既存の行では効かない**。
  文字としてそのまま入るだけなので、記法での後付けは不可
- **見出し画像は「記事にあう画像を選ぶ」（みんなのフォトギャラリー）が速い**。
  `画像をアップロード` は**hidden な file input がアクセシビリティツリーに出ず**、
  file_upload でも掴めなかった（クリックするとネイティブのファイル選択が開いて操作不能）
- 素材選びの注意: ギャラリーには**実在の特定物件を写した写真**があり、タイトルに物件名が入る。
  「実在しない建物」の記事に使うと誤解を生むので外した（採用したのは
  タイトルに「AI生成画像」と明記されたイラスト）
- **note は Markdown が効かない**ので、Zennと同じ原稿をそのまま貼ると `##` や `**` が
  文字として出る。さらに**貼り付けた改行がそのまま行送りになる**ため、原稿の折り返しのまま
  貼るとスマホで不自然に改行される。→ 記法を落とし段落を1行に繋ぐ `make_paste.py` を用意した
  （見出し・引用は画面側で指定する前提で、対象行の一覧をファイル先頭に付ける）

### 次回への引き継ぎ事項・未解決の課題
- **Vercelはgit連携ではなく `vercel` CLI での手動デプロイ**（`.vercel/project.json` あり・
  CLIは `daikyocorps-3085` でログイン済み）。**pushしても本番は更新されない**。
  相互リンクを本番に出すには `npx vercel --prod` が要る（2026-08-16時点で**未実行**）
- note のアカウント作成・ログイン・メール認証は**ご本人の操作が必要**だった
  （Chrome拡張は接続できたが、認証情報の入力は代行しない領域）
- `drafts/note/photo-inpainter.md` の鍵カッコは外したが、**実際に打った文面を思い出したら
  そちらへ差し替えてよい**（趣旨は変えないこと）
- ツール4件（v0 / bolt / devin / windsurf）の `review` 未記入は**据え置き**（触ってから書く）

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
