"""AI業務マネージャー 管理画面（Streamlit・port 8540）。

M1: ダッシュボード / TODO / AI確認待ち / ルーム設定 / 解析履歴。
M2以降で 期限超過・漏れ候補・放置・outbox承認・ナレッジ管理 等を追加する。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st  # noqa: E402

from db.migrate import migrate  # noqa: E402
from services import config  # noqa: E402

st.set_page_config(page_title="AI業務マネージャー", page_icon="🤖", layout="wide")
migrate()


def _check_password() -> bool:
    """簡易パスワード認証。secrets.toml の dashboard_password と照合。"""
    expected = config.get("dashboard_password")
    if not expected:
        st.warning("dashboard_password が未設定です。.streamlit/secrets.toml を設定してください。")
        return True  # 未設定時は開発利便のため素通り（本番は必ず設定）
    if st.session_state.get("authed"):
        return True
    st.title("🤖 AI業務マネージャー")
    pw = st.text_input("パスワード", type="password")
    if st.button("ログイン"):
        if pw == str(expected):
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("パスワードが違います。")
    return False


if not _check_password():
    st.stop()

PAGES = {
    "📊 ダッシュボード": "dashboard",
    "✅ TODO一覧": "todos",
    "📝 業務日報": "daily_report",
    "🛠 開発タスク": "dev_tasks",
    "🗺 物件マップ": "property_map",
    "❓ AI確認待ち": "ai_confirm",
    "📤 投稿承認（outbox）": "outbox",
    "⏰ 定時処理ログ": "scheduled",
    "📚 ナレッジ管理": "knowledge",
    "💬 ルーム設定": "rooms",
    "🧠 AI解析履歴": "analysis_log",
    "⚙️ システム設定": "settings",
}

st.sidebar.title("🤖 AI業務マネージャー")
ai_name = None
try:
    from services.settings import get_state
    ai_name = get_state("ai_account_name")
except Exception:
    pass
if ai_name:
    st.sidebar.caption(f"AIアカウント: {ai_name}")
st.sidebar.caption("Chatworkの会話から業務を自動抽出")

choice = st.sidebar.radio("メニュー", list(PAGES.keys()), label_visibility="collapsed")

st.sidebar.divider()
from services.settings import post_mode  # noqa: E402
_mode_label = {"confirm": "確認モード（自動投稿しない）", "semi": "半自動", "auto": "完全自動"}
st.sidebar.info(f"投稿モード: **{_mode_label.get(post_mode(), post_mode())}**")

page = PAGES[choice]
from views import (  # noqa: E402
    ai_confirm, analysis_log, daily_report, dashboard, dev_tasks, knowledge, outbox,
    property_map, rooms, scheduled, settings as settings_view, todos,
)

_RENDER = {
    "dashboard": dashboard.render, "todos": todos.render, "ai_confirm": ai_confirm.render,
    "daily_report": daily_report.render, "dev_tasks": dev_tasks.render, "property_map": property_map.render,
    "outbox": outbox.render, "scheduled": scheduled.render, "knowledge": knowledge.render,
    "rooms": rooms.render, "analysis_log": analysis_log.render, "settings": settings_view.render,
}
_RENDER[page]()
