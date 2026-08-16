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
- [x] `note/photo-inpainter.md` の鍵カッコ問題 … **鍵カッコを外して地の文にした**（2026-08-16）。
      実際の文面が分からない以上、引用の体裁で載せられないため。
      「改善ではなく原因の特定を頼んだ」という趣旨だけを残してある。
      **実際に打った文面を思い出したら、そちらへ差し替えてよい**（趣旨は変えないこと）
- [x] `note/photo-inpainter.md` 末尾の Zenn リンクを
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
- [x] `note/ai-generated-building.md` の末尾に制作記録（`/works/agent-platform`）への導線を追加

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

### note — **貼り付け用のテキストを用意済み**

**note は Markdown が効かない。** `##` も `**` もそのまま文字として出る。
そこで原稿から記法を落としたものを `note/paste/*.txt` に用意してある。

    python3 drafts/note/make_paste.py     # 原稿(.md)から paste/*.txt を作り直す

1. https://note.com/ でアカウント作成（**ブラウザ操作。AIは代行できない**）
2. 「投稿」→「テキスト」
3. `note/paste/<記事>.txt` の「▼ ここから下」以降を**全部**本文欄に貼る
4. ファイル先頭に**見出しにする行・引用にする行の一覧**があるので、その行を選んで
   note の「見出し」「引用」を押す（6箇所＋1箇所ほど）
5. 末尾のURLは、直前の文字を選んで note のリンク機能で貼り直す（生URLのままでもよい）
6. タイトルは同じくファイル先頭に書いてある
7. 公開後、URLを上の表に記入し、`content/works/*.json` の `links` にも足す

> **note は技術用語を落としきること。** 原稿はその前提で書いてあるが、
> 追記するときも同じ基準を守る。

> **改行に注意。** note は貼り付けた改行をそのまま行送りにする。原稿の折り返しのまま貼ると
> スマホで変な位置に改行が入るので、`make_paste.py` が段落を1行に繋いである。
> **原稿を直したら、貼る前に必ず作り直すこと。**

---

## 公開後にやること

- [x] 本体の該当記録から Zenn へのリンクを張る（2026-08-16。`workSchema.links` を追加し、
      `/works/[slug]` に「この記録から書いた記事」を表示）
- [ ] note を出したら、同じ `links` に note のURLを足す
- [ ] 1週間後にアクセスを見る。**どの媒体から来たか**を必ず確認する
      （どちらが効くか分かれば、次にどこへ力を入れるか決められる）
