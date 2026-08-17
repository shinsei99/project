# TODO — 全アプリの索引

> ## 🖥 メインPCでやること（2026-08-17 夜・サブPCから依頼）
>
> **まず `git pull origin main`。上から順に。終わったらこの節ごと消す。**
> コードと文書は全部gitに入れた。**Dropboxで運ぶものは無い**（今回サブPC→メインPCは git だけで足りる）。
>
> ```bash
> cd ~
> git pull origin main
>
> # ① このPCを「メインPC」と宣言する（点検ツールの期待値が逆になる）
> echo main > .dev-role      # PCごとの設定なのでgitに入らない。サブPCでは作らない
>
> # ② ai-tools-base のフォルダ改名の後始末（gitに乗らない実体だけ手で移す）
> mv ai-tools-lab/node_modules ai-tools-lab/.next ai-tools-lab/.vercel ai-tools-base/ 2>/dev/null
> mv ai-tools-lab/.env* ai-tools-base/ 2>/dev/null
> ls -a ai-tools-lab          # 空なら → rmdir ai-tools-lab
> cd ai-tools-base && npm run validate && cd ~     # 動くか確認（publish.sh はこちらへ移動済み）
>
> # ③ 環境の点検（今回追加した機能）
> ./dev-doctor.py --sync --fetch
> #   ★**メインPCの未コミット変更はサブPCから見えない。** ここで出たら中身を見てから commit/push
> #   ★Python/Node が .python-version(3.9.6) / .nvmrc(26.3.1) と違ったら**上げずにまず報告**
> #   ★メインPCは常駐があって正常。①をやっていれば警告にならない
>
> # ④ Zenn の残り1本（1日2本の上限。日付が変わってから）
> cd ai-tools-base && ./publish.sh zenn && sleep 90 && ./publish.sh status && cd ~
> #   ⬜ llm-pdf-split-gaps が ✅ になれば完了。そのあと note を2本（./publish.sh note <名前>）
>
> # ⑤ MCP `VISUAL_AGENT` の設定をサブPCへ渡す（サブPCには無い）
> D=~/Library/CloudStorage/Dropbox-個人/handoff-20260818; mkdir -p "$D"
> claude mcp get VISUAL_AGENT > "$D/mcp-visual-agent.txt"
> #   ※キーを含む可能性があるので**Dropbox経由・gitには入れない**。サブPCが取り込んだら置き場ごと削除
> #   サーバー本体がローカルのスクリプトなら、その実体も同じ置き場に入れる
>
> # ⑥ Claudeの記憶（メモリ）の差分を取り込む ← **gitに乗らないのでこれだけDropbox経由**
> #    置き場: ~/Library/CloudStorage/Dropbox-個人/handoff-20260818-sub-to-main/
> #    手順はその中の「先に読む.txt」に書いてある（MEMORY.md は上書きせず diff を見てから）
> #    取り込んだら置き場ごと削除する
>
> # ⑦ 開発ループの新ルール（CLAUDE.md 5〜7）を確認する
> ./dev-doctor.py --verify <アプリ>          # 検証の最低ラインを実行（smoke_test / 起動 / lint）
> ./dev-doctor.py --verify <アプリ> --build   # Nextのbuildも回す（Intel Macで数分）
> #   ★ run.sh は検証に使わない（不動産は 0.0.0.0＝LANに晒される）。--verify は 127.0.0.1 で立てる
> #   ★ chatwork-ai-manager と mail-merge-pro は自動検証しない（外部へ実際に送るため）
>
> # ⑧ 新しい道具（使うなら）
> ./va.sh --help          # Visual Agent: ブラウザを見て操作しUIを検証する
> ./see.sh --help         # Macの画面・pptx/pdfの見た目を見る
> #   Chromium は agent-platform/.venv の playwright を借りる。無ければ:
> #   agent-platform/.venv/bin/python -m playwright install chromium
> ```
>
> **この節を消す前に、⑥のDropbox置き場を削除したか確認する。**
>
> ### 今回サブPCで変えたこと（コミット7本・`954844d`〜`a86116d`＋SESSION_LOG）
>
> | 何を | 効果 |
> |---|---|
> | 改名の枝分かれを統合 | 両PCが同じ日に別々に改名していたのを1つに。**フォルダ名は `ai-tools-base` で統一** |
> | 整備ツール5本を再コミット | `.gitignore` の許可行漏れで実体が入っていなかった件を解消（575行入ったことを確認） |
> | `dev-doctor.py --sync` | 未コミット・stash・push漏れ・**ignoreされてgitに入っていないソース**・版の不一致・機密不足・常駐を検知 |
> | `.python-version` / `.nvmrc` | 現状値（3.9.6 / 26.3.1）を基準として固定。**pyenv/nvm は無いので自動切替はしない** |
> | CLAUDE.md 27,288→14,700字 | アプリ個別の事情12,999字を10本の `<アプリ>/README.md` へ移動（両PCに渡る場所） |
> | SESSION_LOG の見出しにPC名必須 | 同じ日付の節を2台が書いて衝突した実例の再発防止 |
> | TODO に「担当PC」列 | 2台で同じ作業を始める事故の防止 |
> | `va.sh` / `see.sh` | Claude Code が画面を見て確かめられるようにした |
> | **開発ループの明文化（CLAUDE.md 5〜7）** | 「完了の定義」＝実装＋検証＋目視＋記録。**アプリ種別ごとの検証の最低ライン**の表。自律で進めてよい範囲と**必ず聞くこと**（外部送信・公開・課金・戻せない操作・解釈が分かれる判断）。タスクの様式は大きい改修だけ |
> | `dev-doctor.py --verify <アプリ>` | その最低ラインを実行する。実測: business-plan-generator は smoke_test ✓ ＋ 127.0.0.1 で HTTP 200 ✓／ai-tools-base は validate ✓ lint ✓ |
>
> ### サブPCの現状（メインPCが知っておくこと）
>
> - **launchd 常駐 0本**（`file-finder` 8520 / `owner-payout-tracker` 8519 は unload＋**disable**）。
>   LAN公開なし。8540（chatwork管理画面）も停止済み。**worker/LINE/ngrok はメインPCのみで変更なし**
> - 依存は Python 31/31・Node 14/14（`business-plan-generator` の venv を作成）
> - 機密は**不足0件**（`digital-shosai/.env.local` は不要だったと判明。オンデバイス版で `process.env` 参照0件）
> - **Build/Test の実走は未実施**（判断により省略）。実施するなら外部に出るアプリを除外すること
>   （chatwork / mail-merge-pro / FTP公開 / Vercel本番 / prisma db push）
> - サブPCに `stash@{0} pre-origin-sync` とローカルブランチ2本が残っている。**消していない**
> - **メインPCでは `launchctl disable` を実行しないこと**（サブPC限定の設定）
>

