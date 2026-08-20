"""メールアーカイバ 閲覧UI（Streamlit）。

ローカルに落としたメールを、キーワード・送信元・フォルダ・期間で探して読む画面。
**この画面からサーバーのメールは消せない**（消すのは CLI の `sync.py --delete --yes` だけ）。
画面には「いま消せる候補」と、実行するためのコマンドだけを出す。
取り違えて押してしまう事故を無くすため、取り返しのつかない操作をUIに置いていない。
"""
from __future__ import annotations

import hmac
import os
from datetime import date, datetime, timedelta, timezone

import streamlit as st

import config
import db

st.set_page_config(page_title="メールアーカイバ", page_icon="📥", layout="wide")

PAGE_SIZE = 50

# スマホ（縦画面）で使うための調整。Streamlit の横並びは狭い画面だと潰れるので折り返す
st.markdown("""
<style>
@media (max-width: 700px) {
  /* 上はStreamlitの固定ヘッダ(約3rem)の下から始める。詰めすぎると題字が隠れる */
  .block-container { padding: 3.2rem 0.7rem 3rem 0.7rem !important; }
  /* 指標4つ・列組みを折り返す（潰れて読めなくなるのを防ぐ） */
  div[data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
  div[data-testid="stHorizontalBlock"] > div { min-width: 45% !important; }
  div[data-testid="stMetricValue"] { font-size: 1.4rem !important; }
  /* 一覧の見出しは2行まで見せる。指で押しやすいよう高さを確保 */
  details summary { font-size: 0.95rem !important; line-height: 1.5 !important;
                    min-height: 44px !important; }
  h1 { font-size: 1.5rem !important; }
  textarea { font-size: 16px !important; }  /* 16px未満だとiOSが勝手に拡大する */
}
</style>
""", unsafe_allow_html=True)


def _bound_to_lan() -> bool:
    """いまLANに出ているか（＝自分のPC以外から開けるか）。"""
    try:
        addr = str(st.get_option("server.address") or "")
    except Exception:
        addr = ""
    return addr not in ("127.0.0.1", "localhost", "::1", "")


def _check_password() -> bool:
    """パスワード認証。`.env.mail-archiver` の `UI_PASSWORD` と照合する。

    **LANに出ているのにパスワードが無いときは、画面を出さずに止める。**
    ここが扱うのはメール本文＝個人情報なので、「未設定なら素通り」にはしない。
    """
    expected = config.load().get("UI_PASSWORD", "")
    if not expected:
        if _bound_to_lan():
            st.error("🔒 パスワード（`UI_PASSWORD`）が未設定のまま、LANに公開された状態で"
                     "起動されています。メール本文を扱うため、この状態では画面を出しません。\n\n"
                     "`.env.mail-archiver` に `UI_PASSWORD=...` を書いて起動し直してください。")
            return False
        return True   # 自分のPCからだけ（127.0.0.1）なら不要
    if st.session_state.get("authed"):
        return True
    st.title("📥 メールアーカイバ")
    pw = st.text_input("パスワード", type="password")
    if st.button("ログイン", use_container_width=True):
        if hmac.compare_digest(str(pw), str(expected)):
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("パスワードが違います。")
    return False


if not _check_password():
    st.stop()


@st.cache_resource
def get_conn():
    conn = db.connect(config.DB_PATH)
    db.init_schema(conn)
    return conn


def human_size(n) -> str:
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return "{:.1f} {}".format(n, unit)
        n /= 1024


def to_local(iso: str) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso


conn = get_conn()
s = db.stats(conn)

st.title("📥 メールアーカイバ")
st.caption("IMAPサーバーの容量を空けるための、ローカル保管＋全文検索。"
           "サーバーからの削除は取り込みから14日後・CLIからのみ。")

