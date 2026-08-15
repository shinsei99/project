"""定時処理ログ: 13:00/18:00/翌10:00 の実行履歴（scheduled_runs）と直近の通知。"""
import json

import streamlit as st

from db.connection import query
from services import scheduler, settings


def render():
    st.header("⏰ 定時処理ログ")
    enabled = settings.get_setting("scheduled_jobs_enabled", "1") == "1"
    st.caption(f"定時処理: {'🟢 有効' if enabled else '🔴 停止中'}　"
               f"（設定で変更可）")

    cols = st.columns(3)
    labels = {"progress_1300": "昼の進捗確認", "closing_1800": "終業前確認",
              "carryover_1000": "前日未完了確認"}
    for i, (job, (_k, default, _kind, _stage, _label)) in enumerate(scheduler.JOBS.items()):
        t = settings.get_setting({"progress_1300": "progress_check_time",
                                  "closing_1800": "closing_check_time",
                                  "carryover_1000": "carryover_check_time"}[job], default)
        cols[i % 3].metric(labels.get(job, job), t)

    st.divider()
    st.subheader("実行履歴（scheduled_runs）")
    rows = query("SELECT * FROM scheduled_runs ORDER BY id DESC LIMIT 60")
    if not rows:
        st.info("まだ定時処理の実行履歴はありません。")
    for r in rows:
        result = r["result"]
        summary = ""
        if result:
            try:
                d = json.loads(result)
                summary = f"候補{d.get('candidates','-')}件 / 連絡{d.get('contacted','-')}件"
                if d.get("error"):
                    summary = "⚠️ " + d["error"]
            except Exception:
                summary = result[:80]
        st.write(f"`{r['run_date']}` **{labels.get(r['job_type'], r['job_type'])}** "
                 f"（{r['ran_at']}）… {summary}")

    st.divider()
    st.subheader("AIが検出した質問・通知（notifications）")
    for n in query("SELECT * FROM notifications ORDER BY id DESC LIMIT 20"):
        st.write(f"`{n['created_at']}` [{n['type']}] room={n['room_id']} {n['payload'] or ''}")