**この表だけで「いま何が進行中か」が分かるようにする。** 詳細は書かない。
詳細は各アプリの `<アプリ>/TODO.md` と `<アプリ>/SESSION_LOG.md` にある。

書き方: 1アプリ1行。終わったら行を消す（記録はアプリ側のログに残るので消してよい）。

| アプリ | 担当PC | いまの状態 / 次にやること | 最終更新 |
|---|---|---|---|
| pokecard-dex | サブ | 画像100%（31,520枚）。内訳に推定14枚・参考画像4枚・透かし2枚あり。次はそれらの実物差し替え | 2026-08-14 |
| flyer-creator | サブ | チラシクリエーター。型10種はagent-platform共通（直すのはagent-platform/core）。下帯ロゴ＋メイン写真の切取位置(上下)スライダー追加。次は物件データの未決3点 | 2026-08-16 |
| agent-platform | サブ | **完成扱いへ移行（2026-08-17）**: launchd 登録・0.0.0.0・社内LAN共有（8532）。残るのは作り込み（出来た .pptx 11枚の見栄え目視確認／字幕焼き込み／投稿API）で、通し実行はできる | 2026-08-17 |
| ai-tools-base | メイン（公開） | **AIツールベース**（2026-08-17改名。旧「AIツールラボ／ai-tools-lab」・旧URLは削除済み。**フォルダ名も ai-tools-base に統一**）。新URL https://ai-tools-base.vercel.app。メインPCで受領済み（npm install／validate 通過・Vercel link は brain-dump/ai-tools-base）。サブPCで Search Console 移行（sitemap 28件）とnote2本＋プロフィールのリンク修正まで完了。残: Zenn/note 5本ずつの公開（1日2本・Zenn→note の順） | 2026-08-17 |
| scrapmemo-petapeta | メイン（ASC） | スクラップ編集の先頭表示を修正＋ボタンを末尾へ。Web版は公開済み。1.0.3/build7 をASCへアップ済み。**残: ASCでビルド7を選び審査提出** | 2026-08-17 |
| digital-shosai | サブ | **広告を全撤去し、画像をWebP化（PNG比28.5%）・検索をv2で高速化（pageText分離・複数語AND・本で絞り込み）・蔵書画面/library（一覧と削除）を追加**。ブラウザで通し確認済み。次は**バックアップ書き出し**（端末内だけなので端末故障で全消失する） | 2026-08-17 |
| chatwork-ai-manager | メイン | Chatwork/LINE常駐AIエージェント（社内RAG・TODO/案件・Web/国交省API）。**常駐4サービスはメインPCで稼働中／サブPCは引き継ぎ受領済みで画面8540のみ起動**（worker・ngrokは1台のみ・同時起動禁止）。次はアプリ側TODO.mdを現状に更新 | 2026-08-16 |

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
- ~~`digital-shosai/.env.local` が不足~~ ✅ **そもそも不要だった**（2026-08-17実測）。完全オンデバイス版
  （pdf.js＋IndexedDB）に作り替えられており `process.env` の参照が0件。旧設計の `.env.local.example` を
  削除し manifest からも外した。→ **機密の不足は0件になった**
- ~~サブPCの launchd 常駐2本（file-finder 8520 / owner-payout-tracker 8519）~~
  ✅ 2026-08-17 に unload 済み。サブPCの launchd 常駐は**0本**（`launchctl list | grep shinsei` が空）。
  画面が要るときは `cd <アプリ> && ./run.sh` で都度起動する（常駐に戻さない）

- ~~CLAUDE.md のスリム化~~ ✅ **2026-08-17にサブPCで実施**。**27,288字 → 14,700字（46%削減）**。
  アプリ個別の補足 12,999字を10本の `<アプリ>/README.md` へ移し、CLAUDE.md にはポインタ一覧だけ残した
  （移動先: gyomu-manual / parking-map / kaitori-dm-maker / psa-collection / agent-platform /
  chatwork-ai-manager / flyer-creator / shorui-cabinet / photo-inpainter / theta-viewer）。
  **`quote-generator` だけは別リポジトリでREADMEが渡らないため CLAUDE.md に残した。**
  なお「`photo-inpainter/` `pdf-organizer/` はフォルダごと無視されてREADMEが渡らない」という
  以前の注意書きは**古い情報だった**（`!photo-inpainter/**` の許可行が既にあり、渡ることを実測）。
- **agent-platform をメインPCで動かすには別途ファイルが要る**（gitに入れていない）:
  `config/`（会社名・免許番号などの発行者情報）、`knowledge/`（学習データ。物件名が混ざる）、
  `.env`（`.env.example` をコピーしてGeminiキーを入れる）。Dropbox等で渡す。
