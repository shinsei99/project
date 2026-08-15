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
- 管理画面（Streamlit・port 8529）: `bash run.sh` → http://localhost:8529
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
chatwork, tasks, projects, knowledge, outbox, settings, agent_tools/）/ `agent_tool.py`（Tool CLI）/
`db/`（schema, migrate, connection）/ `kb_search.py` / `ingest_knowledge.py` / `ocr_ingest.py` / `install-launchd.sh`。