c1, c2, c3, c4 = st.columns(4)
c1.metric("保存メール", "{:,} 通".format(s["messages"]), help="ローカルに原本(.eml)がある通数")
c2.metric("サーバーに残存", "{:,} 通".format(s["present"]), human_size(s["present_bytes"]))
c3.metric("サーバーから削除済", "{:,} 通".format(s["deleted"]), human_size(s["deleted_bytes"]))
c4.metric("添付ファイル", "{:,} 件".format(s["attachments"]), human_size(s["attachment_bytes"]))

tab_search, tab_archive = st.tabs(["🔍 検索・閲覧", "🗄 アーカイブ状況"])

# ------------------------------------------------------------------ 検索
with tab_search:
    accounts = db.list_accounts(conn)
    with st.sidebar:
        st.header("絞り込み")
        acc_map = {a["name"]: a["id"] for a in accounts}
        acc_name = st.selectbox("アカウント", ["（すべて）"] + list(acc_map.keys()))
        account_id = acc_map.get(acc_name)

        folders = db.list_folders(conn, account_id)
        f_map = {f["name"]: f["id"] for f in folders}
        f_name = st.selectbox("フォルダ", ["（すべて）"] + list(f_map.keys()))
        folder_id = f_map.get(f_name)

        sender = st.text_input("送信元（メールアドレス・表示名の一部）")
        use_period = st.checkbox("期間で絞る")
        date_from = date_to = ""
        if use_period:
            d1 = st.date_input("開始", value=date.today() - timedelta(days=365))
            d2 = st.date_input("終了", value=date.today())
            date_from = d1.strftime("%Y-%m-%dT00:00:00Z")
            date_to = d2.strftime("%Y-%m-%dT23:59:59Z")
        has_attach = st.checkbox("添付ありのみ")
        state = st.selectbox("サーバー側の状態",
                             ["all", "present", "deleted", "gone", "local"],
                             format_func=lambda x: {"all": "（すべて）", "present": "残っている",
                                                    "deleted": "このアプリが削除済",
                                                    "gone": "他で消された",
                                                    "local": "Mail.appから取込(IMAP管理外)"}[x])

    q = st.text_input("キーワード（件名・本文・宛先を横断。3文字以上が速い）", "")
    page = st.number_input("ページ", min_value=1, value=1, step=1)

    rows, total = db.search(conn, q=q, sender=sender, folder_id=folder_id,
                            account_id=account_id, date_from=date_from, date_to=date_to,
                            state=state, has_attach=has_attach,
                            limit=PAGE_SIZE, offset=(int(page) - 1) * PAGE_SIZE)
    st.write("**{:,} 件**該当（{} 〜 {} 件目を表示）".format(
        total, (int(page) - 1) * PAGE_SIZE + 1 if total else 0,
        min(int(page) * PAGE_SIZE, total)))

    if not rows:
        if s["messages"] == 0:
            st.info("まだ1通も取り込まれていません。`python3 sync.py --sync` を実行してください。")
        else:
            st.info("該当なし。")
    for r in rows:
        badge = {"present": "🟢", "deleted": "🗑", "gone": "❓", "local": "💻"}.get(
            r["server_state"], "")
        # 件名が無いメールは珍しくない（iPhoneから自分宛に送るメモ等）。実データで19通中19通が
        # 無題だった。「(件名なし)」が並ぶと一覧として使えないので、本文の冒頭を代わりに出す
        title = (r["subject"] or "").strip()
        if not title:
            head = " ".join((r["body_text"] or "").split())[:60]
            title = "（件名なし）{}".format(head) if head else "（件名なし）"
        label = "{} {} — {} ｜ {} ｜ {}{}".format(
            badge, to_local(r["date_utc"]) or "(日付不明)",
            title[:70],
            r["from_addr"] or r["from_name"] or "",
            r["folder_name"], " 📎" if r["has_attachments"] else "")
        with st.expander(label):
            m1, m2 = st.columns([3, 1])
            with m1:
                st.markdown("**件名**: {}".format(r["subject"] or "(なし)"))
                st.markdown("**From**: {} <{}>".format(r["from_name"] or "", r["from_addr"] or ""))
                st.markdown("**To**: {}".format(r["to_addrs"] or ""))
                if r["cc_addrs"]:
                    st.markdown("**Cc**: {}".format(r["cc_addrs"]))
            with m2:
                st.markdown("**フォルダ**: {}".format(r["folder_name"]))
                st.markdown("**サイズ**: {}".format(human_size(r["size_bytes"])))
                st.markdown("**取込日時**: {}".format(to_local(r["synced_at"])))
                st.markdown("**状態**: {}".format(
                    {"present": "サーバーにも在る", "deleted": "サーバーからは削除済",
                     "gone": "サーバーには無い",
                     "local": "Mail.appから取込（IMAP管理外・削除対象にならない）"
                     }.get(r["server_state"], r["server_state"])))
            st.text_area("本文", r["body_text"] or "(本文なし)", height=280,
                         key="body_{}".format(r["id"]))

            atts = db.attachments_of(conn, r["id"])
            if atts:
                st.markdown("**添付**")
                for a in atts:
                    ap = os.path.join(config.DATA_DIR, a["path"])
                    if os.path.exists(ap):
                        with open(ap, "rb") as fp:
                            st.download_button(
                                "⬇ {} ({})".format(a["filename"], human_size(a["size_bytes"])),
                                fp.read(), file_name=a["filename"],
                                key="att_{}".format(a["id"]))
                    else:
                        st.warning("添付が見つかりません: {}".format(a["filename"]))

            raw_abs = os.path.join(config.DATA_DIR, r["raw_path"])
            if os.path.exists(raw_abs):
                with open(raw_abs, "rb") as fp:
                    st.download_button("⬇ 原本 .eml をダウンロード（メールアプリで開ける）",
                                       fp.read(),
                                       file_name="{}.eml".format(r["uid"]),
                                       key="eml_{}".format(r["id"]))
            else:
                st.error("原本 .eml が見つかりません。サーバーからは絶対に消さないこと。")

