"""システム設定: 投稿モード・定時時刻・エスカレーション先など。"""
import streamlit as st

from services import settings as S
from services import daily_report as DR


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
    st.subheader("定時処理（§18:00/翌10:30）")
    enabled = st.checkbox("定時処理を有効にする",
                          value=S.get_setting("scheduled_jobs_enabled", "1") == "1")
    c = st.columns(2)
    t2 = c[0].text_input("終業前確認", S.get_setting("closing_check_time", "18:00"))
    t3 = c[1].text_input("前日未完了確認", S.get_setting("carryover_check_time", "10:30"))
    mroom = st.text_input("期限超過エスカレーション／週次棚卸しの報告先 room_id（空=発生元ルーム。room_id未設定TODOの受け皿）",
                          S.get_setting("manager_room_id", ""))
    if st.button("定時設定を保存"):
        S.set_setting("scheduled_jobs_enabled", "1" if enabled else "0")
        S.set_setting("closing_check_time", t2)
        S.set_setting("carryover_check_time", t3)
        S.set_setting("manager_room_id", mroom)
        st.success("保存しました（次回サイクルから反映）")

    st.divider()
    st.subheader("業務記録リマインド（終業前確認に同居・2026-08-27追加）")
    st.caption("その日、本人がChatworkに投稿した発言数（業務日報が本文生成に使う数え方と同じ）が"
               "既定3件未満の社員へ、18:30の業務日報自動生成より前に入力・報告を促す。")
    rec_enabled = st.checkbox("業務記録リマインドを有効にする",
                              value=S.get_setting("daily_record_reminder_enabled", "1") == "1")
    rec_min = st.number_input("最低件数の目安", min_value=1, max_value=20,
                              value=int(S.get_setting("daily_record_min_count", "3") or 3))
    if st.button("業務記録リマインド設定を保存"):
        S.set_setting("daily_record_reminder_enabled", "1" if rec_enabled else "0")
        S.set_setting("daily_record_min_count", str(int(rec_min)))
        st.success("保存しました（次回サイクルから反映）")

    st.caption("催促の対象者と、18:30に自動生成する日報の対象者は別々に設定できる"
               "（TASK-20260828-005で分離。空にすると監視ルームの全員が対象）。")
    roster_names = [p["name"] for p in DR.roster()]
    cur_reminder = [n.strip() for n in
                    (S.get_setting("daily_record_reminder_people", "") or "").split(",") if n.strip()]
    cur_report = [n.strip() for n in
                 (S.get_setting("daily_report_people", "") or "").split(",") if n.strip()]
    cp = st.columns(2)
    new_reminder = cp[0].multiselect("業務記録リマインドの対象者", roster_names,
                                     default=[n for n in cur_reminder if n in roster_names])
    new_report = cp[1].multiselect("18:30 業務日報の対象者", roster_names,
                                   default=[n for n in cur_report if n in roster_names])
    if st.button("対象者を保存"):
        S.set_setting("daily_record_reminder_people", ",".join(new_reminder))
        S.set_setting("daily_report_people", ",".join(new_report))
        st.success("保存しました（次回サイクルから反映）")

    st.divider()
    st.subheader("期限リマインド・週次棚卸し（2026-08-17追加・2026-08-24タイミング変更）")
    st.caption("期限リマインドは、期限日の前日にこの時刻で送る事前リマインド（既定はcarryover_1000と同じ10:30）。"
               "前日が休業日（年間休暇スケジュールのオレンジ）の場合は前倒しせず当日この時刻に送る。"
               "週次棚卸しは、金曜18時・月曜10時30分に絞り込みなしで未完了TODOを全件まとめて報告する機能。")
    tr = st.text_input("期限リマインドの時刻", S.get_setting("due_reminder_check_time", "10:30"))
    cw = st.columns(2)
    tw_mon = cw[0].text_input("週次棚卸し（月曜）の時刻", S.get_setting("weekly_report_mon_time", "10:30"))
    tw_fri = cw[1].text_input("週次棚卸し（金曜）の時刻", S.get_setting("weekly_report_fri_time", "18:00"))
    if st.button("リマインド・週次棚卸し設定を保存"):
        S.set_setting("due_reminder_check_time", tr)
        S.set_setting("weekly_report_mon_time", tw_mon)
        S.set_setting("weekly_report_fri_time", tw_fri)
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
    dev_rs = st.checkbox(
        "開発完了と同時に、触ったアプリの常駐（launchd）を自動で再起動する",
        value=S.get_setting("dev_restart_enabled", "1") == "1")
    st.caption("常駐は起動時のコードを抱えたままなので、再起動しないと直しても画面に出ません。"
               "対象は project_dir と、このタスクのコミットが触ったフォルダだけ。"
               "定時ジョブ（note投稿など）と未ロードのラベルは触りません。"
               "Next.js/Vite は再起動の前に `npm run build` も回します。")
    cr = st.columns(2)
    dev_rw = cr[0].text_input("再起動後に応答を待つ上限(秒)", S.get_setting("dev_restart_wait_sec", "60"))
    dev_rx = cr[1].text_input("再起動しないラベル（カンマ区切り）",
                              S.get_setting("dev_restart_exclude",
                                            "com.shinsei.chatwork-ai-manager-ngrok"))
    if st.button("開発設定を保存"):
        S.set_setting("dev_agent_enabled", "1" if dev_on else "0")
        S.set_setting("dev_model", dev_model)
        S.set_setting("dev_timeout_sec", dev_to)
        S.set_setting("dev_max_attempts", dev_try)
        S.set_setting("dev_workspace", dev_ws)
        S.set_setting("dev_mcp_config", dev_mcp)
        S.set_setting("dev_allowed_account_ids", dev_ids)
        S.set_setting("dev_restart_enabled", "1" if dev_rs else "0")
        S.set_setting("dev_restart_wait_sec", dev_rw)
        S.set_setting("dev_restart_exclude", dev_rx)
        st.success("保存しました（次の開発タスクから反映）")

    st.divider()
    with st.expander("現在の全設定（デバッグ）"):
        st.json(S.all_settings())
