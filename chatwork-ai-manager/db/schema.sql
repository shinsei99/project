-- chatwork-ai-manager DB schema (SQLite / FTS5)
-- 冪等: すべて CREATE ... IF NOT EXISTS。migrate.py が起動時に実行する。

-- ルーム（監視対象フラグと取得境界を保持）
CREATE TABLE IF NOT EXISTS rooms (
    room_id          INTEGER PRIMARY KEY,
    name             TEXT,
    type             TEXT,
    monitored        INTEGER NOT NULL DEFAULT 0,   -- 1=解析対象
    last_message_id  TEXT,                          -- 取得済み境界（Chatworkのmessage_idは文字列）
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ルームメンバー（担当者名寄せ用）
CREATE TABLE IF NOT EXISTS members (
    room_id     INTEGER NOT NULL,
    account_id  INTEGER NOT NULL,
    name        TEXT,
    role        TEXT,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (room_id, account_id)
);

-- 取得した生メッセージ（processed=0 が未解析）
CREATE TABLE IF NOT EXISTS messages (
    message_id   TEXT PRIMARY KEY,                  -- Chatwork message_id（room内一意でないため単体でPKにできる値をそのまま使用）
    room_id      INTEGER NOT NULL,
    account_id   INTEGER,
    account_name TEXT,
    body         TEXT,
    send_time    INTEGER,                            -- Unix秒
    fetched_at   TEXT NOT NULL DEFAULT (datetime('now')),
    processed    INTEGER NOT NULL DEFAULT 0,          -- 0=未処理 1=処理済（後方互換）
    process_status TEXT NOT NULL DEFAULT 'pending',   -- pending/processing/done/failed（冪等・復旧用）
    process_error  TEXT,
    analysis_id  INTEGER
);
CREATE INDEX IF NOT EXISTS idx_messages_room_unprocessed ON messages(room_id, processed);
CREATE INDEX IF NOT EXISTS idx_messages_send_time ON messages(room_id, send_time);

-- 案件
CREATE TABLE IF NOT EXISTS projects (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    customer   TEXT,
    room_id    INTEGER,
    status     TEXT NOT NULL DEFAULT '進行中',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS project_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    event_type TEXT,
    note       TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- TODO（AI抽出タスク）
-- status: 未着手 / 進行中 / 確認待ち / 完了 / 期限超過 / 保留 / キャンセル / AI確認待ち
-- conf_*: 明示 / 高 / 推測 / 不明
CREATE TABLE IF NOT EXISTS tasks (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    content             TEXT NOT NULL,
    project_id          INTEGER,
    customer            TEXT,
    assignee_account_id INTEGER,
    assignee_name       TEXT,
    requester           TEXT,
    due_date            TEXT,                        -- ISO 'YYYY-MM-DD' or NULL(=未確定)
    due_raw             TEXT,                        -- 元の自然言語表現（例: 金曜まで）
    priority            TEXT NOT NULL DEFAULT '中',   -- 高 / 中 / 低
    status              TEXT NOT NULL DEFAULT '未着手',
    progress            INTEGER NOT NULL DEFAULT 0,   -- 0-100
    done_condition      TEXT,
    room_id             INTEGER,
    source_message_id   TEXT,                        -- 生成元メッセージ（§37 追跡）
    ai_reason           TEXT,                        -- なぜTODOと判断したか（§39）
    ai_confidence       TEXT,                        -- タスク全体の確信度
    conf_assignee       TEXT,
    conf_due            TEXT,
    conf_done           TEXT,
    conf_project        TEXT,
    is_speculative      INTEGER NOT NULL DEFAULT 0,   -- 1=AIの推測（漏れ候補など事実未確認）
    dedup_key           TEXT,                        -- 重複TODO防止キー
    last_activity_at    TEXT,                        -- 放置検出用（最後に動きがあった時刻）
    last_check_at       TEXT,                        -- AIが最後に進捗確認した日時
    last_progress_reply TEXT,                        -- 担当者からの最後の進捗回答
    check_count         INTEGER NOT NULL DEFAULT 0,  -- AIが進捗確認した回数
    escalation_stage    INTEGER NOT NULL DEFAULT 0,  -- 0=通常 1=13時 2=18時 3=翌10時 4=管理者報告
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_room ON tasks(room_id);
CREATE INDEX IF NOT EXISTS idx_tasks_dedup ON tasks(dedup_key);

-- TODOの状態変化・進捗の履歴（§14 根拠メッセージ保存）
CREATE TABLE IF NOT EXISTS task_events (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id           INTEGER NOT NULL,
    event_type        TEXT,                          -- created / status_change / progress / due_change / comment
    from_status       TEXT,
    to_status         TEXT,
    note              TEXT,
    evidence_message_id TEXT,                         -- 判断根拠のメッセージ
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_task_events_task ON task_events(task_id);

-- AI解析ログ（§41 追跡: なぜこのTODOが作られたか）
CREATE TABLE IF NOT EXISTS ai_analysis_logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id      INTEGER,
    kind         TEXT,                                -- extract / qa / progress / report ...
    message_ids  TEXT,                                -- json配列
    model        TEXT,
    prompt       TEXT,
    raw_output   TEXT,
    parsed       TEXT,                                -- json
    error        TEXT,
    duration_ms  INTEGER,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_ai_logs_room ON ai_analysis_logs(room_id, created_at);

-- 投稿キュー（§34-35 プレビュー・冪等）
-- status: pending / approved / sent / discarded / failed
CREATE TABLE IF NOT EXISTS outbox (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id             INTEGER NOT NULL,
    to_account_ids      TEXT,                          -- csv
    body                TEXT NOT NULL,
    reason              TEXT,                          -- 投稿理由
    kind                TEXT,                          -- progress_check / overdue / stale / missing / report / qa_reply / question
    related_task_id     INTEGER,
    related_message_id  TEXT,
    status              TEXT NOT NULL DEFAULT 'pending',
    mode                TEXT,                          -- 生成時の post_mode
    dedup_key           TEXT UNIQUE,                   -- 同一催促の二重投稿防止
    chatwork_message_id TEXT,
    error               TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    sent_at             TEXT
);
CREATE INDEX IF NOT EXISTS idx_outbox_status ON outbox(status);

-- 内部通知キュー（supervisorが生成→outboxへ）
CREATE TABLE IF NOT EXISTS notifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    type       TEXT,
    task_id    INTEGER,
    room_id    INTEGER,
    payload    TEXT,
    status     TEXT NOT NULL DEFAULT 'new',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ナレッジ（会社資料）
CREATE TABLE IF NOT EXISTS knowledge_documents (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    category     TEXT,                                -- 営業/経理/契約/人事/物件/社内規定 ...
    title        TEXT NOT NULL,
    version      INTEGER NOT NULL DEFAULT 1,
    filename     TEXT,
    filepath     TEXT,
    mime         TEXT,
    content_hash TEXT,                                -- 増分更新の変更検知（内容SHA1）
    source_mtime REAL,                                -- 元ファイルの更新時刻
    active       INTEGER NOT NULL DEFAULT 1,
    meta         TEXT,                                -- json
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_kdoc_filepath ON knowledge_documents(filepath, active);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id     INTEGER NOT NULL,
    ord        INTEGER,
    text       TEXT,
    source_ref TEXT,                                  -- 例: "P12" / "Sheet:見積" / ファイル名
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON knowledge_chunks(doc_id);

-- FTS5 全文検索（knowledge_chunks の text を対象・外部コンテンツ）
-- 日本語（空白なし）を部分一致検索するため trigram トークナイザを使う。
-- 注意: trigram は 3 文字以上のクエリでのみマッチ。2 文字以下の語は RAG 側で LIKE フォールバックする。
CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
    text,
    content='knowledge_chunks',
    content_rowid='id',
    tokenize='trigram'
);

-- FTS5 を knowledge_chunks に自動同期するトリガ（外部コンテンツ方式）
CREATE TRIGGER IF NOT EXISTS knowledge_chunks_ai AFTER INSERT ON knowledge_chunks BEGIN
    INSERT INTO knowledge_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS knowledge_chunks_ad AFTER DELETE ON knowledge_chunks BEGIN
    INSERT INTO knowledge_fts(knowledge_fts, rowid, text) VALUES ('delete', old.id, old.text);
END;
CREATE TRIGGER IF NOT EXISTS knowledge_chunks_au AFTER UPDATE ON knowledge_chunks BEGIN
    INSERT INTO knowledge_fts(knowledge_fts, rowid, text) VALUES ('delete', old.id, old.text);
    INSERT INTO knowledge_fts(rowid, text) VALUES (new.id, new.text);
END;

-- key-value 設定（post_mode 等）
CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value      TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 処理状態（ポーリング時刻・スケジューラ最終実行など）
CREATE TABLE IF NOT EXISTS processing_state (
    key        TEXT PRIMARY KEY,
    value      TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 定時処理の実行履歴（同日・同種の二重実行を防止）
-- job_type: closing_1800 / carryover_1000
CREATE TABLE IF NOT EXISTS scheduled_runs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date   TEXT NOT NULL,                        -- 'YYYY-MM-DD'
    job_type   TEXT NOT NULL,
    ran_at     TEXT NOT NULL DEFAULT (datetime('now')),
    result     TEXT,
    UNIQUE(run_date, job_type)
);

-- ============================================================
-- AIがChatworkへ送ったファイルの記録（Stage 9・2026-08-19）
-- 社内資料を外へ出す操作なので、「いつ・何を・どこへ・誰の依頼で」を必ず残す。
-- status: sent（送信済み）/ blocked（安全確認で弾いた）/ failed（送信失敗）
-- ============================================================
CREATE TABLE IF NOT EXISTS sent_files (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id       INTEGER NOT NULL,
    file_path     TEXT NOT NULL,          -- 送った元ファイル（共有フォルダ内の絶対パス）
    file_name     TEXT NOT NULL,
    file_size     INTEGER,
    message       TEXT,                   -- 添付時に添えた本文
    requester     TEXT,                   -- 誰に頼まれて送ったか
    requester_account_id INTEGER,
    chatwork_file_id TEXT,
    status        TEXT NOT NULL DEFAULT 'sent',
    error         TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_sent_files_room ON sent_files(room_id, created_at);

-- ============================================================
-- 保留中の依頼（claudeの詰まり中に受けた質問を捨てないための待避所。Stage 8・2026-08-19）
-- 業務TODO(tasks)とも開発タスク(dev_tasks)とも別物。「AIがまだ答えられていない質問」だけを持つ。
-- status: queued（復旧待ち）/ done（回答済み）/ failed（再試行しても駄目）/ cancelled
-- ============================================================
CREATE TABLE IF NOT EXISTS pending_requests (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    channel          TEXT NOT NULL,              -- 'line' / 'chatwork'
    question         TEXT NOT NULL,
    requester        TEXT,                       -- 表示名
    line_user_id     TEXT,                       -- channel='line' のときの返し先
    room_id          INTEGER,                    -- channel='chatwork' のときの返し先
    asker_account_id INTEGER,
    source_message_id TEXT,                      -- Chatworkの元メッセージ（重複積み防止）
    dedup_key        TEXT UNIQUE,                -- 同じ依頼を二重に積まない
    status           TEXT NOT NULL DEFAULT 'queued',
    attempts         INTEGER NOT NULL DEFAULT 0,
    last_error       TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
    answered_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_requests(status, created_at);

-- ============================================================
-- 開発タスク（DEVELOPMENT Agent）。既存の tasks（業務TODO）とは別物。混同しないこと。
-- status: RECEIVED / PLANNING / RUNNING / WAITING_USER / TESTING / FAILED / COMPLETED / CANCELLED
-- kind:   NEW_APP / EXISTING_APP / FEATURE_ADD / BUG_FIX / UI_CHANGE / API_DEVELOPMENT /
--         DATABASE_CHANGE / INVESTIGATION / OTHER
-- ============================================================
CREATE TABLE IF NOT EXISTS dev_tasks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id       TEXT NOT NULL UNIQUE,               -- TASK-YYYYMMDD-XXX（人が読む一意ID）
    title         TEXT,
    request       TEXT NOT NULL,                      -- ユーザー指示の原文
    kind          TEXT,
    status        TEXT NOT NULL DEFAULT 'RECEIVED',
    project_dir   TEXT,                               -- 対象プロジェクト（workspace配下の絶対パス）
    workspace     TEXT,
    channel       TEXT,                               -- chatwork / line / admin（結果の返し先）
    room_id       INTEGER,
    line_user_id  TEXT,
    requester     TEXT,
    requester_account_id INTEGER,                    -- Chatwork の依頼者（宛先メンション用）
    session_id    TEXT,                             -- claude CLI のセッション（中断からの再開用）
    question      TEXT,                               -- INTERRUPT の質問文
    answer        TEXT,                               -- ユーザーからの回答
    result        TEXT,                               -- 完了報告
    error         TEXT,
    log_path      TEXT,
    attempts      INTEGER NOT NULL DEFAULT 0,         -- 実行回数（再起動復元でも増える）
    started_at    TEXT,
    finished_at   TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_dev_tasks_status ON dev_tasks(status);

-- ============================================================
-- GIS / 地図。物件マスタ（管理物件台帳 Excel から取り込む）と住所→座標のキャッシュ。
-- 既存の projects（案件）とは別物。こちらは「建物そのもの」の台帳。
-- ⚠️ オーナーの連絡先・電話番号は**取り込まない**（地図やLINEに出す情報ではないため）。
-- ============================================================
CREATE TABLE IF NOT EXISTS properties (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id    TEXT NOT NULL UNIQUE,          -- 物件名から作る安定キー（P-0001 形式ではなく名前ベース）
    name           TEXT NOT NULL,
    category       TEXT,                          -- 種別: マンション/ビル/駐車場/看板/トランク など
    classification TEXT,                          -- 分類: 自社/管理/仲介/終了
    address        TEXT,
    postal_code    TEXT,
    built          TEXT,                          -- 築年数（原文のまま）
    structure      TEXT,                          -- 構造
    units          TEXT,                          -- 戸数
    access         TEXT,                          -- 交通
    owner          TEXT,                          -- オーナー（法人名/担当。電話番号は持たない）
    folder         TEXT,                          -- 社内フォルダの場所
    lat            REAL,
    lon            REAL,
    geo_source     TEXT,                          -- 座標の出所（gsi / manual）
    geo_query      TEXT,                          -- 実際に問い合わせた住所文字列
    geo_status     TEXT,                          -- ok / no_address / not_found / error
    active         INTEGER NOT NULL DEFAULT 1,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_properties_geo ON properties(lat, lon);
CREATE INDEX IF NOT EXISTS idx_properties_cls ON properties(classification, category);

-- 住所→座標のキャッシュ。同じ住所を二度と外部へ問い合わせないための土台。
CREATE TABLE IF NOT EXISTS geocode_cache (
    query      TEXT PRIMARY KEY,                  -- 正規化した問い合わせ文字列
    lat        REAL,
    lon        REAL,
    title      TEXT,                              -- 相手が返した正式表記
    source     TEXT,                              -- gsi など
    status     TEXT,                              -- ok / not_found / error
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 開発タスクの経過（監査・引き継ぎ用）
CREATE TABLE IF NOT EXISTS dev_task_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id    TEXT NOT NULL,                         -- dev_tasks.task_id
    event_type TEXT,                                  -- created/status/note/interrupt/answer/completed/failed
    note       TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_dev_task_events ON dev_task_events(task_id, created_at);

-- 業務日報（1日1人1本）。その日の会話＋TODOの動きから AI が生成する。
-- UNIQUE(report_date, person) で作り直しても増えない（冪等）。
CREATE TABLE IF NOT EXISTS daily_reports (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date  TEXT NOT NULL,               -- 'YYYY-MM-DD'
    person       TEXT NOT NULL,               -- 表示名（Chatworkの名前）
    account_id   INTEGER,                     -- Chatwork account_id（不明なら NULL）
    body         TEXT NOT NULL,               -- 日報本文（Markdown）
    summary      TEXT,                        -- 1行要約
    stats        TEXT,                        -- json（発言数/宛先/完了・進行中TODO数 …）
    evidence     TEXT,                        -- json（根拠にした message_id の配列）
    model        TEXT,
    generated_by TEXT,                        -- manual / scheduled
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(report_date, person)
);
CREATE INDEX IF NOT EXISTS idx_daily_reports_date ON daily_reports(report_date);

-- 業務月報（TASK-20260825-001。TASK-20260826-002でLINE起点に変更）。日報とは別物。
-- オーナーがLINEで直接送った内容（「月報開始」〜「月報終了」の間の材料）が起点。
-- 1セッション（trigger_message_id='line:<monthly_report_line_sessions.id>'）につき1本。
-- UNIQUE(trigger_message_id)で冪等。
CREATE TABLE IF NOT EXISTS monthly_reports (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    report_period       TEXT NOT NULL,          -- 'YYYY-MM'（作成月。表示・ファイル名用）
    trigger_message_id  TEXT NOT NULL UNIQUE,   -- 元になったセッション（'line:<session_id>'）
    room_id             INTEGER,
    summary             TEXT,                   -- 1行要約
    body                TEXT NOT NULL,          -- 月報本文（Markdown。日報と同じ見出し記法）
    evidence            TEXT,                   -- json（元にしたmonthly_report_line_items.idの配列）
    files               TEXT,                   -- json（添付ファイルの抽出結果 [{filename, ok, error}]）
    model               TEXT,
    generated_by        TEXT,                   -- manual / line / line_timeout
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_monthly_reports_period ON monthly_reports(report_period);

-- 業務月報のLINE材料受付セッション（TASK-20260826-002）。
-- オーナーがLINEで「月報開始」〜「月報終了」の間に送った内容だけが、その回の月報の材料になる。
CREATE TABLE IF NOT EXISTS monthly_report_line_sessions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    line_user_id  TEXT,
    status        TEXT NOT NULL DEFAULT 'open',   -- open / closed
    opened_at     TEXT NOT NULL DEFAULT (datetime('now')),
    closed_at     TEXT
);

CREATE TABLE IF NOT EXISTS monthly_report_line_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL REFERENCES monthly_report_line_sessions(id),
    kind        TEXT NOT NULL,     -- text / image / file
    filename    TEXT,
    text        TEXT,
    ok          INTEGER NOT NULL DEFAULT 1,
    error       TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_mr_line_items_session ON monthly_report_line_items(session_id);

-- 会社の休業日（年間休暇スケジュールExcelのオレンジ塗り＝休み）を写したもの。
-- 元ファイルは Google Drive 上にあり launchd からは読めないことがあるため、DBに持つ。
CREATE TABLE IF NOT EXISTS holidays (
    holiday_date TEXT PRIMARY KEY,           -- 'YYYY-MM-DD'
    note         TEXT,
    source       TEXT,
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Chatwork音声添付（ボイスメモ等）の文字起こし・要約キャッシュ（TASK-20260826-004）。
-- 同じ添付が会話コンテキスト（直近メッセージ）に何度も登場しても、二度と
-- Gemini/Claudeへ問い合わせないための土台（geocode_cacheと同じ考え方）。成功時のみ保存する
-- （失敗はキーの未設定・一時的な通信エラーがありうるため、次回また試せるようキャッシュしない）。
CREATE TABLE IF NOT EXISTS audio_transcripts (
    room_id     INTEGER NOT NULL,
    file_id     INTEGER NOT NULL,
    filename    TEXT,
    transcript  TEXT,
    summary     TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (room_id, file_id)
);
