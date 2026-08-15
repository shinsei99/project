"""AI解析履歴（§41）: いつ・どのメッセージを解析し・何を出力したかを追跡。"""
import json

import streamlit as st

from db.connection import query


def render():
    st.header("🧠 AI解析履歴")
    st.caption("「なぜこのTODOが作られたか」を後から追跡できます。")

    rows = query(
        "SELECT * FROM ai_analysis_logs ORDER BY id DESC LIMIT 100"
    )
    if not rows:
        st.info("まだ解析ログはありません。")
        return

    for r in rows:
        title = f"{r['created_at']} ／ room={r['room_id']} ／ {r['kind']}"
        if r["error"]:
            title = "⚠ " + title
        with st.expander(title):
            if r["error"]:
                st.error(r["error"])
            if r["message_ids"]:
                st.caption(f"対象メッセージ: {r['message_ids']}")
            if r["duration_ms"]:
                st.caption(f"所要: {r['duration_ms']} ms / model={r['model']}")
            if r["parsed"]:
                try:
                    st.json(json.loads(r["parsed"]))
                except Exception:
                    st.code(r["parsed"])
            if r["raw_output"]:
                with st.popover("生出力"):
                    st.code(r["raw_output"])
