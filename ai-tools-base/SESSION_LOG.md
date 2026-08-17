# SESSION_LOG.md — AIツールベース 作業ログ

> **2026-08-17 に「AIツールラボ」から改名した。** これより下の過去ログには旧名
> `AIツールラボ` / `ai-tools-lab` / `ai-tools-lab-psi.vercel.app` がそのまま残っている。
> **当時の事実なので書き換えていない。** 読み替えること。

新しい項目は上に追記する（上が新しい）。

---

## 2026-08-17 — 「AIツールラボ」→「AIツールベース」に改名（メインPCで追従）

### 完了したこと
- 公開中のサイトは **https://ai-tools-base.vercel.app/**、名称は **AIツールベース** であることを実物で確認
  （h1「AIツールベース」／標語は「Claude Code を主軸に」のまま／制作記録10本）
- **リポジトリ側が旧名・旧URLのままだった**ので統一した（37ファイル）。
  `src/lib/site.ts` の `name`/`url`、layout・Hero の表示、`drafts/` の原稿と貼り付け用txt、
  リポジトリ直下 `articles/` のZenn記事5本、README/CLAUDE/HANDOFF/TODO
- `npm run validate` と `npm run build` が通ることを確認

### 発生したエラーと解決策
- **症状**: 公開済みのZenn記事5本・note2本のリンク先が404。
  **原因**: 旧URL `ai-tools-lab-psi.vercel.app` を意図的に削除したため（ややこしいので、という判断）。
  記事側のリンクは旧URLのまま残っていた。
  **直し方**: パス構成は新旧で同じなのでドメインだけ差し替え。`articles/` を push すれば
  Zennの5本は自動で直る。**noteは手作業**（Markdownが効かないため貼り直しが要る）。

### 次回への引き継ぎ事項・未解決の課題
- **note の公開済み2本（photo-inpainter / agent-platform）のリンクは手で直す**。
  `drafts/note/paste/*.txt` は更新済みなので、該当箇所だけ貼り替えればよい
- ~~フォルダ名は `ai-tools-lab` のまま~~ → **2026-08-17 夜に `ai-tools-base` へ統一**
  （サブPCが同じ日にフォルダごと改名しており、gitのマージでサブPC側を採用した）

> ↑この節はメインPCでの並行作業（同日）。サブPC側の節（下の「続き」）と内容が重なる。

---

## 2026-08-17（続き2）— note 公開済み2本の404リンクを修正

### 完了したこと
- **note 2本の本文リンクを新URLへ**（Chrome で代行・どちらも「更新する」まで完了）
  - `nad3f0dce2889`（半年あきらめていた開発が、2日で終わった話）
    … `AIツールラボ` → `AIツールベース` ＋ URL
  - `n0388b9c81b5f`（AIが、実際には存在しない建物を描いてきた話）
    … 同上 ＋ 制作記録リンク `/works/agent-platform`
- **3か所目が見つかった: note プロフィールの自己紹介欄**。旧URLが入っており
  **全記事の下部と クリエイターページに出ていた**。ご本人の判断で新サイト名ごと書き換え:
  「…制作記録「AIツールベース」: https://ai-tools-base.vercel.app」（107字／上限140字）
- リンク先の到達確認: 本体 200 ／ `/works/agent-platform` 200 ／ 旧URL 404（想定どおり）

### 分かったこと（再調査不要・note のエディタ）
- **リンクの文字を打ち替えると、追加した文字はリンクの外に出る。**
  「ラボ」→「ベース」と打つと下線が `AIツール` までしか掛からない。
  → **文字を直してから、リンク文字全体を選び直してリンクを貼り直す**のが正しい順序
- 選択は `shift+End` を使わないこと。**行末ではなく後続の段落まで飲み込む**
  （45文字選択された）。**`shift+Right` を文字数ぶん繰り返す**のが確実
- リンクを選ぶと出る 🔗 ボタンで **URL 欄に既存値が入った状態のポップアップ**が出る。
  `cmd+a` → 新URL → 「適用」
- 選択位置が画面の上端／下端に近いと**ツールバーが別の行に重なって誤クリックする**。
  対象の行を画面の中ほどに置いてから選択する
- 「更新する」の後に**シェア用ダイアログが自動で出る**。× で閉じるだけでよい（共有はしない）

### 次回への引き継ぎ事項・未解決の課題
- **残るは `git push` のみ（19:56 以降）**。これで Zenn 2本のリンクも直る

---

