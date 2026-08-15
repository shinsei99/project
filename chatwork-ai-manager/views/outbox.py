"""投稿承認（§34-35）: AIが作った投稿を確認して [送信]/[編集]/[破棄]。"""
import streamlit as st

from services import outbox as OB


def _client():
    from services.chatwork import ChatworkClient
    return ChatworkClient()


def render():
    st.header("📤 投稿承認（outbox）")
    st.caption("AIがChatworkへ投稿しようとしている内容です。確認して送信/編集/破棄できます。")

    pend = OB.pending()
    if not pend:
        st.success("確認待ちの投稿はありません。")
    for o in pend:
        with st.container(border=True):
            st.markdown(f"**宛先ルーム:** `{o['room_id']}` ／ 種別: `{o['kind']}` "
                        f"／ 関連TODO: {o['related_task_id'] or '-'}")
            if o["reason"]:
                st.caption(f"投稿理由: {o['reason']}")
            new_body = st.text_area("投稿内容", value=o["body"], key=f"body{o['id']}", height=140)
            c1, c2, c3, _ = st.columns([1, 1, 1, 3])
            if c1.button("📨 送信", key=f"send{o['id']}"):
                if new_body != o["body"]:
                    OB.update_body(o["id"], new_body)
                res = OB.send_one(_client(), o["id"])
                if res.get("ok"):
                    st.success(f"送信しました（message_id={res.get('message_id')}）")
                    st.rerun()
                else:
                    st.error(f"送信失敗: {res.get('reason')}")
            if c2.button("💾 保存のみ", key=f"save{o['id']}"):
                OB.update_body(o["id"], new_body)
                st.info("編集を保存しました（未送信）")
                st.rerun()
            if c3.button("🗑 破棄", key=f"disc{o['id']}"):
                OB.discard(o["id"])
                st.rerun()

    st.divider()
    st.subheader("最近の送信/破棄")
    for o in OB.recent(30):
        icon = {"sent": "✅", "discarded": "🗑", "failed": "⚠️"}.get(o["status"], "・")
        line = f"{icon} `{o['status']}` [{o['kind']}] room={o['room_id']} ／ {(o['body'] or '')[:60]}"
        if o["error"]:
            line += f"  ← {o['error']}"
        st.write(line)
