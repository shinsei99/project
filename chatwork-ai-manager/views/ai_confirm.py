"""AI確認待ち（§11）: AIが自信を持てなかったTODO候補を、人が [登録]/[無視] する。"""
import streamlit as st

from db.connection import query_one
from services import tasks as T


def render():
    st.header("❓ AI確認待ち")
    st.caption("AIがTODOか判断できなかった候補です。登録すると未着手TODOになります。無視するとキャンセル扱いになります。")

    rows = T.list_tasks(status=T.STATUS_AI_CONFIRM)
    if not rows:
        st.success("確認待ちの候補はありません。")
        return

    for t in rows:
        with st.container(border=True):
            st.markdown(f"**{t['content']}**")
            st.caption(f"担当候補: {t['assignee_name'] or '不明'} ／ 期限候補: {t['due_date'] or '未確定'}"
                       f"（{t['due_raw'] or ''}） ／ 確信度: {t['ai_confidence'] or '-'}")
            st.write(f"AI判断理由: {t['ai_reason'] or '-'}")
            if t["source_message_id"]:
                m = query_one("SELECT * FROM messages WHERE message_id=?", (t["source_message_id"],))
                if m:
                    st.info(f"元発言 [{m['account_name'] or m['account_id']}]: {m['body']}")
            c1, c2, _ = st.columns([1, 1, 4])
            if c1.button("✅ 登録", key=f"reg{t['id']}"):
                T.update_status(t["id"], T.STATUS_TODO, note="人が確認しTODO登録")
                st.rerun()
            if c2.button("🗑 無視", key=f"ign{t['id']}"):
                T.update_status(t["id"], T.STATUS_CANCEL, note="人が確認し無視")
                st.rerun()
