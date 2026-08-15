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
-- job_type: progress_1300 / closing_1800 / carryover_1000
CREATE TABLE IF NOT EXISTS scheduled_runs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date   TEXT NOT NULL,                        -- 'YYYY-MM-DD'
    job_type   TEXT NOT NULL,
    ran_at     TEXT NOT NULL DEFAULT (datetime('now')),
    result     TEXT,
    UNIQUE(run_date, job_type)
);
