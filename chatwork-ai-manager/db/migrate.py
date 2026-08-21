"""schema.sql を冪等に適用し、初期設定を投入する。

worker/app どちらの起動時にも呼ばれる想定（CREATE ... IF NOT EXISTS なので何度でも安全）。
"""
import os

from db.connection import get_conn

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")

# 初期設定（存在しなければ挿入。既存値は上書きしない）
DEFAULT_SETTINGS = {
    "post_mode": "confirm",          # confirm / semi / auto（初期は安全側の確認モード）
    "poll_interval_sec": "30",
    "supervisor_interval_sec": "600",
    "due_soon_hours": "24",          # 期限まで何時間で進捗確認するか
    "stale_days": "3",               # 放置とみなす日数
    "morning_report_time": "08:30",  # 毎朝レポート時刻 HH:MM
    "morning_report_room_id": "",    # レポート投稿先（未設定なら投稿しない）
    "ai_prefix": "🤖AI業務マネージャー",
    # 定時進捗確認（Stage 3）
    "closing_check_time": "18:00",   # 終業前の未完了確認
    "carryover_check_time": "10:30", # 翌日の前日未完了・期限超過確認
    "scheduled_jobs_enabled": "1",   # 0で定時処理を停止
    "manager_room_id": "",           # 期限超過エスカレーションの管理者報告先（空なら発生元ルーム）
    "due_reminder_check_time": "09:00",  # 期限リマインドの時刻
    "due_reminder_days": "2",            # 期限の何日前にリマインドするか
    "weekly_report_mon_time": "10:30",   # 週次棚卸し（月曜・やり残し確認）の時刻
    "weekly_report_fri_time": "18:00",   # 週次棚卸し（金曜）の時刻
    # 業務日報（Stage 10・2026-08-21 オーナー指示で 18:30 自動）
    "daily_report_enabled": "1",
    "daily_report_time": "18:30",
    "daily_report_people": "塚本,松本,森",   # 空なら監視ルームのメンバー全員
    "daily_report_room_id": "",              # 空なら manager_room_id → 監視中のgroupルーム
    "daily_report_upload": "1",              # 1でChatworkへ自動アップ（post_modeは見ない）
    "daily_report_save_dir": ("/Users/apple/Library/CloudStorage/Dropbox-大京商事　株式会社/"
                              "共有フォルダ/（★必読★）新共有フォルダ/社内・総務/業務日報"),
    # 会社の休業日（年間休暇スケジュール。オレンジ＝休み）。この日は日報を作らない
    "holiday_schedule_path": ("/Users/apple/Library/CloudStorage/GoogleDrive-daikyocorp.s@gmail.com/"
                              "その他のパソコン/マイ Mac mini/Desktop/ルーティーン/"
                              "年間休暇スケジュール2026.xlsx"),
    # 日次ナレッジ増分リフレッシュ（Stage 5）
    "knowledge_refresh_enabled": "1",
    "knowledge_refresh_time": "07:00",
    # 役割別モデル（枠節約）: 分類系=軽量haiku / 回答系=sonnet
    "model_analyzer": "haiku",   # TODO抽出・進捗・完了判定（分類タスク）
    "model_scheduler": "haiku",  # 定時の催促文生成（定型）
    "model_qa": "sonnet",        # @Claude質問回答・エージェント（多段推論）
    "model_daily_report": "sonnet",  # 業務日報の文章化（会話をまとめる）
    # ---- DEVELOPMENT Agent（アプリ開発。既存の業務TODOとは別系統）----
    "dev_agent_enabled": "1",           # 0 で開発タスクの実行を停止（受付は残る）
    "dev_model": "sonnet",              # 開発エージェントのモデル
    "dev_timeout_sec": "3600",          # 1タスク1回あたりの上限（秒）
    "dev_workspace": "/Users/apple",    # 成果物を置く場所。Desktop/Downloads へは作らせない
    "dev_mcp_config": "/Users/apple/.mcp.json",   # 共通Visual Agent（Playwright MCP）の定義
    # 開発タスクを作ってよい Chatwork アカウント（csv）。空なら LINE と管理画面のみ。
    # 既定は管理者=鷲見慎一(7426045)。社員が勝手にコードを書かせないための制限。
    "dev_allowed_account_ids": "7426045",
    "dev_max_attempts": "3",            # 再起動復元での再実行上限
    # ---- ファイル添付送信（Stage 9）----
    # 送信のたびにLINEへ通知するか。既定は 0（送らない。2026-08-19 オーナー判断）。
    # 送信の記録は設定に関わらず sent_files テーブルに必ず残る。
    "file_send_notify_line": "0",
}


def _ensure_column(conn, table, col, decl):
    """既存 DB に不足カラムを追加（ALTER は IF NOT EXISTS 不可のため自前判定）。"""
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    if col not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")


def migrate() -> None:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    with get_conn() as conn:
        conn.executescript(schema_sql)
        # 既存 DB 向けの追加カラム（新規作成時は schema.sql 側で作成済み）
        _ensure_column(conn, "knowledge_documents", "content_hash", "TEXT")
        _ensure_column(conn, "knowledge_documents", "source_mtime", "REAL")
        # Stage 0: 進捗確認・エスカレーション用
        _ensure_column(conn, "tasks", "last_check_at", "TEXT")
        _ensure_column(conn, "tasks", "last_progress_reply", "TEXT")
        _ensure_column(conn, "tasks", "check_count", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "tasks", "escalation_stage", "INTEGER NOT NULL DEFAULT 0")
        # 定時進捗確認から個別に除外するフラグ（例: 社外待ちで確認しても意味がない場合。TASK-20260817-013）
        _ensure_column(conn, "tasks", "skip_check", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "tasks", "skip_check_reason", "TEXT")
        # Stage 0: メッセージ処理状態（冪等・クラッシュ復旧用）
        _ensure_column(conn, "messages", "process_status", "TEXT NOT NULL DEFAULT 'pending'")
        _ensure_column(conn, "messages", "process_error", "TEXT")
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)",
                (key, value),
            )


if __name__ == "__main__":
    migrate()
    print(f"migrated: {os.environ.get('CWAI_DB_PATH', 'data/app.db')}")
