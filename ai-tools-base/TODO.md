# TODO — AIツールベース（ai-tools-base）計画

記号: `[ ]`未着手 / `[~]`着手中 / `[x]`完了

---

## ▶ 「続きから」と言われたら、ここから（2026-08-17 セッション中断）

**中断理由**: Claude in Chrome 拡張がペアリングできず、Search Console の操作を代行できなかった。
拡張自体は正常（有効・権限付与済み・v1.0.85・プロファイルはDefault1つ）だが
`list_connected_browsers` が空を返した。**セッション再起動で繋がる想定**（前回も同じ症状→再起動で解決）。

### やること（この順）

1. **ブラウザ接続を確認** … `list_connected_browsers`。空なら `switch_browser` で
   Chrome側に出る「Connect」を押してもらう
2. **Google Search Console に新URLを登録**（← 中断したのはここ）
   - https://search.google.com/search-console →「プロパティを追加」→「**URL プレフィックス**」
     → `https://ai-tools-base.vercel.app`
   - 所有権の確認は「**HTMLタグ**」。**表示される値が
     `kI8QDUk7Op-BmaU3y6VoUvdt18cVp0IxfDgViBzK7do` と同じなら、押すだけで通る**
     （このタグは新URLで配信済み。`src/app/layout.tsx` の `verification.google`）
   - 違う値が出たら `layout.tsx` を書き換えて `npx vercel --prod` → それから「確認」
   - 通ったら「サイトマップ」で `sitemap.xml` を送信（28件）
   - 旧プロパティ（`ai-tools-lab-psi`）は削除してよい。URLごと消してある
   - ⚠️ **Googleへのログイン・トークン入力は代行しない**（本人操作）
3. **19:56 以降に `git push`** … 直下 `articles/` の Zenn 未公開3本が投稿上限で弾かれるため、
   それより前に push しない。push すると同時に**公開済みZenn2本のリンクが新URLに直る**
4. **note 公開済み2本の404リンクを修正**（ブラウザ・本人）
   - https://note.com/shinsei99/n/nad3f0dce2889
   - https://note.com/shinsei99/n/n0388b9c81b5f
5. 以降は `drafts/PUBLISH.md` の順番表どおり、Zenn→note を1日2本ずつ

### 今日ここまでで終わっていること

改名は**コード・文書・Vercel とも完了済み**（`267e7fa` でコミット。**push はまだ**）。
本番 https://ai-tools-base.vercel.app は全ページ200。旧URLは削除済み。
Vercelの余計な `drafts` プロジェクトも削除した。

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
- [ ] **🔴 公開済み4本のリンクが 404 のまま。貼り直す**
      Zenn2本 = 19:56以降の push で直る（原稿は新URL済み）／**note2本はブラウザ・本人**
- [ ] Google Search Console に新URLを登録（**ブラウザ・本人**）。旧プロパティは消してよい

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
