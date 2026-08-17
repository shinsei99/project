# HANDOFF — AIツールベースをメインPCへ引き継ぐ

**2026-08-16、サブPC（`/Users/apple`）からメインPCへ移管する。**
以後の開発・公開はメインPCで行う。サブPC側では触らない。

**引き継ぐのはアプリのコードではなく「全アプリの制作過程」。**
サイトの中身は制作記録であり、その素材（実際に投げた指示・つまずき・直し方）は
**開発を実際にやったメインPCにしか無い**。だから移管する。→ 「§7 制作過程の集め方」

---

## 0. 最初に読むもの（この順で）

1. `ai-tools-lab/CLAUDE.md` … **この1本の運用ルール**（1本増やしたらZenn・noteも同時に出す）
2. `ai-tools-lab/SESSION_LOG.md` … 2026-08-16 の3節が今回ぶん（上が新しい）
3. `ai-tools-lab/drafts/README.md` … 3媒体の書き分けと、出さないと決めたもの
4. `ai-tools-lab/drafts/PUBLISH.md` … **公開待ちの順番表**（Zennは1日2本まで）

---

## 1. git から来るもの / 来ないもの

**来る（コード・文書は全部コミット済み）**

- サイト本体（`src/` `content/` `scripts/` `public/`）
- 原稿（`drafts/zenn/*.md` `drafts/note/*.md` `drafts/note/paste/*.txt`）
- Zenn公開用のディレクトリ … **リポジトリ直下の `articles/`**（`ai-tools-lab/` の中ではない）

**来ない（メインPCで用意する）**

| もの | どうするか |
|---|---|
| `node_modules/` | `npm install` |
| `.next/` `out/` | ビルドで再生成 |
| **`.vercel/`** | **`npx vercel link` でプロジェクト `ai-tools-lab`（team: brain-dump）に紐づける** |
| Vercel CLI のログイン | `npx vercel login`（現在の所有者は `daikyocorps-3085`） |

```bash
cd ai-tools-lab
npm install
npm run validate     # コンテンツ検証。ここが通らないならビルドしない
npm run build
./run.sh             # 127.0.0.1:3004
```

---

## 2. ⚠️ 引き継ぎで事故りやすい3点

### (1) Vercel は git 連携ではない。**手動デプロイ**

`git push` しても**本番は変わらない**。反映には必ずこれが要る。

```bash
npx vercel --prod
```

**出力を捨てないこと。** サブPCで `>/dev/null` に流して実行した結果、
デプロイが走っていないのに成功したと勘違いした（実際に1回やらかした）。
最後に `Aliased https://ai-tools-base.vercel.app` が出るのを目で見る。

### (2) Zenn は「直近24時間の投稿数」で制限がある

- 上限に達した記事は**黙ってデプロイされない**。デプロイ履歴は「成功」と出て、
  お知らせ欄にだけ「投稿数の上限に達したためデプロイされませんでした」と書かれる
- **時間が経っても自動で再試行されない。** 空けてから**もう一度 push** が要る
- したがって **Zennへ出すのは1日2本まで**にする
- 状況確認: https://zenn.dev/dashboard/deploys （要ログイン）または

```bash
curl -s "https://zenn.dev/api/articles?username=shinsei99&order=latest" | python3 -m json.tool | head -40
```

### (3) note は Markdown が効かない

`##` も `**` もそのまま文字として出る。**HTMLをクリップボードに載せて貼る**のが正解。

```bash
python3 drafts/note/md2html.py <原稿名>   # 例: upside-down
# → 本文欄で ⌘V。見出し・引用・箇条書き・リンクが一度に付く
```

見出し画像は編集画面の画像アイコン →「記事にあう画像を選ぶ」（みんなのフォトギャラリー）が速い。
`画像をアップロード` は hidden な file input が掴めず、自動操作できなかった。

---

## 3. いまの状態（2026-08-16 時点）

| | 本体 | Zenn | note |
|---|---|---|---|
| photo-inpainter | 公開 | ✅公開 | ✅公開 |
| agent-platform | 公開 | ✅公開 | ✅公開 |
| chatwork-ai-manager | 公開 | 原稿済み | 原稿済み |
| port-conflict | 公開 | 原稿済み | 原稿済み |
| shorui-cabinet | 公開 | 原稿済み | 原稿済み |
| baikai-generator | 公開 | 原稿済み | 原稿済み |
| ai-ticket-counter | 公開 | 原稿済み | 原稿済み |

- 集客の基盤は導入済み: OGP・記事ごとのOG画像・sitemap・robots・JSON-LD・RSS（`/feed.xml`）
- **Google Search Console 登録済み**（所有権はHTMLタグで確認。トークンは `src/app/layout.tsx` の
  `verification.google`。**消すと所有権が外れる**）。sitemap送信済み・ステータス「成功」

---

## 4. メインPCで最初にやること

1. **Zenn 5本・note 5本を、1日2本ずつ出し切る**（順番は `drafts/PUBLISH.md` の表）
   - 8/17 19:56 以降に投稿上限が解ける
   - Zenn: `drafts/zenn/<名前>.md` を**リポジトリ直下の `articles/`** へコピーして push
   - note: `md2html.py` → ⌘V → 見出し画像 → 投稿
   - 公開後、`content/works/<slug>.json` の `links` にURLを追記 → `npx vercel --prod`
   - `npm run validate` の「転載がまだです」警告が消えたら完了