# ------------------------------------------------------------------ アーカイブ状況
with tab_archive:
    cfg = config.load()
    days = int(cfg.get("ARCHIVE_DELETE_DAYS", "14"))
    st.subheader("サーバー側削除の状況")
    st.markdown(
        "- 削除の有効/無効: **{}**（`.env.mail-archiver` の `ARCHIVE_DELETE_ENABLED`）\n"
        "- 据置日数: **{}日**（取り込み `synced_at` からこの日数が過ぎたものだけが対象）\n"
        "- 除外フォルダ: {}".format(
            "有効" if cfg.get("ARCHIVE_DELETE_ENABLED") == "1" else "無効",
            days, "、".join(config.excluded_folders(cfg)) or "（なし）"))

    accounts = db.list_accounts(conn)
    if accounts:
        acc = accounts[0]
        cands = db.deletable_candidates(conn, acc["id"], days)
        total_bytes = sum(int(c["size_bytes"] or 0) for c in cands)
        st.metric("いま削除条件を満たすメール", "{:,} 通".format(len(cands)), human_size(total_bytes))
        st.caption("※ここに出るのは「日数」の条件だけを見た候補。実行時は原本のSHA256・"
                   "UIDVALIDITY・Message-ID の一致まで1通ずつ確かめ、"
                   "合わないものは飛ばします。")
        st.code("cd {}\npython3 sync.py --delete          # まず dry-run（何も消えない）\n"
                "python3 sync.py --delete --yes    # 確認後に本当に消す".format(config.APP_DIR),
                language="bash")

    st.subheader("削除ログ（直近200件）")
    logs = db.recent_delete_log(conn, 200)
    if logs:
        st.dataframe(
            [{"日時": to_local(l["at"]), "結果": l["mode"], "フォルダ": l["folder"],
              "uid": l["uid"], "件名": (l["subject"] or "")[:50],
              "サイズ": human_size(l["size_bytes"]), "理由": l["reason"] or ""} for l in logs],
            use_container_width=True, hide_index=True)
    else:
        st.info("まだ削除（dry-run 含む）を実行していません。")