## 2026-08-17（続き）— Google Search Console を新URLへ移行

### 完了したこと
- **新プロパティ `https://ai-tools-base.vercel.app` を登録**（URL プレフィックス型）。
  **所有権は「自動確認」で通った**（確認方法: HTML タグ）。
  `src/app/layout.tsx` の `verification.google` が既に新URLで配信されていたため、
  トークンの貼り直しは不要だった
- **sitemap.xml を送信 → ステータス「成功しました」/ 検出ページ数 28**
  （8/16 の旧プロパティは26。ページが2つ増えている）
- **旧プロパティ `ai-tools-lab-psi.vercel.app` は残す**（ご本人の判断）。
  URL自体が404なので害はなく、旧URLのインデックスが消えていく過程を見られるため

### 分かったこと（再調査不要）
- **Search Console の「プロパティを追加」UI が変わっている。** プロパティ選択の
  プルダウン →「プロパティを追加」→ **「ウェブサイトを追加」**（Instagram/TikTok/X/YouTube と
  並ぶ新メニュー）→ そこで初めて「ドメイン / URL プレフィックス」の選択が出る
- **同じGoogleアカウントで別プロパティを確認済みだと、同じHTMLタグの値が使い回される。**
  新URLで同じ `verification.google` を配信していれば、追加した瞬間に自動確認される
  （＝タグの貼り直し・再デプロイは不要だった）
- 追加直後は画面が旧プロパティのままになる。
  `…/sitemaps?resource_id=<URLエンコードした新URL>` へ直接移動すると切り替わる

### 次回への引き継ぎ事項・未解決の課題
- **push はまだ（8/17 07:53 時点）。19:56 以降に行う**。下の節と同じ理由
- note 公開済み2本の404リンク修正は**未着手**（ブラウザ・本人）

---

## 2026-08-17 — 改名（AIツールラボ → AIツールベース）とURL移行

**サブPC（`/Users/apple`）で実施。** メインPCへの引き継ぎは**まだ行われていない**ため、
`HANDOFF.md` の「以後はメインPCで触る」は**この時点では未発効**。

### 完了したこと
- **改名の理由**: 旧名「AIツールラボ」は同種メディアに類似名が多く（JAPAN AI ラボ 等）、
  名前で埋もれると判断。**外部に出ていたのが4本（Zenn2・note2）だけの今が最小コスト**
- 表示名 `AIツールラボ` → `AIツールベース`（`src/lib/site.ts` / `layout.tsx` / `Hero.tsx`）
- slug・フォルダ名 `ai-tools-lab` → `ai-tools-base`（`git mv`。package.json / package-lock /
  `.gitignore` / ルート `CLAUDE.md` `TODO.md` / `content/works/*.json` / 全原稿）
- **本番URL `ai-tools-lab-psi.vercel.app` → `https://ai-tools-base.vercel.app`**
- `npm run validate` 通過（既存の⚠️4件＝review未記入、5件＝転載待ちのみ）／`npm run build` 成功

### 発生したエラーと解決策
- **`grep -rl` の結果を `for f in $FILES` で回したら、パスが改行ごと1つの文字列として
  perl に渡り、ほとんどのファイルが置換されなかった**（`Can't open TODO.md\n.gitignore\n…`）。
  それでも一部は成功していたため**「完了した」と誤認しかけた**。
  → **`find -print0 | xargs -0`** に変更。置換後は必ず `grep` で残存0件を確認する
- **`vercel project rename` をしても、綺麗なドメイン `ai-tools-base.vercel.app` は
  自動では付かない**。旧 `ai-tools-lab-psi.vercel.app` が本番ドメインのまま残る
- **`vercel alias set` でデプロイURLに直接エイリアスを張ると、Vercel の SSO 保護に掛かって
  302（`vercel.com/sso-api?url=…`）になる。** デプロイ単位のエイリアス扱いになるため。
  → **`vercel domains add <domain> <project>` でプロジェクトのドメインとして登録**すると 200 になる
- **`ai-tools-lab.vercel.app`（`-psi` 無し）は他人の別サイト**（title: `AI Tools Lab - AIツール比較・レビュー`）。
  自分のものと勘違いしかけた。**改名の判断を裏づける材料でもある**

### 分かったこと（再調査不要）
- **プロジェクト名を rename しても、旧ドメインは自動では失効しない。**
  rename 後も `ai-tools-lab-psi.vercel.app` は 200 を返し、canonical だけが新URLを指す状態になる。
  残す/消すは **`vercel alias rm` で選べる**

