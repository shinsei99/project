# 公開手順とURL記録

**公開の順番を守ること。** 本体を先に出してインデックスさせないと、
本体が後追い扱いになり、自分の記事に負ける。

1. 本体を公開（✅ 済み）
2. Google にインデックスされるのを待つ（数日〜1週間）
3. **Zenn** に出す
4. **note** に出す（Zenn の記事URLを本文から参照するため、Zennが先）

---

## 1本目：写真から電線を消すツール

| 媒体 | 原稿 | URL |
|---|---|---|
| 本体 | （公開済み） | https://ai-tools-lab-psi.vercel.app/works/photo-inpainter |
| Zenn | `zenn/photo-inpainter.md` | ⬜ 公開後にここへ記入 |
| note | `note/photo-inpainter.md` | ⬜ 公開後にここへ記入 |

**公開前に直すもの**
- [ ] `note/photo-inpainter.md` … 「品質が低い原因を突き止めてほしい」の鍵カッコ内は
      **再構成であり実際の文面ではない**。実際に打った指示に差し替えるか、鍵カッコを外す
      （原稿内にHTMLコメントで警告あり）
- [ ] `note/photo-inpainter.md` 末尾の Zenn リンク `(#)` を、公開後のZenn URLに差し替え
- [ ] `zenn/photo-inpainter.md` の frontmatter を `published: true` に

---

## 2本目：Gemini API の罠 / AIが実在しない建物を描いた

| 媒体 | 原稿 | URL |
|---|---|---|
| 本体 | （公開済み） | https://ai-tools-lab-psi.vercel.app/works/agent-platform |
| Zenn | `zenn/gemini-api-traps.md` | ⬜ 公開後にここへ記入 |
| note | `note/ai-generated-building.md` | ⬜ 公開後にここへ記入 |

**公開前に直すもの**
- [ ] `zenn/gemini-api-traps.md` の frontmatter を `published: true` に

---

## 投稿のしかた

### Zenn
1. https://zenn.dev/ で GitHub アカウントでログイン
2. 「記事を投稿」→「Markdownで投稿」
3. 原稿の frontmatter より下（`---` の次の行以降）を貼り付け
4. タイトル・emoji・トピックは frontmatter の値を画面側で設定する
5. 公開後、URLを上の表に記入

> 継続するなら **GitHub連携**（リポジトリの `articles/` を push で公開）に切り替えると楽。
> ただし記事が数本たまってからでよい。

### note
1. https://note.com/ でアカウント作成
2. 「投稿」→「テキスト」
3. 原稿の見出し（`# 〜`）はnoteの見出し機能に置き換える。Markdownはそのままでは効かない
4. 本文中のリンクはnoteのリンク機能で貼る
5. 公開後、URLを上の表に記入

> **note は技術用語を落としきること。** 原稿はその前提で書いてあるが、
> 追記するときも同じ基準を守る。

---

## 公開後にやること

- [ ] 本体の該当記録から、Zenn / note へのリンクを張る（相互リンク）
- [ ] 1週間後にアクセスを見る。**どの媒体から来たか**を必ず確認する
      （どちらが効くか分かれば、次にどこへ力を入れるか決められる）
