"""🛠 開発タスク画面（DEVELOPMENT Agent）。

- 進行中/過去の開発タスクを見る
- 開発エージェントからの質問（WAITING_USER）にここから答えて再開させる
- 管理画面から直接 開発タスクを投入する（LINE/Chatworkを経由せずテストできる）
"""
import os

import streamlit as st

from services import dev_runner
from services import dev_tasks as DT
from services import settings

_BADGE = {
    DT.RECEIVED: "🟡 実行待ち", DT.PLANNING: "🔵 計画中", DT.RUNNING: "🟢 実行中",
    DT.WAITING_USER: "🟠 回答待ち", DT.TESTING: "🧪 検証中", DT.FAILED: "🔴 失敗",
    DT.COMPLETED: "✅ 完了", DT.CANCELLED: "⚫ 中止",
}


def _new_task_form():
    with st.expander("＋ 開発タスクを投入（管理画面から直接）", expanded=False):
        req = st.text_area("依頼内容", placeholder="例: 簡単なTODOアプリを作って",
                           height=100, key="dev_new_req")
        col1, col2 = st.columns(2)
        kind = col1.selectbox("種別", ["(自動判定)"] + list(DT.KINDS), key="dev_new_kind")
        proj = col2.text_input("対象プロジェクト（既存アプリを直す場合のみ）",
                               placeholder="例: flyer-creator", key="dev_new_proj")
        if st.button("開発タスクを作成", type="primary", key="dev_new_go"):
            if not req.strip():
                st.error("依頼内容を入力してください。")
            else:
                ws = settings.get_setting("dev_workspace", "/Users/apple")
                t = DT.create(
                    request=req.strip(), kind=None if kind.startswith("(") else kind,
                    channel="admin", requester="管理画面", workspace=ws,
                    project_dir=(os.path.join(ws, proj.strip()) if proj.strip() else None),
                )
                st.success(f"{t['task_id']} を受け付けました（workerが順次実行します）。")
                st.rerun()


def render():
    st.title("🛠 開発タスク（DEVELOPMENT Agent）")
    st.caption("アプリの制作・改修をAIが実行します。業務TODO（社員の仕事）とは別系統です。")

    enabled = settings.get_setting("dev_agent_enabled", "1") == "1"
    cols = st.columns([2, 2, 3])
    cols[0].metric("実行中", dev_runner.current_task_id() or "—")
    cols[1].metric("開発エージェント", "稼働" if enabled else "停止中")
    cols[2].caption(f"Workspace: `{settings.get_setting('dev_workspace', '/Users/apple')}`  \n"
                    f"Visual Agent: `{settings.get_setting('dev_mcp_config', '~/.mcp.json')}`")
    if not enabled:
        st.warning("開発エージェントは停止中です（システム設定 dev_agent_enabled）。"
                   "受付はできますが実行されません。")

    # QA（調べて答える担当）がコードを触ったら、ここに出す。
    # Bash がある以上プロンプトの禁止は強制力が無いので、破られたら分かるようにしてある。
    from db.connection import query as _q
    guards = _q("SELECT id, created_at, prompt, raw_output FROM ai_analysis_logs "
                "WHERE kind='guard' ORDER BY id DESC LIMIT 5")
    if guards:
        with st.expander(f"⚠️ QAエージェントがファイルを変更した記録（{len(guards)}件）", expanded=True):
            st.caption("業務QAは調べて答える担当で、改修は開発エージェントの仕事です。"
                       "ここに出ている場合は、意図しない書き換えが起きていないか確認してください。")
            for g in guards:
                st.markdown(f"**{g['created_at']}** — 質問: {(g['prompt'] or '')[:80]}")
                st.code(g["raw_output"] or "", language=None)

    _new_task_form()

    # --- 回答待ち（最優先で見せる） ---
    waiting = DT.list_tasks(status=DT.WAITING_USER, limit=20)
    if waiting:
        st.subheader("🟠 あなたの回答待ち")
        for t in waiting:
            with st.container(border=True):
                st.markdown(f"**{t['task_id']}** — {t['title'] or ''}")
                st.code(t["question"] or "(質問なし)", language=None)
                ans = st.text_input("回答", key=f"ans_{t['task_id']}")
                c1, c2 = st.columns([1, 1])
                if c1.button("回答して再開", key=f"go_{t['task_id']}", type="primary"):
                    if ans.strip():
                        DT.answer(t["task_id"], ans.strip())
                        st.success("再開します。")
                        st.rerun()
                    else:
                        st.error("回答を入力してください。")
                if c2.button("中止", key=f"cancel_{t['task_id']}"):
                    DT.cancel(t["task_id"], "管理画面から中止")
                    st.rerun()

    # --- 一覧 ---
    st.subheader("一覧")
    status = st.selectbox("状態で絞り込み", ["(すべて)"] + list(DT.STATUSES), key="dev_filter")
    rows = DT.list_tasks(status=None if status.startswith("(") else status, limit=50)
    if not rows:
        st.info("開発タスクはまだありません。")
        return
    for t in rows:
        with st.expander(f"{_BADGE.get(t['status'], t['status'])}  {t['task_id']}  "
                         f"{t['title'] or ''}", expanded=False):
            st.write(f"**依頼**: {t['request']}")
            meta = (f"種別: {t['kind'] or '—'} / 入口: {t['channel']} / 依頼者: {t['requester'] or '—'} / "
                    f"実行回数: {t['attempts']} / 作成: {t['created_at']} / 更新: {t['updated_at']}")
            st.caption(meta)
            if t["project_dir"]:
                st.caption(f"対象: `{t['project_dir']}`")
            if t["result"]:
                st.success(t["result"])
            if t["error"]:
                st.error(t["error"])
            if t["log_path"] and os.path.exists(t["log_path"]):
                if st.button("実行ログを見る（末尾200行）", key=f"log_{t['task_id']}"):
                    with open(t["log_path"], "r", encoding="utf-8", errors="replace") as f:
                        st.code("".join(f.readlines()[-200:]), language=None)
            ev = DT.events(t["task_id"], limit=30)
            if ev:
                st.markdown("**経過**")
                for e in ev:
                    st.caption(f"{e['created_at']}  [{e['event_type']}] {(e['note'] or '')[:300]}")
            if t["status"] not in DT.DONE_STATUSES:
                if st.button("中止", key=f"c2_{t['task_id']}"):
                    DT.cancel(t["task_id"], "管理画面から中止")
                    st.rerun()
