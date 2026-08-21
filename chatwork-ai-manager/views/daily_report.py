"""業務日報（Stage 10）。その日の会話＋TODOから社員1人ずつの日報をAIが作る。

Chatwork へは**この画面からは送らない**。送るときは「承認待ちへ積む」→
📤 投稿承認（outbox）で人が承認する（kind=daily_report は自動送信されない）。
"""
import datetime
import json
import os
import tempfile

import streamlit as st

from services import daily_report as DR
from services import daily_report_export as EX
from services import outbox
from services.chatwork import mention


def _built(builder, date_str: str, rows, ext: str) -> bytes:
    """docx/xlsx はファイルにしか書けないので、一時ファイル経由でバイト列にする。"""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, f"report.{ext}")
        builder(date_str, rows, path)
        with open(path, "rb") as f:
            return f.read()


def _local(ts: str) -> str:
    """DBは datetime('now')＝UTC で入るので、表示だけ日本時間に直す。"""
    try:
        dt = datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        return (dt + datetime.timedelta(hours=9)).strftime("%m/%d %H:%M")
    except (TypeError, ValueError):
        return ts or "-"


def _stats_line(row) -> str:
    s = json.loads(row["stats"] or "{}")
    return (f"発言 {s.get('messages_own', 0)}件 ／ 本日動いたTODO {s.get('tasks_moved', 0)}件"
            f"（うち完了 {s.get('tasks_done_today', 0)}件）／ 未完了 {s.get('tasks_open', 0)}件")


def render():
    st.title("📝 業務日報")
    st.caption("その日のChatworkの会話とTODOの動きから、社員1人ずつの日報をAIが作ります。"
               "会話に無いことは書かせない方針です（本人の発言は account_id で判定）。")

    date = st.date_input("対象日", value=datetime.date.today())
    date_str = date.isoformat()

    people = DR.roster()
    if not people:
        st.warning("監視ルームのメンバーが取得できていません。「💬 ルーム設定」で同期してください。")
        return
    names = [p["name"] for p in people]
    by_name = {p["name"]: p for p in people}

    default = [n for n in ("塚本", "松本", "森") if n in names] or names
    targets = st.multiselect("対象者", names, default=default)

    msgs = DR.day_messages(date_str)
    c1, c2, c3 = st.columns([2, 2, 3])
    c1.metric("その日の会話", f"{len(msgs)}件")
    if c2.button("🔄 Chatworkから最新を取得", help="読むだけ。投稿はしません（取れるのは直近分のみ）"):
        res = DR.sync_from_chatwork()
        if res["error"]:
            st.error(f"取得に失敗: {res['error']}")
        else:
            st.success(f"新規 {res['new']}件を取り込みました。")
            st.rerun()
    if len(msgs) == 0:
        c3.info("この日の会話がDBにありません。日報は「記録なし」になります。")

    if st.button("🧠 選んだ人の日報を作成", type="primary", disabled=not targets):
        bar = st.progress(0.0)
        for i, name in enumerate(targets):
            p = by_name[name]
            with st.spinner(f"{name} さんの日報を作成中…"):
                try:
                    DR.generate(date_str, name, account_id=p["account_id"])
                except Exception as e:
                    st.error(f"{name}: {type(e).__name__}: {e}")
            bar.progress((i + 1) / len(targets))
        st.rerun()

    # 並び順は「対象者」で選んだ順（既定は 塚本・松本・森）。書き出しもこの順になる。
    rank = {n: i for i, n in enumerate(targets)}
    rows = [r for r in DR.list_for_date(date_str) if not targets or r["person"] in targets]
    rows.sort(key=lambda r: rank.get(r["person"], 999))
    if not rows:
        st.info("この日の日報はまだありません。上のボタンで作成してください。")
        return

    st.divider()
    st.markdown("**書き出し（1日分まとめて）**")
    d1, d2, d3 = st.columns(3)
    d1.download_button("📄 Word（.docx）", _built(EX.build_docx, date_str, rows, "docx"),
                       file_name=f"業務日報_{date_str}.docx",
                       mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                       help="1人1ページ。そのまま印刷・回覧できる形")
    d2.download_button("📊 Excel（.xlsx）", _built(EX.build_xlsx, date_str, rows, "xlsx"),
                       file_name=f"業務日報_{date_str}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       help="1シートに全員分。対象者で選んだ順に並ぶ")
    d3.download_button("⬇ Markdown（.md）", DR.to_markdown(date_str, rows),
                       file_name=f"業務日報_{date_str}.md", mime="text/markdown")

    for r in rows:
        with st.expander(f"**{r['person']}** — {r['summary'] or '(要約なし)'}", expanded=True):
            st.caption(f"{_stats_line(r)} ／ 生成: {_local(r['updated_at'])}（{r['model']}）")
            st.markdown(r["body"])
            st.text_area("コピー用", r["body"], height=160, key=f"copy_{r['id']}",
                         label_visibility="collapsed")
            col = st.columns(3)
            if col[0].button("🔁 作り直す", key=f"re_{r['id']}"):
                p = by_name.get(r["person"], {})
                try:
                    DR.generate(date_str, r["person"], account_id=p.get("account_id"))
                    st.rerun()
                except Exception as e:
                    st.error(f"{type(e).__name__}: {e}")
            if col[1].button("📤 Chatworkへ（承認待ちに積む）", key=f"ob_{r['id']}"):
                _enqueue(r, date_str, by_name.get(r["person"], {}))
            if col[2].button("🗑 削除", key=f"del_{r['id']}"):
                DR.delete(date_str, r["person"])
                st.rerun()


def _enqueue(row, date_str, person, include_opinion=False):
    """outbox に pending で積むだけ。実送信は「投稿承認」画面で人が行う。"""
    room_id = person.get("room_id")
    if not room_id:
        st.error("投稿先ルームが分かりません。")
        return
    aid = person.get("account_id")
    to = mention(aid, row["person"]) if aid else ""
    body = f"{to}\n{EX.chatwork_body(row, date_str, include_opinion=include_opinion)}"
    ob_id = outbox.enqueue(room_id, body, kind="daily_report",
                           reason=f"{date_str} の業務日報",
                           to_account_ids=str(aid) if aid else None,
                           dedup_key=f"daily_report:{date_str}:{row['person']}")
    st.success(f"承認待ちに積みました（outbox #{ob_id}）。"
               "「📤 投稿承認（outbox）」で内容を確認して送信してください。")
