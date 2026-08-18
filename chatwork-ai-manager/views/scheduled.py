"""定時処理ログ: 18:00/翌10:00 の実行履歴（scheduled_runs）と直近の通知。"""
import json

import streamlit as st

from db.connection import query
from services import scheduler, settings


def render():
    st.header("⏰ 定時処理ログ")
    enabled = settings.get_setting("scheduled_jobs_enabled", "1") == "1"
    st.caption(f"定時処理: {'🟢 有効' if enabled else '🔴 停止中'}　"
               f"（設定で変更可）")

    labels = {"closing_1800": "終業前確認",
              "carryover_1000": "前日未完了確認", "due_reminder": "期限リマインド",
              "weekly_report_mon": "週次棚卸し(月)", "weekly_report_fri": "週次棚卸し(金)"}
    cols = st.columns(4)
    for i, (job, (time_key, default, _kind, _stage, _label)) in enumerate(scheduler.JOBS.items()):
        cols[i % 4].metric(labels.get(job, job), settings.get_setting(time_key, default))
    st.caption("週次棚卸し（絞り込みなしの全件報告）")
    cw = st.columns(4)
    for i, (job, (_weekday, time_key, default, _label)) in enumerate(scheduler.WEEKLY_JOBS.items()):
        cw[i % 4].metric(labels.get(job, job), settings.get_setting(time_key, default))

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
                if d.get("error"):
                    summary = "⚠️ " + d["error"]
                elif "candidates" in d:
                    summary = f"候補{d.get('candidates','-')}件 / 連絡{d.get('contacted','-')}件"
                elif "rooms" in d:
                    summary = f"未完了{d.get('tasks','-')}件 / {d.get('rooms','-')}ルームへ報告"
                else:
                    summary = json.dumps(d, ensure_ascii=False)[:80]
            except Exception:
                summary = result[:80]
        st.write(f"`{r['run_date']}` **{labels.get(r['job_type'], r['job_type'])}** "
                 f"（{r['ran_at']}）… {summary}")

    st.divider()
    st.subheader("AIが検出した質問・通知（notifications）")
    for n in query("SELECT * FROM notifications ORDER BY id DESC LIMIT 20"):
        st.write(f"`{n['created_at']}` [{n['type']}] room={n['room_id']} {n['payload'] or ''}")
