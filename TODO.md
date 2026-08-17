# TODO — 全アプリの索引

**この表だけで「いま何が進行中か」が分かるようにする。** 詳細は書かない。
詳細は各アプリの `<アプリ>/TODO.md` と `<アプリ>/SESSION_LOG.md` にある。

書き方: 1アプリ1行。終わったら行を消す（記録はアプリ側のログに残るので消してよい）。

| アプリ | いまの状態 / 次にやること | 最終更新 |
|---|---|---|
| pokecard-dex | 画像100%（31,520枚）。内訳に推定14枚・参考画像4枚・透かし2枚あり。次はそれらの実物差し替え | 2026-08-14 |
| flyer-creator | チラシクリエーター。型10種はagent-platform共通（直すのはagent-platform/core）。下帯ロゴ＋メイン写真の切取位置(上下)スライダー追加。次は物件データの未決3点 | 2026-08-16 |
| agent-platform | **完成扱いへ移行（2026-08-17）**: launchd 登録・0.0.0.0・社内LAN共有（8532）。残るのは作り込み（出来た .pptx 11枚の見栄え目視確認／字幕焼き込み／投稿API）で、通し実行はできる | 2026-08-17 |
| ai-tools-base | **AIツールベース**（2026-08-17改名。旧「AIツールラボ／ai-tools-lab」・旧URLは削除済み。**フォルダ名も ai-tools-base に統一**）。新URL https://ai-tools-base.vercel.app。メインPCで受領済み（npm install／validate 通過・Vercel link は brain-dump/ai-tools-base）。サブPCで Search Console 移行（sitemap 28件）とnote2本＋プロフィールのリンク修正まで完了。残: Zenn/note 5本ずつの公開（1日2本・Zenn→note の順） | 2026-08-17 |
| scrapmemo-petapeta | スクラップ編集の先頭表示を修正＋ボタンを末尾へ。Web版は公開済み。1.0.3/build7 をASCへアップ済み。**残: ASCでビルド7を選び審査提出** | 2026-08-17 |
| chatwork-ai-manager | Chatwork/LINE常駐AIエージェント（社内RAG・TODO/案件・Web/国交省API）。**常駐4サービスはメインPCで稼働中／サブPCは引き継ぎ受領済みで画面8540のみ起動**（worker・ngrokは1台のみ・同時起動禁止）。次はアプリ側TODO.mdを現状に更新 | 2026-08-16 |

## 横断作業（複数アプリにまたがるもの）

- **Zenn: 残り1本（`llm-pdf-split-gaps`）がまだ未反映。** 2026-08-17 20:00 のpushで
  `ai-agent-always-on` と `launchd-restart-loop` の2本は通った（1日2本の上限に当たって3本目が残った）。
  記事側の直しは不要（`published: true` のまま）。**明日の枠で再pushすれば通る**。自動再試行はされない。
  確認は `cd ai-tools-base && ./publish.sh status`（⬜ が未反映）
- **MCP `VISUAL_AGENT` の代わりに `./va.sh`（Visual Agent）を用意した**（2026-08-17）。
  ブラウザ起動・操作・DOM/a11y・Console/Network・レスポンシブ・UI崩れ検出まで手元で完結する。
  使い方は `CLAUDE.md` の「Claude Code の『目』」か `./va.sh --help`。
  **メインPCの `VISUAL_AGENT` の設定（`claude mcp get VISUAL_AGENT` の出力）がもらえたら、そちらも入れる。**
  MCPの設定は**gitに乗らない**（ユーザースコープ＝`~/.claude.json` の `mcpServers`）。サブPCは
  `claude mcp list` が空で、リポジトリ内に `VISUAL_AGENT` の文字列も0件（設定も実体も未受領）。
  要るもの: ①上記の出力 ②サーバー本体がローカル実装ならその実体（Dropbox経由）③キーが要るなら値は機密扱い。
  → **今後は「gitに乗らないPC側の設定」として `secrets-manifest.txt` の対象に加える**（漏れの再発防止）
- **見つかった未修正のUI崩れ（ai-tools-base・390px幅）**: 比較表が横に484pxはみ出していて
  料金列が読めない（`div.table-scroll` は `overflow-x:auto` だが手がかりが無い）。ロゴも2行に折れる
- 3媒体への公開はメインPCの担当（Chrome拡張・note/Zenn/Vercelのログインがある）。
  手順は `ai-tools-base/drafts/PUBLISH.md`、入口は `ai-tools-base/publish.sh`
- **メインPCで1回だけ必要な後始末（ai-tools-base のフォルダ改名を取り込むため）**
  サブPC・メインPCの両方で同じ改名をしたため 2026-08-17 に git で統合し、**フォルダ名は
  `ai-tools-base` に統一**した。メインPCは `git pull` 後、gitに入らない実体を手で移す:
  `mv ai-tools-lab/node_modules ai-tools-lab/.next ai-tools-lab/.vercel ai-tools-lab/.env* ai-tools-base/`
  → 移したら `rmdir ai-tools-lab`（`./publish.sh` は `ai-tools-base/` 側にある）
- `digital-shosai/.env.local` は**メインPCにも存在しない**（`.env.local.example` のみ）＝運べないので要件取り下げ。
- ~~サブPCの launchd 常駐2本（file-finder 8520 / owner-payout-tracker 8519）~~
  ✅ 2026-08-17 に unload 済み。サブPCの launchd 常駐は**0本**（`launchctl list | grep shinsei` が空）。
  画面が要るときは `cd <アプリ> && ./run.sh` で都度起動する（常駐に戻さない）

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
