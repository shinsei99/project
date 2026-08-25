"""業務月報（TASK-20260825-001）。鷲見が全体Chatworkルームへアップロードする月1回の会議資料・
会議内容から、会社としての方針・戦略の記録をAIが作る。日報とは別物（役割・起点が違う）。

自動処理（トリガー検出のたび）は worker のループ（scheduler.run_monthly_report_check）で
承認を挟まず走る（日報の18:30自動処理と同じ扱い）。この画面は手動生成・確認・書き出し用。
"""
import datetime
import json
import os
import tempfile

import streamlit as st

from services import monthly_report as MR
from services import monthly_report_export as MEX
from services import settings as ST
from services.chatwork import ChatworkClient


def _built(builder, row, ext: str) -> bytes:
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, f"report.{ext}")
        builder(row, path)
        with open(path, "rb") as f:
            return f.read()


def _local(ts: str) -> str:
    try:
        dt = datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        return (dt + datetime.timedelta(hours=9)).strftime("%Y/%m/%d %H:%M")
    except (TypeError, ValueError):
        return ts or "-"


def render():
    st.title("📅 業務月報")
    st.caption("鷲見さんが全体Chatworkルームへ月1回アップロードする会議資料・会議内容から、"
               "会社としての方針・戦略の記録をAIが作ります。日報（社員ごと・毎日）とは別物です。")

    rid = MR.target_room_id()
    aid = MR.trigger_account_id()
    if not rid or not aid:
        st.warning("対象ルーム／対象者が決まっていません。下の「⚙️ 設定」で確認してください。")

    st.subheader("🆕 未処理の資料アップロード")
    st.caption("対象者が添付ファイル付きで送ったメッセージのうち、まだ月報にしていないもの"
               "（自動処理が有効なら worker が自動で作ります。ここは手動確認・作り直し用）。")
    pending = MR.pending_triggers(limit=10, room_id=rid, account_id=aid) if rid and aid else []
    if not pending:
        st.info("未処理の資料アップロードはありません。")
    for trig in pending:
        d = datetime.datetime.fromtimestamp(trig["send_time"]).strftime("%Y-%m-%d %H:%M")
        c1, c2 = st.columns([5, 1])
        c1.write(f"`{d}` {(trig['body'] or '')[:60]}")
        if c2.button("🧠 月報を作成", key=f"gen_{trig['message_id']}"):
            with st.spinner("会議資料・会議内容から月報を作成中…"):
                try:
                    MR.generate(trig["message_id"], generated_by="manual")
                    st.rerun()
                except Exception as e:
                    st.error(f"{type(e).__name__}: {e}")

    st.divider()
    st.subheader("📚 作成済みの月報")
    rows = MR.list_all(limit=24)
    if not rows:
        st.info("まだ月報はありません。")

    for r in rows:
        with st.expander(f"**{MEX.period_label(r['report_period'])}** — {r['summary'] or '(要約なし)'}",
                         expanded=(r is rows[0] if rows else False)):
            st.caption(f"生成: {_local(r['updated_at'])}（{r['model']}・{r['generated_by']}）")
            files = json.loads(r["files"] or "[]")
            if files:
                st.caption("添付資料: " + "、".join(
                    f"{f['filename']}{'' if f['ok'] else '（読取不可）'}" for f in files))
            st.markdown(r["body"])
            st.text_area("コピー用", r["body"], height=160, key=f"copy_{r['id']}",
                         label_visibility="collapsed")

            d1, d2, d3 = st.columns(3)
            d1.download_button("📄 Word（.docx）", _built(MEX.build_docx, r, "docx"),
                               file_name=f"業務月報_{r['report_period']}.docx",
                               mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                               key=f"docx_{r['id']}")
            d2.download_button("📊 Excel（.xlsx）", _built(MEX.build_xlsx, r, "xlsx"),
                               file_name=f"業務月報_{r['report_period']}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               key=f"xlsx_{r['id']}")
            d3.download_button("⬇ Markdown（.md）",
                               f"# 業務月報 {MEX.period_label(r['report_period'])}\n\n{r['body']}",
                               file_name=f"業務月報_{r['report_period']}.md", mime="text/markdown",
                               key=f"md_{r['id']}")

            col = st.columns(3)
            if col[0].button("🔁 作り直す", key=f"re_{r['id']}"):
                try:
                    MR.generate(r["trigger_message_id"], generated_by="manual")
                    st.rerun()
                except Exception as e:
                    st.error(f"{type(e).__name__}: {e}")
            if col[1].button("📤 同じルームへ手動アップ", key=f"up_{r['id']}"):
                try:
                    with tempfile.TemporaryDirectory() as d:
                        path = os.path.join(d, f"業務月報_{r['report_period']}.xlsx")
                        MEX.build_xlsx(r, path)
                        client = ChatworkClient()
                        client.post_file(r["room_id"], path,
                                         message=MEX.chatwork_body(r)[:1900])
                    st.success("アップしました。")
                except Exception as e:
                    st.error(f"{type(e).__name__}: {e}")
            if col[2].button("🗑 削除", key=f"del_{r['id']}"):
                MR.delete(r["trigger_message_id"])
                st.rerun()

    _settings_section()


def _settings_section():
    st.divider()
    st.subheader("⚙️ 設定")
    on = ST.get_setting("monthly_report_enabled", "1") == "1"
    upload_on = ST.get_setting("monthly_report_upload", "1") == "1"
    mail_on = ST.get_setting("monthly_report_mail", "0") == "1"
    st.caption(f"自動処理: {'🟢 有効' if on else '🔴 停止中'}／"
               f"アップロード検出→月報作成→Excel化→Dropbox保管（日報と同じフォルダ）"
               f"{'→同じルームへ自動アップ' if upload_on else ''}"
               f"{'→メール送信' if mail_on else ''}。**承認を挟みません。**"
               "止めたいときは下のチェックを外してください。")

    c1, c2, c3 = st.columns(3)
    new_on = c1.checkbox("自動処理を有効にする", value=on, key="mr_on")
    new_upload = c2.checkbox("同じルームへ自動アップ", value=upload_on, key="mr_upload")
    new_mail = c3.checkbox("社内メールでも送る", value=mail_on, key="mr_mail")

    room_id = ST.get_setting("monthly_report_room_id", "")
    account_id = ST.get_setting("monthly_report_account_id", "7426045")
    mail_to = ST.get_setting("monthly_report_mail_to", "")
    new_room = st.text_input("対象ルームID（空なら業務日報と同じ判定を流用）", value=room_id)
    new_account = st.text_input("資料をアップロードする人のaccount_id", value=account_id)
    new_mail_to = st.text_input("メール送信先（空なら業務日報の送信先を流用）", value=mail_to)

    if st.button("保存", key="mr_save"):
        ST.set_setting("monthly_report_enabled", "1" if new_on else "0")
        ST.set_setting("monthly_report_upload", "1" if new_upload else "0")
        ST.set_setting("monthly_report_mail", "1" if new_mail else "0")
        ST.set_setting("monthly_report_room_id", new_room.strip())
        ST.set_setting("monthly_report_account_id", new_account.strip())
        ST.set_setting("monthly_report_mail_to", new_mail_to.strip())
        st.success("保存しました。")
        st.rerun()

    st.caption(f"実際に使われる保存フォルダ（業務日報と共通）: "
               f"`{ST.get_setting('daily_report_save_dir', '(未設定)')}`")
