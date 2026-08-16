# articles/ — Zenn の記事

**Zenn の GitHub連携がこのディレクトリを見る。** リポジトリ直下に `articles/` を置く
のがZennの決まりで、ここに `.md` を push すると公開される（frontmatter の
`published: true` のものだけ）。

- 原稿の元は `ai-tools-lab/drafts/zenn/` にある。**あちらが原本**で、ここへコピーする
- ファイル名がそのまま記事のURL（slug）になる。半角英数とハイフンのみ、12〜50字
- `published: false` にすると下書き扱い。公開せずにプレビューできる

## 3媒体の分け方

本体（ai-tools-lab）・Zenn・note で**同じ本文を出さない**。
Zenn はドメインが強いので、全文が重複すると本体が自分の記事に負ける。
Zenn には「症状 → 原因 → 直し方」だけを載せ、プロンプト全文と過程は本体に置く。
詳細は `ai-tools-lab/drafts/README.md`。