2. **theta-viewer の制作記録**（サブPCでは書けなかった）
   - サブPCの `theta-viewer/README.md` は **Vite の雛形のまま**で、`SESSION_LOG.md` も無い
   - **メインPCに未コミットの開発記録がある可能性が高い**。あればそれを元に書く
   - 無ければ書かない。**憶測でプロンプトや経緯を書かないこと**
3. 制作記録を増やす（不動産カテゴリのみ転載対象）。素材が残っているのは
   `parking-map` / `realestate-valuation` / `restoration-calculator` / `settlement-creator` あたり

---

## 5. 触ってはいけない決まりごと

- **プロンプトは体裁と語調だけ整えてよい。内容と粒度は変えない**（`src/lib/schema.ts` のコメント）
  実際に一言で済ませた指示を、長い依頼へ書き直さない
- `content/works/*.json` の **`visibility` は必須**。`public` 以外はページに出ない
- **psa-collection は本体からも外してある**（`visibility: internal`）。Zenn/noteにも出さない。
  他社サイトの内部APIを叩く手順の公開になるため
- 転載の対象は**不動産カテゴリの公開記録だけ**。ツール・ゲーム分類は本体のみ
- 有料化は当面しない。まず無料で流入を作る（判断の経緯は SESSION_LOG に記載）

---

## 6. サブPC側の後始末

- サブPCでは**このアプリを触らない**。`run.sh` は 127.0.0.1 のままで、launchd 未登録なので放置でよい
- Chrome の Claude 拡張はサブPCで接続済みだが、メインPCでは**改めて接続が要る**
  （claude.ai に同じアカウントでログイン → 拡張を有効化）
- Zenn / note / Search Console のログインは**ブラウザ側の状態**なので、メインPCで入り直す

---

## 7. 制作過程の集め方（引き継ぎの本体）

本体の制作記録はいま7本。**不動産カテゴリのアプリは30本ある**ので、素材はまだ大量に残っている。
ただし**憶測で書かないこと**が絶対条件なので、出典のあるものだけを書く。

### 一次資料は3層ある

| 層 | 置き場 | そこから取れるもの |
|---|---|---|
| **① 会話ログ** | `~/.claude/projects/**/*.jsonl` | **実際に投げた指示**（唯一の出典。記憶で書くと粒度が変わる） |
| ② アプリの文書 | 各アプリの `SESSION_LOG.md` / `README.md` | 症状 → 原因 → 直し方、機能一覧、経緯 |
| ③ ルート `CLAUDE.md` | リポジトリ直下 | 「再調査不要」と書いてある結晶化した知見。改善過程の宝庫 |

**①が最重要。** サイトの方針は「体裁と語調は整えてよいが、**内容と粒度は変えない**」なので、
一言で済ませた指示は一言のまま載せる。それが読者にとっての情報になる。

### 会話ログから拾う道具

```bash
npm run prompts -- 間取り                 # キーワードを含むセッションの発話を出す
npm run prompts -- madori --first         # 各セッションの最初の1通だけ（着手の指示を探す）
npm run prompts -- "" --list              # セッション一覧だけ
npm run prompts -- 謄本 --dir /path/to/logs   # 別PCから持ってきたログを指定
```

⚠️ **出力には会社名・物件名・氏名がそのまま出る。** `content/` へ移すときは必ず伏せる。
`npm run validate` が敬称・電話番号・郵便番号・メールアドレスを検査するが、最後は人が見ること。

> サブPCで試したところ、`photo-inpainter` の開発セッションは**1件しかヒットしなかった**。
> 実際の開発はメインPCで行われている。**メインPC側のログが本命。**

### 1本ぶんの作り方（3点セット）

1. `npm run prompts -- <アプリ名>` で着手時の指示と、詰まった箇所のやりとりを拾う
2. アプリの `SESSION_LOG.md` / ルート `CLAUDE.md` から「症状 → 原因 → 直し方」を拾う
3. `content/works/<slug>.json` を書く（`visibility` 必須。プロンプトが取れないなら `prompts: []` でよい。
   **無理に埋めない**）
4. `drafts/zenn/<zenn-slug>.md`（技術）と `drafts/note/<名前>.md`（非技術）を書く
5. Zenn → note の順で公開 → `links` にURL追記 → `npx vercel --prod`
6. `npm run validate` の「転載がまだです」警告が消えたら1本完了

### 書く順番（素材の厚い順）

1. `parking-map` … レイアウト固定×データは毎回読む設計、個人情報を含む静的版は公開しない工夫
2. `realestate-valuation` … 登記簿/レントロール解析＋国交省・国土地理院API
3. `restoration-calculator` … 業者見積の解析とガイドラインの按分
4. `settlement-creator` … 重説と評価証明から日割り計算
5. `theta-viewer` … **メインPCに記録があるか先に確認**（サブPCのREADMEはViteの雛形のまま）

**ツール・ゲーム分類は本体だけに置く**（転載しない）。psa-collection は本体からも外してある。

