# AI業務マネージャー（chatwork-ai-manager）

Chatwork を業務基盤として、AI専用アカウント「claude」が**社内のAI社員**として働くシステム。
社員が普段どおりChatworkで会話するだけで、AIが会話を理解し **TODO抽出・進捗管理・
期限/放置/漏れ検知・社内資料Q&A・定時の進捗確認** までを継続的に行う。
Claude Code 型の**エージェント**（自分で複数ツールを反復実行して調べ・操作してから答える）。

> 運用ルール・アーキテクチャ詳細は `CLAUDE.md`、計画は `TODO.md`、作業履歴は `SESSION_LOG.md` を参照。

## 必要環境
- macOS / Python **`/usr/bin/python3`**（3.9系）。venv Python は使わない（claude subprocess が SIGSEGV するため）。
- `claude` CLI（ログイン済み・MAX/Pro。Anthropic APIキー不要）。
- 依存: `streamlit pandas pymupdf openpyxl python-docx`（`pip install --user -r requirements.txt`）。
- SQLite（標準・WAL・FTS5）。

## セットアップ
1. `.streamlit/secrets.toml` を作成（`.streamlit/secrets.toml.example` 参照）:
   ```toml
   chatwork_api_token = "（claude用アカウントのAPIトークン）"
   dashboard_password = "（管理画面ログインパスワード）"
   knowledge_source_dir = "（社内資料フォルダ。例: Dropbox共有フォルダ）"
   ```
2. 依存インストール: `/usr/bin/python3 -m pip install --user -r requirements.txt`
3. DB初期化（自動・冪等）: 初回起動時に `db/migrate.py` が走る。

## 起動
- 管理画面（Streamlit・port 8540）: `bash run.sh` → http://localhost:8540
- 常時起動デーモン（監視・解析・定時処理）: `bash run_worker.sh`
- **恒久化（launchd・24時間稼働・自動復旧）**: `bash install-launchd.sh`
  - 2サービス登録: `com.shinsei.chatwork-ai-manager`(dashboard) と `-worker`(daemon)。
  - worker は **flock で単一化**（多重起動不可）。

## Chatwork 設定
- claude用アカウントで API Token を発行 → `chatwork_api_token` に設定。
- 接続確認: `/usr/bin/python3 worker.py --whoami`
- 監視ルーム設定: 管理画面「ルーム設定」で対象ルームにチェック（または `worker.py --monitor <room_id>`）。

## 使い方（社員はChatworkで普通に会話するだけ）
- 依頼「田中さんに○○を明日までにお願いします」→ AIが自動でTODO化（依頼者/担当/期限/発生元を保存）。
- 進捗「確認中です」「終わりました」→ TODOを進行中/完了に自動更新。
- 質問「@Claude ○○案件どうなってる？」「メゾンドール都島501の入居者は？」→ AIが資料/履歴/TODOを横断調査して回答。
- 定時: **13:00 昼の進捗確認 / 18:00 終業前確認 / 翌10:00 前日未完了・期限超過確認**（AIが優先度判断して必要な相手だけ確認）。

## AIが使えるツール（Common Tool Layer）
`services/agent_tools/` に安全なラッパー関数として実装。CLI入口は `agent_tool.py <tool> '<JSON>'`（`--list`で一覧）。
kb_search / chatwork_search / chatwork_get_messages / chatwork_post_message /
task_search / task_create / task_update / task_complete / task_progress_update /
project_search / project_update / tasks_needing_attention。
QA/自動解析/定時処理が**同じTool層**を共有する。

## アプリ開発（DEVELOPMENT Agent ＋ Visual Agent）※2026-08-17 追加
LINE / Chatwork から「○○アプリを作って」と言うだけで、**設計→実装→Build→起動→ブラウザで動作確認→
修正→テスト→README→Gitコミット**までAIが自分でやる。業務機能（TODO/検索/案件）とは別系統。

```
LINE/Chatwork → 既存Agent(qa) ─┬─ 業務 → 既存Tool層（変更なし）
                               └─ 開発 → dev_task_create（受付だけ・即応答）
                                            ↓ DB: dev_tasks
                                worker のループ → dev_runner.tick()（同時1本）
                                            ↓
                              claude（全ツール＋Playwright MCP）→ Workspace で開発
                                            ↓
                              進捗・質問・完了を依頼元の入口へ通知（notify）
```

