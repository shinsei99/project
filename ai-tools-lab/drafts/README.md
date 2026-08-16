# drafts/ — 外部媒体へ出す原稿

**本体サイトには表示されない**（`content/` の外にあるため）。ここは Zenn / note へ
投稿するための原稿置き場。

## 3媒体の分け方（重複コンテンツを作らないこと）

| 媒体 | 切り口 | 読者 | 技術用語 |
|---|---|---|---|
| **note** | 経緯と結果の物語 | 非エンジニア・経営者・同業 | **使わない**。全部ふつうの言葉に置き換える |
| **Zenn** | 症状 → 原因 → 直し方 | エンジニア | 使う。再現手順とコードを出す |
| **本体** | プロンプト全文・過程・機能一覧 | 両方 | 使う。3つの中で最も詳しい |

**全文コピーは禁止。** Zenn / note はドメインの力が強いので、同じ本文があると
Google はそちらを本命と判断し、本体が自分の記事に負ける。

## 出す順番

1. **本体に完全版を公開**
2. Google にインデックスされるのを待つ（数日〜1週間）
3. Zenn / note に部分版を出し、本体へリンクする

逆にすると本体が後追い扱いになる。


## 原稿の一覧

**方針: 本体の「不動産」カテゴリの公開記録と、Zenn / note の本数を揃える。**
ツール・ゲーム分類のものは転載しない（本体だけに置く）。

| 素材（不動産・公開） | Zenn | note | 本体 |
|---|---|---|---|
| photo-inpainter | `zenn/photo-inpainter.md` ✅公開 | `note/photo-inpainter.md` ✅公開 | `/works/photo-inpainter` |
| agent-platform | `zenn/gemini-api-traps.md` ✅公開 | `note/ai-generated-building.md` ✅公開 | `/works/agent-platform` |
| chatwork-ai-manager | `zenn/ai-agent-always-on.md` | `note/ai-always-on.md` | `/works/chatwork-ai-manager` |
| port-conflict | `zenn/launchd-restart-loop.md` | `note/silent-failure.md` | `/works/port-conflict` |
| shorui-cabinet | `zenn/llm-pdf-split-gaps.md` | `note/scanned-pile.md` | `/works/shorui-cabinet` |

**note の原稿には Zenn 記事のURLを先に書いてある。** ZennのURLはファイル名から決まる
（`https://zenn.dev/shinsei99/articles/<ファイル名>`）ので、公開前でも確定できる。
ただし**Zennを先に公開すること**（noteから死んだリンクを出さない）。

## 出さないと決めたもの

- **psa-collection … 本体からも外した（2026-08-16）。**
  `content/works/psa-collection.json` を `visibility: internal` にしてページを止めてある
  （削除ではないので戻せる）。**Zenn / note にも出さない。**
  理由: 他社サイトの内部APIを叩く手順を公開する形になり、
  自分のデータを取るぶんには問題なくても、手順書として出すと規約違反を助長しかねない。
- 転載の対象は**不動産カテゴリの公開記録のみ**。ツール分類（flyer-creator /
  ios-build-number など）とゲームは本体だけに置く。
