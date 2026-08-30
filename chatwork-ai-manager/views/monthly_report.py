"""業務月報（TASK-20260825-001 → TASK-20260826-002 で入力源をLINEへ変更）。
オーナーがLINEで直接送った内容（「月報開始」〜「月報終了」）から、会社としての方針・戦略の
記録をAIが作る。日報とは別物（役割・起点が違う）。Chatworkの資料アップロードでは作らない。

セッションの締切（自動生成・Excel化・Dropbox保管・Chatworkアップ）は line_webhook.py
（オーナーの「月報終了」）と scheduler.py（放置タイムアウト）が行う。この画面は状況確認・
過去分の閲覧・書き出し用。
"""
import datetime
import json
import os
import tempfile

import streamlit as st

from services import monthly_report as MR
from services import monthly_report_export as MEX
from services import monthly_report_line as MRL
from services import settings as ST
from services.chatwork import ChatworkClient


def _built(builder, row, ext: str) -> bytes:
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, f"report.{ext}")
        builder(row, path)
        with open(path, "rb") as f:
            return f.read()


def _local(ts: str) -> str:
    """DBは日本時間で入っているので、形を整えるだけ。

    ★2026-08-31 以前は datetime('now')＝UTC で記録していたため、ここで+9時間して
      いた。DB側を日本時間に直した（既存データも変換済み）ので、足すと二重になる。
    """
    try:
        dt = datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%Y/%m/%d %H:%M")
    except (TypeError, ValueError):
        return ts or "-"


def render():
    st.title("📅 業務月報")
    st.caption("オーナーがLINEで直接送った内容（「月報開始」〜「月報終了」）から、"
               "会社としての方針・戦略の記録をAIが作ります。日報（社員ごと・毎日）とは別物で、"
               "Chatworkの資料アップロードでは作りません。")

    if not MR.target_room_id():
        st.warning("Excelのアップ先ルームが決まっていません。下の「⚙️ 設定」で確認してください。")

    st.subheader("📥 LINE材料受付の状況")
    session = MRL.current_session()
    if not session:
        st.info("現在、受付中の月報セッションはありません。"
               "オーナーがLINEで「月報開始」と送ると材料受付が始まります。")
    else:
        n = MRL.item_count(session["id"])
        expired = MRL.is_expired(session)
        st.write(f"🟢 受付中（開始: {_local(session['opened_at'])}／材料 {n} 件）"
                + ("　⚠️ 放置タイムアウト対象（次のチェックで自動的に締め切られます）" if expired else ""))
        c1, c2 = st.columns(2)
        if c1.button("🧠 ここで締めて月報を作成", key="mr_line_finalize"):
            with st.spinner("受け付けた材料から月報を作成中…"):
                result = MR.finalize_line_session(session, generated_by="manual")
            if result["errors"]:
                st.error("・".join(result["errors"]))
            else:
                st.success("作成しました。")
            st.rerun()
        if c2.button("🗑 材料を破棄してセッションを閉じる", key="mr_line_discard"):
            MRL.close_session(session["id"])
            st.rerun()

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
                    session_id = int(r["trigger_message_id"].split(":", 1)[1])
                    mat = MRL.items(session_id)
                    MR.generate_from_line({"id": session_id}, mat, generated_by="manual")
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
    st.caption("オーナーがLINEで「月報開始」と送ると材料受付が始まり、「月報終了」で締めて"
               "月報を作成します。締め忘れたセッションは一定時間の放置で自動的に締め切ります。")
    st.caption(f"{'🟢 有効' if on else '🔴 停止中（LINEの月報開始/終了も無視されます）'}／"
               f"月報作成→Excel化→Dropbox保管（日報と同じフォルダ）"
               f"{'→アップ先ルームへ自動アップ' if upload_on else ''}"
               f"{'→メール送信' if mail_on else ''}。"
               "止めたいときは下のチェックを外してください。")

    c1, c2, c3 = st.columns(3)
    new_on = c1.checkbox("LINE経由の月報作成を有効にする", value=on, key="mr_on")
    new_upload = c2.checkbox("アップ先ルームへ自動アップ", value=upload_on, key="mr_upload")
    new_mail = c3.checkbox("社内メールでも送る", value=mail_on, key="mr_mail")

    room_id = ST.get_setting("monthly_report_room_id", "")
    mail_to = ST.get_setting("monthly_report_mail_to", "")
    timeout_min = ST.get_setting("monthly_report_line_session_timeout_min", "180")
    new_room = st.text_input("Excelのアップ先ルームID（空なら業務日報と同じ判定を流用）", value=room_id)
    new_mail_to = st.text_input("メール送信先（空なら業務日報の送信先を流用）", value=mail_to)
    new_timeout = st.text_input("LINE材料受付セッションの放置タイムアウト（分）", value=timeout_min)

    if st.button("保存", key="mr_save"):
        ST.set_setting("monthly_report_enabled", "1" if new_on else "0")
        ST.set_setting("monthly_report_upload", "1" if new_upload else "0")
        ST.set_setting("monthly_report_mail", "1" if new_mail else "0")
        ST.set_setting("monthly_report_room_id", new_room.strip())
        ST.set_setting("monthly_report_mail_to", new_mail_to.strip())
        if new_timeout.strip().isdigit():
            ST.set_setting("monthly_report_line_session_timeout_min", new_timeout.strip())
        st.success("保存しました。")
        st.rerun()

    st.caption(f"実際に使われる保存フォルダ（業務日報と共通）: "
               f"`{ST.get_setting('daily_report_save_dir', '(未設定)')}`")