- **新しい常駐プロセスは増やしていない。** 既存 worker のループに間借りする（scheduler と同じ流儀）。
- Task ID = `TASK-YYYYMMDD-XXX`。状態は
  `RECEIVED/PLANNING/RUNNING/WAITING_USER/TESTING/FAILED/COMPLETED/CANCELLED`
  （業務TODOの「未着手/進行中/完了」とは**別体系。混同しない**）。
- **再起動耐性**: 状態は全部DB。worker が落ちても起動時に `RUNNING → RECEIVED` へ戻し、
  claude の `session_id` を使って `--resume` で続きから再開する（最初からやり直さない）。
- **INTERRUPT**: 人の判断が要るとき（本番デプロイ・課金・不可逆操作・重大な仕様判断）だけ
  `WAITING_USER` で止まり、質問が入口へ届く。返事をすると同じTaskが再開する（`dev_task_answer`）。
- **Visual Agent**: 実際のChrome（headless）を操作して表示・操作・コンソール・レスポンシブを確認する。
  定義は `~/.mcp.json` の1ファイルで、**ターミナルのClaude Codeと共通**（→ `~/VISUAL_AGENT.md`）。
- **権限**: Chatworkは `dev_allowed_account_ids`（既定は管理者のみ）。社員が勝手にコードを書かせられない。
  LINEは既存の userId 許可制をそのまま使う。
- 管理画面の「🛠 開発タスク」で一覧・実行ログ・質問への回答・タスク直接投入ができる。
- 関連設定（システム設定）: `dev_agent_enabled` / `dev_model` / `dev_timeout_sec` /
  `dev_workspace`（既定 `/Users/apple`）/ `dev_mcp_config` / `dev_allowed_account_ids` / `dev_max_attempts`。

## GIS / 地図（管理物件の位置情報）※2026-08-17 追加
「この物件の近くに自社物件ある？」「管理物件を地図にして」「どのエリアに集中してる？」に答える。
**常駐AgentもターミナルのClaude Codeも同じ `services/agent_tools/gis_tools.py` を使う**（2系統に分けない）。

### データの作り方（最初に1回・台帳を更新したら再実行）
```bash
python3 ingest_properties.py          # 台帳Excel取込 → 住所→座標（未取得ぶんだけ）
python3 ingest_properties.py --stats  # 登録状況
```
- 元データは Dropbox の `★要更新★管理物件台帳.xlsx`。**ターミナルから実行する**
  （CloudStorage は launchd 常時起動からは読めない。`/bin/bash` にFDAがあれば常駐でも可）。
- 実績: **108件登録 / 88件に座標**。残り20件は**台帳の住所欄が空**（ほぼ仲介ビル）。
  台帳に住所を入れて再実行すれば地図に載る。
- **オーナーの連絡先・電話番号の列は意図的に取り込んでいない**（地図やLINEに出す情報ではないため）。

### Geocoding（住所→緯度経度）
- **国土地理院 住所検索API**（`msearch.gsi.go.jp`）。**APIキー不要・無料・政府提供**。
- OpenStreetMap の Nominatim は**利用規約で一括ジオコーディングを禁止**しているため使わない。
- 結果は `geocode_cache` テーブルに保存し、**同じ住所を二度外部へ問い合わせない**。呼び出し間隔1秒。
- ⚠️ **国土地理院は町名が特定できないと黙って区の中心座標を返す。** `geocode()` の戻りの
  `coarse=True` がその印。町名ごとに点を並べる用途では捨てること（全部同じ点に重なる）。

### ライブラリを追加していない理由（再検討しないための記録）
このMacは51本のアプリが共通の `/usr/bin/python3`(3.9) を使い、本番workerもそこで動いている。
geopandas は fiona/GDAL のバイナリを引き込むため、共有環境を壊す危険が利益に見合わない。
→ 距離は Haversine（純Python）、地図は Leaflet を読むHTMLを自前生成、GeoJSONは標準json。
将来ポリゴン解析（町丁目・ハザード重ね）が要るなら、その時に隔離venvで shapely を足す。

### Tool 一覧
`gis_property_search`（物件検索）/ `gis_nearby_properties`（半径検索・距離つき）/
`gis_distance`（2地点間）/ `gis_area_stats`（エリア別集計）/ `gis_create_map`（地図HTML生成）/
`gis_market_map`（**既存の reinfolib_transactions を再利用**して取引価格を重ねた地図）/
`gis_geocode` / `gis_export_geojson` / `gis_status`。

