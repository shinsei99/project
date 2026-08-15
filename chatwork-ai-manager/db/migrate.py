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
    "progress_check_time": "13:00",  # 昼の進捗確認
    "closing_check_time": "18:00",   # 終業前の未完了確認
    "carryover_check_time": "10:00", # 翌日の前日未完了・期限超過確認
    "scheduled_jobs_enabled": "1",   # 0で定時処理を停止
    "manager_room_id": "",           # 期限超過エスカレーションの管理者報告先（空なら発生元ルーム）
    # 日次ナレッジ増分リフレッシュ（Stage 5）
    "knowledge_refresh_enabled": "1",
    "knowledge_refresh_time": "07:00",
    # 役割別モデル（枠節約）: 分類系=軽量haiku / 回答系=sonnet
    "model_analyzer": "haiku",   # TODO抽出・進捗・完了判定（分類タスク）
    "model_scheduler": "haiku",  # 定時の催促文生成（定型）
    "model_qa": "sonnet",        # @Claude質問回答・エージェント（多段推論）
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
