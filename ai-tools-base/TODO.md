# TODO — AIツールベース（ai-tools-base）計画

記号: `[ ]`未着手 / `[~]`着手中 / `[x]`完了

---

## ▶ 「続きから」と言われたら、ここから（2026-08-21 22:30 更新）

**9本目「Excelの行の高さを実機で採寸した」が本体だけ公開済み。**

1. **8/21 23:40 以降**に空コミットで再push → `./publish.sh status` で
   `openpyxl-row-height-autofit` が ✅ になるまで確認（24時間の投稿上限で弾かれている）
2. ✅になったら note を手貼り（`./publish.sh note moji-ga-kireteru` → ⌘V → 見出し画像 → 公開）
3. 両方のURLを `content/works/excel-row-height.json` の `links` と `drafts/PUBLISH.md` に追記 →
   **`npx vercel --prod --scope brain-dump`**（`--scope` 無しは `Not authorized` になる）

---

## （古い）2026-08-17 の「続きから」— 済んだので参考用に残す

### やること（この順）

1. ~~ブラウザ接続を確認~~ ✅ 繋がった（前回の症状はセッション再起動で解消）
2. ~~Google Search Console に新URLを登録~~ ✅ **完了（8/17 07:53）**
   所有権は**自動確認**で通り、`sitemap.xml` 送信 →「成功しました」/ **28件検出**。
   旧プロパティ `ai-tools-lab-psi` は**残す**判断（URLが404なので害なし）
3. **🔴 19:56 以降に `git push`（未実施・これだけ残っている）** … 直下 `articles/` の
   Zenn 未公開3本が投稿上限で弾かれるため、それより前に push しない。
   push すると同時に**公開済みZenn2本のリンクが新URLに直る**
4. ~~note 公開済み2本の404リンクを修正~~ ✅ **完了（8/17 08:2x・Chromeで代行）**
   本文2本に加え、**noteプロフィールの自己紹介欄**（全記事下部に出る）も新URL＋新サイト名に
5. 以降は `drafts/PUBLISH.md` の順番表どおり、Zenn→note を1日2本ずつ

**19:56 まで待つ間にできること**: Stage 2 のページ（`/tools` `/articles` `/works` `/history`）。

### ここまでで終わっていること

改名は**コード・文書・Vercel とも完了済み**（`267e7fa` でコミット。**push はまだ**）。
本番 https://ai-tools-base.vercel.app は全ページ200。旧URLは削除済み。
Vercelの余計な `drafts` プロジェクトも削除した。
Search Console は新URLで登録・sitemap送信済み。

---

## 🔄 進行中: 改名（AIツールラボ → AIツールベース）2026-08-17

理由: 旧名「AIツールラボ」は同種メディアに類似名が多く（JAPAN AI ラボ 等）、名前で埋もれる。
外部に出ていたのが4本（Zenn2・note2）だけの**いまが改名の最小コスト**。