### 地図の置き場所・見方
- `chatwork-ai-manager/maps/` に HTML を保存（**gitignore**。実在の所在地とオーナー名を含むため）。
- 管理画面の「🗺 物件マップ」で表示・作成・物件一覧の確認ができる。
- 背景地図は地理院タイル。LINEには画像を送れないので、**要点を文章で返し**ファイル名を添える運用。

## 投稿モード（安全設計）
`confirm`（既定・AIの自発投稿はすべて管理画面で承認）/ `semi`（進捗確認等は自動）/ `auto`（全自動）。
管理画面「システム設定」で切替。@Claudeへの直接返信は常に送信。

## ナレッジ（社内資料RAG）
- 取込: `python3 ingest_knowledge.py [--dir <folder>] [--dry-run] [--full]`（PDF/Excel/Word/HTML/CSV/txt/.url）。
- OCR（スキャンPDF）: `python3 ocr_ingest.py`（claude vision・長時間）。
- 日次増分リフレッシュ: 既定 07:00 に worker が更新分のみ再取込（`scheduled_runs`で1日1回）。
- **⚠️ CloudStorage(Dropbox)取込はTCC権限が必要**。launchd常時起動で取込するには `/bin/bash` にフルディスクアクセスを付与。
  未付与ならターミナルから取込（検索・Q&AはローカルDBのみで常時起動でも動く）。

## バックグラウンド処理・定期処理
- worker.py が常時ループ: 新着取得→質問応答→TODO解析→定時処理→（post_modeに従い）投稿。
- ポーリング間隔・定時時刻は管理画面「システム設定」で変更可。

## 再起動・冪等
- 全状態はDB永続（TODO/進捗/確認履歴/処理済みメッセージ/定時履歴）。プロセスメモリに業務状態を持たない。
- 二重防止: messages.processed / last_message_id / outbox.dedup_key / tasks.dedup_key / scheduled_runs(UNIQUE)。
- 再起動時: 中断メッセージを pending へ戻す。同一TODO重複作成・定時ジョブ二重実行なし。

## トラブルシューティング
- worker が応答しない: `ps -eo pid,command | awk '/MacOS\/Python worker\.py$/{print $1}'` で稼働確認（1個であるべき）。
  再起動は `launchctl unload/load ~/Library/LaunchAgents/com.shinsei.chatwork-ai-manager-worker.plist`。
- claude が落ちる(-11): venv Python を使っていないか確認。必ず `/usr/bin/python3`。
- 日本語検索が弱い: FTSは trigram、索引は NFKC 正規化済み（半角/全角カナ吸収）。
- ログ: `~/Library/Logs/com.shinsei.chatwork-ai-manager*.log`。

## 主要ファイル
`worker.py`（デーモン）/ `app.py`＋`views/`（管理画面）/ `services/`（sync, analyzer, qa, scheduler,
chatwork, tasks, projects, knowledge, outbox, settings, agent_tools/,
**dev_tasks, dev_runner, notify**）/ `agent_tool.py`（Tool CLI）/
`db/`（schema, migrate, connection）/ `kb_search.py` / `ingest_knowledge.py` / `ocr_ingest.py` / `install-launchd.sh`。

## 運用メモ（ルート CLAUDE.md から移動・2026-08-17）

> 元の見出し: 「AI業務マネージャー（chatwork-ai-manager）補足 ※不動産・画面8540／LINE8530」
> **他PCと共有される情報。** ここを直せば2台で同じ内容になる。

- 詳細は `chatwork-ai-manager/README.md`（gitに入っている）と、同フォルダの `CLAUDE.md` / `TODO.md` /
  `SESSION_LOG.md`（識別子を含むため**gitignore**。Dropbox-個人のtarで運ぶ）。
- **⚠️ worker / LINE webhook / ngrok は「同時に1台のPCだけ」。** 2台で動かすとChatwork・LINEへ
  二重返信し、ngrok固定ドメインを奪い合う。移すときは先に旧PCで
  `launchctl unload ~/Library/LaunchAgents/com.shinsei.chatwork-ai-manager*.plist`。
- **PCをまたぐ引き継ぎ**: コードはgit、機密（secrets・`data/app.db`・内部docs・ngrok token）は
  `handoff_export.sh` → Dropbox-個人 → `handoff_import.sh`。**DBは双方向マージできない**ので、
  常駐を移す直前に必ず export→import で最新へ揃える。
- Python は **`/usr/bin/python3` 固定**（venv Python だと `claude` サブプロセスが SIGSEGV）。
