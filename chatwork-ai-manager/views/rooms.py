"""ルーム設定（§32-10）: 参加ルーム一覧・監視ON/OFF・手動同期。"""
import streamlit as st

from db.connection import get_conn, query
from services import config


def _client():
    from services.chatwork import ChatworkClient
    return ChatworkClient()


def render():
    st.header("💬 ルーム設定")

    if not config.get("chatwork_api_token"):
        st.warning("Chatwork API トークンが未設定です。`.streamlit/secrets.toml` に "
                   "`chatwork_api_token` を設定してください。")
        return

    col1, col2 = st.columns(2)
    if col1.button("🔄 ルーム一覧を同期"):
        try:
            from services import sync
            client = _client()
            n = sync.sync_rooms(client)
            aid = sync.get_ai_account_id(client)
            st.success(f"{n} ルームを同期しました（AIアカウント account_id={aid}）")
        except Exception as e:
            st.error(f"同期失敗: {e}")

    if col2.button("▶ 監視ルームを今すぐ解析（1サイクル）"):
        try:
            from services import sync
            client = _client()
            summary = sync.run_cycle(client)
            st.success(f"完了: {summary}")
        except Exception as e:
            st.error(f"解析失敗: {e}")

    st.divider()
    rooms = query("SELECT * FROM rooms ORDER BY monitored DESC, room_id")
    if not rooms:
        st.info("まず「ルーム一覧を同期」を押してください。")
        return

    st.caption("チェックを入れたルームだけがAIの解析対象になります。テストは自分のマイチャット（type=my）が手軽です。")
    for r in rooms:
        c1, c2, c3 = st.columns([1, 4, 2])
        checked = c1.checkbox("", value=bool(r["monitored"]), key=f"mon{r['room_id']}",
                              label_visibility="collapsed")
        c2.write(f"**{r['name'] or '(無題)'}**  \n`room_id={r['room_id']}` type={r['type']}")
        c3.caption(f"最終取得ID: {r['last_message_id'] or '-'}")
        if checked != bool(r["monitored"]):
            with get_conn() as conn:
                conn.execute("UPDATE rooms SET monitored=? WHERE room_id=?",
                             (1 if checked else 0, r["room_id"]))
            if checked:
                try:
                    from services import sync
                    sync.sync_members(_client(), r["room_id"])
                except Exception:
                    pass
            st.rerun()
