# Zenn の記事について

**原本はこのフォルダ。公開はリポジトリ直下の `articles/` から行う。**

**Zenn の GitHub連携がこのディレクトリを見る。** リポジトリ直下に `articles/` を置く
のがZennの決まりで、ここに `.md` を push すると公開される（frontmatter の
`published: true` のものだけ）。

- ここが原本。`~/articles/` へコピーして push すると公開される
- ファイル名がそのまま記事のURL（slug）になる。半角英数とハイフンのみ、12〜50字
- `published: false` にすると下書き扱い。公開せずにプレビューできる

## 3媒体の分け方

本体（ai-tools-lab）・Zenn・note で**同じ本文を出さない**。
Zenn はドメインが強いので、全文が重複すると本体が自分の記事に負ける。
Zenn には「症状 → 原因 → 直し方」だけを載せ、プロンプト全文と過程は本体に置く。
詳細は `ai-tools-lab/drafts/README.md`。

## デプロイが走らないとき

**Zenn は push を合図にデプロイする。** 連携より前に push した内容は、
連携しただけでは取り込まれない（webhookが発火していないため）。
**連携後に一度 push すれば取り込まれる。** 変更が無ければ空コミットでよい。

    git commit --allow-empty -m "trigger zenn deploy" && git push origin main

また `articles/` には **frontmatter のある .md だけ**を置く。
README のような通常のMarkdownを混ぜるとデプロイ時に警告・失敗の原因になる。
