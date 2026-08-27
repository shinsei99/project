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
    # 期限リマインドの時刻。期限日の前日にこの時刻で送る（carryover_1000と同じ10:30が既定）。
    # 前日が休業日の場合は前倒しせず当日この時刻に送る（services/scheduler.py 参照）。
    "due_reminder_check_time": "10:30",
    "weekly_report_mon_time": "10:30",   # 週次棚卸し（月曜・やり残し確認）の時刻
    "weekly_report_fri_time": "18:00",   # 週次棚卸し（金曜）の時刻
    # 業務日報（Stage 10・2026-08-21 オーナー指示で 18:30 自動）
    "daily_report_enabled": "1",
    "daily_report_time": "18:30",
    "daily_report_people": "塚本,松本,森",   # 空なら監視ルームのメンバー全員
    "daily_report_room_id": "",              # 空なら manager_room_id → 監視中のgroupルーム
    "daily_report_upload": "1",              # 1でChatworkへ自動アップ（post_modeは見ない）
    # 社内メールへも同じExcelを添付して送る（2026-08-21 オーナー依頼）。SMTP設定は secrets.toml
    "daily_report_mail": "1",
    "daily_report_mail_to": "info@daikyocorp.co.jp",
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
    "model_audio_summary": "haiku",  # 音声添付の要約（Geminiで文字起こし後、Claudeで要約。TASK-20260826-004）
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
    # 開発完了と同時に、触ったアプリの launchd 常駐を入れ替える（services/dev_restart.py）。
    # 常駐は起動時のコードを抱えたままなので、再起動しないと直しても画面に出ないため。
    "dev_restart_enabled": "1",          # 0 で自動再起動をしない（報告だけ）
    "dev_restart_wait_sec": "60",        # 再起動後、応答が返るまで待つ上限（秒）
    "dev_restart_build_timeout_sec": "900",  # Next.js/Vite の npm run build の上限（秒）
    # 触らないラベル（csv）。ngrok は自作コードではなく、落とすとLINEのwebhook URLが切れる
    "dev_restart_exclude": "com.shinsei.chatwork-ai-manager-ngrok",
    # ---- 業務月報（TASK-20260825-001。TASK-20260826-002でLINE起点に変更）----
    # 入力源・トリガー＝オーナーがLINEで「月報開始」〜「月報終了」の間に送った内容。
    # Chatworkの資料アップロードでは今後いっさい作らない（services/scheduler.py参照）。
    "monthly_report_enabled": "1",
    "monthly_report_room_id": "",            # Excelのアップ先（空なら daily_report_room_id → manager_room_id → 監視中groupルーム）
    "monthly_report_upload": "1",            # 1でアップ先ルームへExcelを自動アップ
    # 社内メールへも同じExcelを添付して送る（TASK-20260825-002・日報と同じ挙動に揃える）
    "monthly_report_mail": "1",
    "monthly_report_mail_to": "",            # 空なら daily_report_mail_to を使う
    "model_monthly_report": "sonnet",
    # LINEの材料受付セッションを開いたまま放置された場合、何分後に自動で締め切るか（TASK-20260826-002）。
    # 締め切らないと、忘れたセッションが以降のLINE質問応答を乗っ取り続けてしまう。
    "monthly_report_line_session_timeout_min": "180",
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
        # 進捗報告があった日時（last_check_atとは別。定時確認の重複催促防止に使う。TASK-20260824-002）
        _ensure_column(conn, "tasks", "last_progress_at", "TEXT")
        _ensure_column(conn, "tasks", "check_count", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "tasks", "escalation_stage", "INTEGER NOT NULL DEFAULT 0")
        # 定時進捗確認から個別に除外するフラグ（例: 社外待ちで確認しても意味がない場合。TASK-20260817-013）
        _ensure_column(conn, "tasks", "skip_check", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "tasks", "skip_check_reason", "TEXT")
        # Stage 0: メッセージ処理状態（冪等・クラッシュ復旧用）
        _ensure_column(conn, "messages", "process_status", "TEXT NOT NULL DEFAULT 'pending'")
        _ensure_column(conn, "messages", "process_error", "TEXT")
        # 物件×担当者マスタ（管理物件台帳の「担当」列。TASK-20260826-003）
        _ensure_column(conn, "properties", "assignee_name", "TEXT")
        # Chatwork画像の検索用（物件名/ルーム名。TASK-20260827-002）
        _ensure_column(conn, "chatwork_images", "room_name", "TEXT")
        _ensure_column(conn, "chatwork_images", "property_name", "TEXT")
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)",
                (key, value),
            )
        # due_reminderの実行時刻を旧既定09:00→新既定10:30へ（TASK-20260824-001）。
        # 手動でカスタマイズ済み（09:00以外）の値は上書きしない。
        conn.execute(
            "UPDATE settings SET value='10:30' WHERE key='due_reminder_check_time' AND value='09:00'"
        )


if __name__ == "__main__":
    migrate()
    print(f"migrated: {os.environ.get('CWAI_DB_PATH', 'data/app.db')}")
