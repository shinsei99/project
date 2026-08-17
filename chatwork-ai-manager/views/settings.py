"""システム設定: 投稿モード・定時時刻・エスカレーション先など。"""
import streamlit as st

from services import settings as S


def render():
    st.header("⚙️ システム設定")

    st.subheader("投稿モード（§34）")
    st.caption("AIがChatworkへ投稿する際の動作。@Claudeへの直接返信は常に送信します。")
    modes = {"confirm": "確認モード（AIの自発投稿はすべて確認待ち）",
             "semi": "半自動（進捗確認・催促・レポートは自動／その他は確認）",
             "auto": "完全自動（すべて自動投稿）"}
    cur = S.post_mode()
    new = st.radio("モード", list(modes.keys()),
                   format_func=lambda k: modes[k], index=list(modes.keys()).index(cur))
    if new != cur:
        S.set_setting("post_mode", new)
        st.success(f"投稿モードを『{modes[new]}』に変更しました")
        st.rerun()

    st.divider()
    st.subheader("定時処理（§13:00/18:00/翌10:00）")
    enabled = st.checkbox("定時処理を有効にする",
                          value=S.get_setting("scheduled_jobs_enabled", "1") == "1")
    c = st.columns(3)
    t1 = c[0].text_input("昼の進捗確認", S.get_setting("progress_check_time", "13:00"))
    t2 = c[1].text_input("終業前確認", S.get_setting("closing_check_time", "18:00"))
    t3 = c[2].text_input("前日未完了確認", S.get_setting("carryover_check_time", "10:00"))
    mroom = st.text_input("期限超過エスカレーションの管理者報告先 room_id（空=発生元ルーム）",
                          S.get_setting("manager_room_id", ""))
    if st.button("定時設定を保存"):
        S.set_setting("scheduled_jobs_enabled", "1" if enabled else "0")
        S.set_setting("progress_check_time", t1)
        S.set_setting("closing_check_time", t2)
        S.set_setting("carryover_check_time", t3)
        S.set_setting("manager_room_id", mroom)
        st.success("保存しました（次回サイクルから反映）")

    st.divider()
    st.subheader("役割別モデル（枠節約）")
    st.caption("分類系（TODO抽出・定時催促）は軽量モデル、回答系（@Claude質問）は高性能モデルが推奨。")
    _models = ["haiku", "sonnet", "opus"]
    cm = st.columns(3)
    m_an = cm[0].selectbox("TODO抽出(analyzer)", _models,
                           index=_models.index(S.get_setting("model_analyzer", "haiku")) if S.get_setting("model_analyzer", "haiku") in _models else 0)
    m_sc = cm[1].selectbox("定時催促(scheduler)", _models,
                           index=_models.index(S.get_setting("model_scheduler", "haiku")) if S.get_setting("model_scheduler", "haiku") in _models else 0)
    m_qa = cm[2].selectbox("質問回答(QA)", _models,
                           index=_models.index(S.get_setting("model_qa", "sonnet")) if S.get_setting("model_qa", "sonnet") in _models else 1)
    if st.button("モデル設定を保存"):
        S.set_setting("model_analyzer", m_an)
        S.set_setting("model_scheduler", m_sc)
        S.set_setting("model_qa", m_qa)
        st.success("保存しました（次回の解析/回答から反映）")

    st.divider()
    st.subheader("放置・期限の閾値")
    c2 = st.columns(2)
    due_h = c2[0].text_input("期限間近とみなす時間(h)", S.get_setting("due_soon_hours", "24"))
    stale_d = c2[1].text_input("放置とみなす日数", S.get_setting("stale_days", "3"))
    if st.button("閾値を保存"):
        S.set_setting("due_soon_hours", due_h)
        S.set_setting("stale_days", stale_d)
        st.success("保存しました")

    st.divider()
    st.subheader("🛠 開発エージェント（アプリ制作・改修）")
    st.caption("LINE/Chatworkからの「○○アプリを作って」を、裏でClaude Codeが実装・ブラウザ検証・"
               "Gitまで行う機能。業務機能とは別系統です。")
    dev_on = st.checkbox("開発エージェントを有効にする",
                         value=S.get_setting("dev_agent_enabled", "1") == "1")
    cd = st.columns(3)
    dev_model = cd[0].selectbox(
        "モデル", _models,
        index=_models.index(S.get_setting("dev_model", "sonnet"))
        if S.get_setting("dev_model", "sonnet") in _models else 1)
    dev_to = cd[1].text_input("1回あたりの上限(秒)", S.get_setting("dev_timeout_sec", "3600"))
    dev_try = cd[2].text_input("再試行の上限(回)", S.get_setting("dev_max_attempts", "3"))
    dev_ws = st.text_input("Workspace（成果物の置き場所）", S.get_setting("dev_workspace", "/Users/apple"))
    dev_mcp = st.text_input("Visual Agent の定義ファイル（Playwright MCP）",
                            S.get_setting("dev_mcp_config", "/Users/apple/.mcp.json"))
    dev_ids = st.text_input(
        "開発を依頼してよい Chatwork account_id（カンマ区切り・空ならLINEと管理画面のみ）",
        S.get_setting("dev_allowed_account_ids", ""))
    st.caption("⚠️ 開発エージェントはWorkspace内のファイルを書き換えます。"
               "社員が誰でも依頼できる状態にしないこと。")
    if st.button("開発設定を保存"):
        S.set_setting("dev_agent_enabled", "1" if dev_on else "0")
        S.set_setting("dev_model", dev_model)
        S.set_setting("dev_timeout_sec", dev_to)
        S.set_setting("dev_max_attempts", dev_try)
        S.set_setting("dev_workspace", dev_ws)
        S.set_setting("dev_mcp_config", dev_mcp)
        S.set_setting("dev_allowed_account_ids", dev_ids)
        st.success("保存しました（次の開発タスクから反映）")

    st.divider()
    with st.expander("現在の全設定（デバッグ）"):
        st.json(S.all_settings())
