"""ダッシュボード: 本日期限・期限超過・状態別件数・担当者別（§33）。"""
import datetime

import streamlit as st

from db.connection import query
from services import tasks as T


def render():
    st.header("📊 ダッシュボード")
    counts = T.counts_by_status()
    today = datetime.date.today().isoformat()

    total_open = sum(counts.get(s, 0) for s in T.OPEN_STATUSES)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("未着手", counts.get(T.STATUS_TODO, 0))
    c2.metric("進行中", counts.get(T.STATUS_DOING, 0))
    c3.metric("確認待ち", counts.get(T.STATUS_WAITING, 0))
    c4.metric("AI確認待ち", counts.get(T.STATUS_AI_CONFIRM, 0))
    c5.metric("完了", counts.get(T.STATUS_DONE, 0))

    st.divider()
    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("🔴 期限超過")
        overdue = query(
            "SELECT * FROM tasks WHERE due_date IS NOT NULL AND due_date < ? "
            "AND status IN ({}) ORDER BY due_date".format(
                ",".join("?" * len(T.OPEN_STATUSES))),
            (today, *T.OPEN_STATUSES),
        )
        if overdue:
            for t in overdue:
                st.error(f"**{t['content']}** ／ 担当: {t['assignee_name'] or '?'} ／ 期限: {t['due_date']}")
        else:
            st.caption("なし")

    with col_r:
        st.subheader("🟡 本日期限")
        due_today = query(
            "SELECT * FROM tasks WHERE due_date = ? AND status IN ({}) ORDER BY id".format(
                ",".join("?" * len(T.OPEN_STATUSES))),
            (today, *T.OPEN_STATUSES),
        )
        if due_today:
            for t in due_today:
                st.warning(f"**{t['content']}** ／ 担当: {t['assignee_name'] or '?'}")
        else:
            st.caption("なし")

    st.divider()
    st.subheader("👥 担当者別（未完了）")
    ph = ",".join("?" * len(T.OPEN_STATUSES))
    rows = query(
        f"SELECT COALESCE(assignee_name,'(未割当)') AS who, COUNT(*) AS n "
        f"FROM tasks WHERE status IN ({ph}) GROUP BY who ORDER BY n DESC",
        tuple(T.OPEN_STATUSES),
    )
    if rows:
        st.dataframe(
            {"担当者": [r["who"] for r in rows], "未完了件数": [r["n"] for r in rows]},
            hide_index=True, use_container_width=True,
        )
    else:
        st.caption("未完了のTODOはありません。")

    st.caption(f"未完了合計: {total_open} 件")
