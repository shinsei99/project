# AIツールラボ（ai-tools-lab）

**「Claude Code を主軸に」**を旗印に、チャット型AI → 自律型AIエージェントへの変革期を
開発者・副業ワーカー・IT初心者へ翻訳するメディア兼Webアプリ。

port **3004** / 127.0.0.1（ツール分類・社内LAN共有なし）。起動は `bash run.sh`。

## 4つのコンテンツ軸

| 軸 | 置き場所 | 中身 |
|---|---|---|
| ツール比較 | `content/tools/*.json` | 5軸の共通評価・料金・強み弱み |
| 記事 | `content/articles/*.mdx` | 導入ガイド、歴史特集、比較、プロンプトの型 |
| 制作記録 | `content/works/*.json` | **プロンプト／機能／過程／改善過程** |
| 内蔵ツール | （未着手） | 将来のSaaS。`/apps/*` を予定 |

## 設計の芯（変えると高くつく決定）

1. **コンテンツはファイル。** AIと自動化スクリプトが git diff で読める形で直接書き換えられることを最優先。管理画面もDBも作らない
2. **読み出しは `src/lib/content/source.ts` の1箇所に閉じる。** DBへ移すときはこのファイルだけ差し替える
3. **スキーマは `src/lib/schema.ts` に1本化。** `npm run validate` で公開前に落とす
4. **制作記録は `visibility` が必須。** `getWorks()` は `public` しか返さない（安全装置であり、表示側の都合ではない）

## コマンド

```bash
bash run.sh          # 開発サーバー（http://127.0.0.1:3004）
npm run validate     # コンテンツ検証。公開前に必ず通す
npm run photos       # フリー写真を Openverse から取り込む
npm run build        # 本番ビルド
```

## フリー素材の扱い（重要）

- 取得元は **Openverse**（APIキー不要）。マルチプロダクション（`../agent-platform`）と同じ経路
- **`license=cc0,pdm` に絞っている。** CC BY / BY-SA は出典表示が義務で、ページ構成を変えた
  ときに表示が落ちればライセンス違反になる。**そもそも表示義務のない素材だけを取る**ことで
  構造的に防ぐ方を選んだ（母数は減る）
- 取り込んだ画像は `public/photos/` に置き、サイトを自己完結させる。外部ホストを直接参照すると
  向こうが落ちたときに見栄えが壊れる
- クレジット記録（`content/photo-credits.json`）と表示コンポーネントは残してある。将来 CC BY を
  混ぜた場合、`needsCredit` が立って**自動でフッターに出典が出る**
- 写真が無い記事は `CoverArt` が **slug から決定的に生成するSVG**を表紙にする。外部依存ゼロで、
  同じ記事なら毎回同じ絵になる

## 実測メモ

- Next.js 16.3.1 + React 19 + Tailwind v4 + TypeScript。`create-next-app` の雛形から開始
- 本番ビルドは約9秒（Turbopack）
- Tailwind v4 は `@theme` でトークンを定義すると `bg-surface` / `text-muted` などのユーティリティが
  自動生成される。色は `globals.css` 以外に直書きしない
