# TODO — 全アプリの索引

**この表だけで「いま何が進行中か」が分かるようにする。** 詳細は書かない。
詳細は各アプリの `<アプリ>/TODO.md` と `<アプリ>/SESSION_LOG.md` にある。

書き方: 1アプリ1行。終わったら行を消す（記録はアプリ側のログに残るので消してよい）。

| アプリ | いまの状態 / 次にやること | 最終更新 |
|---|---|---|
| pokecard-dex | 画像100%（31,520枚）。内訳に推定14枚・参考画像4枚・透かし2枚あり。次はそれらの実物差し替え | 2026-08-14 |
| flyer-creator | チラシクリエーター。型10種はagent-platform共通（直すのはagent-platform/core）。下帯ロゴ＋メイン写真の切取位置(上下)スライダー追加。次は物件データの未決3点 | 2026-08-16 |
| agent-platform | 講演スライドを .pptx で作り直し（4:3・型8種）＋フリー素材自動補充（Openverse）。11枚の通し実行は成功、**見栄えの目視確認が未了**。作り込みはいったん停止 | 2026-08-15 |
| ai-tools-base | **旧「AIツールラボ／ai-tools-lab」から改名（2026-08-17）。新URL https://ai-tools-base.vercel.app。Search Console登録・sitemap送信（28件）とnote2本＋プロフィールのリンク修正は完了。残るは 19:56 以降の `git push` だけ**（これでZenn2本のリンクも直る）。サブPCで作業継続中 | 2026-08-17 |
| chatwork-ai-manager | Chatwork/LINE常駐AIエージェント（社内RAG・TODO/案件・Web/国交省API）。**常駐4サービスはメインPCで稼働中／サブPCは引き継ぎ受領済みで画面8540のみ起動**（worker・ngrokは1台のみ・同時起動禁止）。次はアプリ側TODO.mdを現状に更新 | 2026-08-16 |

## 横断作業（複数アプリにまたがるもの）

- **【明日いちばん最初】メインPCで `./secrets-sync.sh export` を実行 → サブPCで `import`**
  サブPCに無いのは `digital-shosai/.env.local` / `psa-collection/data/{orders,albums}.json` の3件。
  これでサブPCで全アプリが触れる状態になる（依存は2026-08-16に整備済み・不足0本）
- **ai-tools-base: Zenn 5本 / note 5本の公開待ち。** Zennの投稿上限が **8/17 19:56** に解ける。
  1日2本ずつ Zenn→note の順で。手順は `ai-tools-base/drafts/PUBLISH.md`。
  **19:56 より前に push しない**（直下 `articles/` の未公開3本がまた弾かれる）
- ~~ai-tools-base 改名の残件（Search Console・note のリンク修正）~~ ✅ 8/17 に完了。
  **残っているのは 19:56 以降の `git push` だけ**（Zenn 2本のリンクがそれで直る）
- サブPCの launchd 常駐2本（file-finder 8520 / owner-payout-tracker 8519）を
  止めるか要判断（メインPCと二重にLAN公開されている・個人情報を含む）

- **CLAUDE.md のスリム化（メインPCで実施予定・2026-08-15決定）**
  現状19,159字。うち**55%（約10,500字）がアプリ個別の補足**（psa-collection 3,539字／
  agent-platform 2,064字／photo-inpainter 1,518字／pdf-organizer 1,128字 ほか）。
  これを**各アプリの README.md へそのまま移し、CLAUDE.md には1行のポインタだけ残す**。
  狙い: CLAUDE.md は全セッション・全ターンに乗る固定費のため、半分以下（約8,700字）にする。
  **注意**: 移す前に `.gitignore` に許可行が要る。`photo-inpainter/` `pdf-organizer/` は
  フォルダごと無視されており、README を作っても**他PCへ渡らない**（README自体もまだ無い）。
  共通ルール（PDCA・バインド先・iOS再配信・ポート一覧・アプリ一覧）は**CLAUDE.mdに残す**。
- **agent-platform をメインPCで動かすには別途ファイルが要る**（gitに入れていない）:
  `config/`（会社名・免許番号などの発行者情報）、`knowledge/`（学習データ。物件名が混ざる）、
  `.env`（`.env.example` をコピーしてGeminiキーを入れる）。Dropbox等で渡す。