### 旧URLは削除した（ご本人の判断）
- 判断理由: **まだアクセスが無く、2つのURLが並存するほうがややこしい**。
  公開済み記事のリンクは**新URLで貼り直す**方針
- 削除したエイリアスは2つ: `ai-tools-lab-psi.vercel.app` / `ai-tools-lab-brain-dump.vercel.app`
  （`npx vercel alias rm <domain> --yes`）→ **どちらも 404 を確認**
- 現在のエイリアスは `ai-tools-base.vercel.app` / `ai-tools-base-brain-dump.vercel.app` の2つ

### 次回への引き継ぎ事項・未解決の課題
- **未コミット。** 改名の差分はまだ手元にある（`git mv` 済み・commit していない）
- **push は 8/17 19:56 以降にする。** リポジトリ直下 `articles/` には Zenn 未公開3本が
  置かれたままで、いま push しても投稿上限で弾かれる（公開済み2本のURL差し替えも同じ push で入る）
- **🔴 公開済み4本のリンクが今 404。旧URLを消したため。** 貼り直しが要る
  - **Zenn 2本** … 直下 `articles/` の原稿は新URLに直してある。**push すれば直る**
    （ただし 19:56 まで待つ。未公開3本が投稿上限で弾かれるため）
  - **note 2本** … **ブラウザで本人が修正**（本文の `AIツールラボ` と旧URL）
    - https://note.com/shinsei99/n/nad3f0dce2889
    - https://note.com/shinsei99/n/n0388b9c81b5f
- **Google Search Console は旧URLで登録されている。** 新URL `ai-tools-base.vercel.app` を
  別プロパティとして追加し、sitemap を出し直す（**ブラウザ・本人**）。旧プロパティは残してよい
- Vercel に **`drafts` という身に覚えのないプロジェクトがある**（9時間前に更新）。
  `drafts/` ディレクトリを誤ってデプロイした疑い。中身を確認して不要なら削除する

## 2026-08-16（続き4）— 集客の実装・制作記録2本追加・メインPCへ引き継ぎ

### 完了したこと
- **Google Search Console**: プロパティ登録 → 所有権確認（HTMLタグ方式）→ sitemap送信。
  ステータス「成功しました」/ 検出ページ数26。トークンは `src/app/layout.tsx` の
  `verification.google`（**消すと所有権が外れる**）
- **構造化データ（JSON-LD）**: Article / BreadcrumbList / WebSite
- **RSS `/feed.xml`** と `<link rel=alternate>` による自動検出
- **内部リンクの修復**（ここが最大の穴だった）
  - 制作記録の詳細ページ同士が繋がっていなかった → 末尾に「ほかの制作記録」3件
  - 記事内のツール名が**公式サイトへ直リンク**していて回遊が切れていた → `/tools/<slug>` へ
- **Zenn / note のプロフィールを整備**（自己紹介＋サイトURL。noteはクリエイターページにリンク表示）
- **制作記録を2本追加**（不動産）: `baikai-generator` / `ai-ticket-counter`。
  それぞれ Zenn・note の原稿も作成（計4本）→ 本体は本番反映済み
- **`HANDOFF.md` を作成**。以後の開発・公開は**メインPC**で行う

### 発生したエラーと解決策
- **`npx vercel --prod` の出力を `>/dev/null` に捨てて実行し、デプロイが走っていないのに
  成功したと誤認した**（本番に新ページが出ず404のままだった）。
  → **出力を見て `Aliased https://ai-tools-base.vercel.app` を目視確認する**
- **theta-viewer の制作記録は書けなかった。** サブPCの `README.md` は Vite の雛形のままで、
  `SESSION_LOG.md` も存在しない（gitにあるSESSION_LOGは5アプリぶんのみ）。
  **メインPCに未コミットの記録がある可能性が高い**ので保留。憶測では書かない
- note のプロフィールには**ウェブサイト専用の欄が無い**（ソーシャルリンクはX/Instagram等のみ）。
  自己紹介文にURLを書くとリンクになる

### 次回への引き継ぎ事項・未解決の課題
- **`ai-tools-lab/HANDOFF.md` を参照。** 引き継ぎ手順はそこに集約した
- 公開待ち: Zenn 5本 / note 5本（`drafts/PUBLISH.md` に日別の順番表あり）
- theta-viewer の記録はメインPCで素材を確認してから

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
- **Vercel公開**: https://ai-tools-base.vercel.app （全ページ200確認）
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
