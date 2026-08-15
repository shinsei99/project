"""TODO一覧＋詳細（§37,39,40 追跡・根拠・信頼度表示）。"""
import streamlit as st

from db.connection import query_one
from services import tasks as T


def _detail(task_id: int):
    t = T.get_task(task_id)
    if not t:
        st.error("TODOが見つかりません。")
        return
    if st.button("← 一覧へ戻る"):
        st.session_state.pop("sel_task", None)
        st.rerun()

    st.subheader(f"#{t['id']}  {t['content']}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("状態", t["status"])
    c2.metric("担当", t["assignee_name"] or "?")
    c3.metric("期限", t["due_date"] or "未確定")
    c4.metric("優先度", t["priority"] or "-")

    with st.form("edit"):
        st.markdown("**編集**")
        new_status = st.selectbox("状態", T.ALL_STATUSES, index=T.ALL_STATUSES.index(t["status"]) if t["status"] in T.ALL_STATUSES else 0)
        new_progress = st.slider("進捗率", 0, 100, int(t["progress"] or 0))
        col = st.columns(2)
        if col[0].form_submit_button("状態を更新"):
            T.update_status(t["id"], new_status, note="管理画面から手動更新", progress=new_progress)
            st.success("更新しました")
            st.rerun()

    st.divider()
    st.markdown("**AI判断（透明性・§39,40）**")
    st.write(f"- 判断理由: {t['ai_reason'] or '-'}")
    st.write(f"- 全体の確信度: {t['ai_confidence'] or '-'}")
    st.write(f"- 担当={t['conf_assignee'] or '-'} / 期限={t['conf_due'] or '-'} / "
             f"完了条件={t['conf_done'] or '-'} / 案件={t['conf_project'] or '-'}")
    if t["is_speculative"]:
        st.warning("⚠ これはAIの推測（事実未確認）です。")
    if t["due_raw"]:
        st.caption(f"元の期限表現: 「{t['due_raw']}」")

    # 生成元メッセージ（§37）
    if t["source_message_id"]:
        m = query_one("SELECT * FROM messages WHERE message_id=?", (t["source_message_id"],))
        st.markdown("**生成元メッセージ**")
        if m:
            st.info(f"[{m['account_name'] or m['account_id']}] {m['body']}")
        else:
            st.caption(f"message_id={t['source_message_id']}（本文は取得範囲外）")

    st.markdown("**履歴（task_events）**")
    for ev in T.get_events(t["id"]):
        line = f"- {ev['created_at']}  **{ev['event_type']}**"
        if ev["from_status"] or ev["to_status"]:
            line += f"  {ev['from_status'] or ''}→{ev['to_status'] or ''}"
        if ev["note"]:
            line += f"  ／ {ev['note']}"
        st.write(line)


def render():
    if st.session_state.get("sel_task"):
        _detail(st.session_state["sel_task"])
        return

    st.header("✅ TODO一覧")
    status_filter = st.selectbox("状態で絞り込み", ["（未完了のみ）", "（すべて）"] + T.ALL_STATUSES)

    if status_filter == "（すべて）":
        rows = T.list_tasks()
    elif status_filter == "（未完了のみ）":
        rows = [r for r in T.list_tasks() if r["status"] in T.OPEN_STATUSES]
    else:
        rows = T.list_tasks(status=status_filter)

    if not rows:
        st.info("該当するTODOはありません。Chatworkの監視ルームで会話が発生し、workerが解析すると自動で追加されます。")
        return

    for t in rows:
        cols = st.columns([5, 2, 2, 1.5, 1.5])
        cols[0].write(f"**{t['content']}**")
        cols[1].write(f"👤 {t['assignee_name'] or '?'}")
        cols[2].write(f"📅 {t['due_date'] or '未確定'}")
        cols[3].write(f"`{t['status']}`")
        if cols[4].button("詳細", key=f"d{t['id']}"):
            st.session_state["sel_task"] = t["id"]
            st.rerun()
        st.divider()
