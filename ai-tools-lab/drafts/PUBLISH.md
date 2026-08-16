# 公開手順とURL記録

**公開の順番を守ること。** 本体を先に出してインデックスさせないと、
本体が後追い扱いになり、自分の記事に負ける。

1. 本体を公開（✅ 済み）
2. Google にインデックスされるのを待つ（数日〜1週間）
3. **Zenn** に出す（✅ 2026-08-16 に2本公開）
4. **note** に出す（Zenn の記事URLを本文から参照するため、Zennが先）

---

## 1本目：写真から電線を消すツール

| 媒体 | 原稿 | URL |
|---|---|---|
| 本体 | （公開済み） | https://ai-tools-lab-psi.vercel.app/works/photo-inpainter |
| Zenn | `articles/photo-inpainter.md` | ✅ https://zenn.dev/shinsei99/articles/photo-inpainter |
| note | `note/photo-inpainter.md` | ⬜ 公開後にここへ記入 |

**公開前に直すもの**
- [ ] `note/photo-inpainter.md` … 「品質が低い原因を突き止めてほしい」の鍵カッコ内は
      **再構成であり実際の文面ではない**。実際に打った指示に差し替えるか、鍵カッコを外す
      （原稿内にHTMLコメントで警告あり）
- [ ] `note/photo-inpainter.md` 末尾の Zenn リンク `(#)` を
      https://zenn.dev/shinsei99/articles/photo-inpainter に差し替え
- [x] `zenn/photo-inpainter.md` の frontmatter を `published: true` に（`articles/` へ複製済み）

---

## 2本目：Gemini API の罠 / AIが実在しない建物を描いた

| 媒体 | 原稿 | URL |
|---|---|---|
| 本体 | （公開済み） | https://ai-tools-lab-psi.vercel.app/works/agent-platform |
| Zenn | `articles/gemini-api-traps.md` | ✅ https://zenn.dev/shinsei99/articles/gemini-api-traps |
| note | `note/ai-generated-building.md` | ⬜ 公開後にここへ記入 |

**公開前に直すもの**
- [x] `zenn/gemini-api-traps.md` の frontmatter を `published: true` に（`articles/` へ複製済み）

---

## 投稿のしかた

### Zenn — **GitHub連携済み（2026-08-16）。以後は push だけでよい**

1. リポジトリ直下の **`articles/<slug>.md`** に記事を置く（`drafts/zenn/` は下書き置き場）
2. frontmatter は `title` / `emoji` / `type`（tech|idea）/ `topics`（5個まで）/ `published`
3. **ファイル名がそのままURLのslugになる。** 12〜50字の半角英小文字・数字・ハイフンのみ
4. push すると Zenn 側がデプロイする。`published: false` なら下書きのまま
5. 公開の確認は `curl -s "https://zenn.dev/api/articles?username=shinsei99&order=latest"`

> **連携が効いていないときの見分け方**: push しても記事が増えない場合、
> GitHub App が未インストールのことがある（github.com/settings/installations で確認）。
> **App のインストールはブラウザでの承認が必須で、CLI からは実行できない。**
> 連携より前の push は取り込まれないので、連携後に空コミットを1つ push する。

> 画面から出す場合（連携なし）は `drafts/zenn/paste/*.txt` を投稿画面に貼る。
> frontmatter を投稿画面用の値に変換済み。

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

- [x] 本体の該当記録から Zenn へのリンクを張る（2026-08-16。`workSchema.links` を追加し、
      `/works/[slug]` に「この記録から書いた記事」を表示）
- [ ] note を出したら、同じ `links` に note のURLを足す
- [ ] 1週間後にアクセスを見る。**どの媒体から来たか**を必ず確認する
      （どちらが効くか分かれば、次にどこへ力を入れるか決められる）