- [x] 表示名 → `AIツールベース`
- [x] slug・フォルダ名 → `ai-tools-base`（package.json / works/*.json / .gitignore / ルート文書）
- [x] 本番URL → **`https://ai-tools-base.vercel.app`**（`-psi` 無しの綺麗な方が空いていた）
- [x] 未公開の Zenn 5本 / note 5本の原稿に埋まった旧URLを差し替え
- [x] Vercel プロジェクト rename → `npx vercel --prod` → 全ページ200を確認
- [x] **旧URLは削除した**（`ai-tools-lab-psi` / `ai-tools-lab-brain-dump` の2エイリアス）。
      アクセスがまだ無く、URLが2つ並存するほうがややこしいため。リンクは貼り直す方針
- [~] **公開済み4本のリンクの貼り直し**
      note2本 ✅完了（8/17・プロフィール欄も直した）／
      **🔴 Zenn2本は 19:56 以降の push でまとめて直る**（原稿は新URL済み）
- [x] Google Search Console に新URLを登録（8/17 07:53・自動確認／sitemap 28件送信済み）。
      旧プロパティは**残す**（URLが404なので害なし）

**書き換えなかったもの（意図的）**: `SESSION_LOG.md` の過去ログと
`content/works/ai-tools-base.json` の「名前と立ち位置を先に決めた」。当時の事実なので改竄しない。
改名の経緯は同 json の process step 5 と、SESSION_LOG の新しい節に書いた。

---

## このアプリの狙い

**「Claude Code を主軸に」**を旗印に、チャット型AI → 自律型AIエージェントへの変革期を
開発者・副業ワーカー・IT初心者に向けて翻訳するメディア兼Webアプリ。
比較して終わりではなく、**サイト内で動くツール（将来は有料SaaS）**を同じ土台に載せる。

**第4の軸＝制作記録（works）。** 「Claude Code で個人がここまで作れる」を実例で示す。
他の比較サイトが真似できない差別化であり、記事の説得力の土台になる。

### ⚠️ 出すもの・出さないもの（絶対に外さない）

**出すのは成果物ではなく「作り方」。** ①最初に投げたプロンプト ②できあがった機能
③完成までの過程 ④その後の改善過程（症状→原因→直し方）の4点だけ。
アプリ本体・画面・顧客データは公開しない。**だから社内業務アプリでも記事にできる。**

- `content/works/*.json` に **`visibility` を必須項目**として持たせ、
  **`public` のものしかページに出さない**（`internal` は集計の本数にだけ使う）
- プロンプト本文に会社名・物件名・氏名が混ざりやすい。`public` にする前に必ず伏せる。
  `npm run validate` が敬称・電話番号・郵便番号・メールアドレスを走査して警告する
- スクリーンショットを載せる場合は**実データが写っていないもの**だけ

## 設計の芯（後から変えると高くつく決定）

1. **コンテンツはファイル**（`content/tools/*.json`・`content/articles/*.mdx`）。
   AIと自動化スクリプトが**git diff で読める形で直接書き換えられる**ことを最優先にする。
   管理画面もDBも要らないうちは作らない。
2. **読み出しは `src/lib/content/source.ts` の1箇所に閉じる。** ページは source 経由でしか
   コンテンツを取らない。将来DB（Prisma等）へ移すときは**このファイルだけ差し替える**。
3. **スキーマはzodで1本**（`src/lib/schema.ts`）。ビルド前に `npm run validate` で全件検証し、
   壊れたコンテンツはビルドを通さない（AIが書き換える前提なので、検証が無いと静かに壊れる）。
4. ツールの比較軸は**全ツール共通の型**で持つ。表・カード・詳細ページが同じ型を読む。

## Stage 0: 土台 ✅完了
- [x] Next.js 16.3.1 + React 19 + Tailwind v4 + TypeScript + ESLint（App Router / src / `@/*`）
- [x] TODO.md（このファイル）・README.md・SESSION_LOG.md

## Stage 1: アーキテクチャとトップページ ✅完了（2026-08-16）
- [x] ディレクトリ構造の確定（content / scripts / src/{app,components,lib}）
- [x] `src/lib/schema.ts`（zod）… Tool / Article / Work / Category の型
- [x] `src/lib/content/source.ts`（読み出し境界）＋ `tools.ts` / `articles.ts` / `works.ts` / `photos.ts`
- [x] 初期コンテンツ（ツール9件・記事4本・制作記録11本＝公開9／社内2）
- [x] トップページ: Hero／特徴4枚／比較テーブル（検索・カテゴリ・無料枠・並べ替え）／制作記録／記事カード
- [x] `npm run validate`（slug不一致・visibility欠落・個人情報の混入を検査）
- [x] フリー写真の取り込み（Openverse・CC0/PDMのみ）＋クレジット表示の仕組み
- [x] `run.sh`（port 3004・127.0.0.1）／ルート CLAUDE.md・TODO.md へ登録

## Stage 2: 各ページ（次回以降）
- [ ] `/tools`（全件・絞り込み）・`/tools/[slug]`（詳細・スコア内訳）
- [ ] `/articles`・`/articles/[slug]`（MDX本文レンダリング。今は frontmatter のみ読んでいる）
- [ ] `/history`（AIの歴史変革 特集: 黎明期 vs エージェント時代の年表）
- [ ] `/works`・`/works/[slug]`（実績の一覧と詳細。作った経緯・つまずき・所要時間を書く）

## Stage 3: 内蔵ツール（SaaS化の布石）
- [ ] `/apps/*` の置き場と共通レイアウト（1ツール=1ディレクトリ）
- [ ] 無料/有料の境界をどこに引くか決める（認証・課金は入れる直前まで作らない）

## 決めていない・要確認
- [ ] 公開先（Vercel想定でよいか。既存の brain-dump / pasha-calo と同じ流儀）
- [ ] 独自ドメインを取るか
- [ ] 収益の形（アフィリエイト / 有料ツール / 両方）
