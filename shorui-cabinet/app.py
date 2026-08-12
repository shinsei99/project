# -*- coding: utf-8 -*-
"""書類キャビネット — 紙の書類が「どこにあるか」を管理するアプリ。

管理の単位は **ファイル1冊（クリアファイル・バインダー・箱）**。書類1枚ずつは登録しない。
中身をパラパラ数枚撮ると claude CLI が目録を起こすので、人の作業は1冊あたり1回で済む。

起動: ./run.sh → http://localhost:8528
"""

# 実行環境は system python 3.9（他アプリと同じ）。新しい型注釈を書けるようにする。
from __future__ import annotations

import io
import json
import os
import shutil
from datetime import date

import pandas as pd
import streamlit as st

import ai_reader
import db
import inbox
import pdf_split

st.set_page_config(page_title="書類キャビネット", page_icon="🗄", layout="wide")

db.init_db()

ACCEPT = ["pdf", "jpg", "jpeg", "png", "webp", "heic"]
IMG_EXT = (".pdf", ".jpg", ".jpeg", ".png", ".webp", ".heic")
CONF_LABEL = {"high": "確度 高", "medium": "確度 中", "low": "確度 低"}
# 重要度（人が手で選ぶ。契約書=高 など）
IMPORTANCE_OPTS = ["", "高", "中", "低"]
IMPORTANCE_BADGE = {"高": "🔴 高", "中": "🟡 中", "低": "⚪ 低", "": ""}
def imp_label(x: str) -> str:
    return IMPORTANCE_BADGE.get(x or "", "") or "（未設定）"

# スマホ用（shorui-mobile）が Dropbox 経由で写真を届けるフォルダ。
# 1サブフォルダ＝1冊。処理済みは _済/ に退避する。環境変数で上書き可。
INBOX_DIR = os.environ.get(
    "SHORUI_INBOX",
    os.path.expanduser("~/Library/CloudStorage/Dropbox-個人/書類取込"),
)
INBOX_DONE = os.path.join(INBOX_DIR, "_済")


def list_inbox_batches() -> list:
    """取込フォルダ内の未処理の束（サブフォルダ）を新しい順に返す。"""
    if not os.path.isdir(INBOX_DIR):
        return []
    out = []
    for name in os.listdir(INBOX_DIR):
        if name.startswith("_") or name.startswith("."):
            continue
        path = os.path.join(INBOX_DIR, name)
        if not os.path.isdir(path):
            continue
        imgs = sorted(
            f for f in os.listdir(path)
            if f.lower().endswith(IMG_EXT) and not f.startswith(".")
        )
        if not imgs:
            continue
        meta = {}
        mp = os.path.join(path, "meta.json")
        if os.path.exists(mp):
            try:
                with open(mp, encoding="utf-8") as fh:
                    meta = json.load(fh)
            except Exception:
                meta = {}
        out.append({"name": name, "path": path, "images": imgs, "meta": meta})
    out.sort(key=lambda b: b["name"], reverse=True)
    return out


# ---------------- 共通の小道具 ----------------

def location_options():
    """保管場所のselectbox用（先頭は未設定）。"""
    locs = db.list_locations()
    ids = [None] + [r["id"] for r in locs]
    labels = {None: "（未設定）"}
    labels.update({r["id"]: r["name"] for r in locs})
    return ids, labels


def property_names() -> list:
    return [r["name"] for r in db.list_properties()]


def thumb_path(name: str):
    if not name:
        return None
    p = os.path.join(db.THUMB_DIR, name)
    return p if os.path.exists(p) else None


def draft_default() -> dict:
    return {
        "label": "", "properties": [], "doc_types": [],
        "year_from": "", "year_to": "", "contents": [],
        "summary": "", "confidence": "",
    }


# ---------------- サイドバー ----------------

s = db.stats()
st.sidebar.title("🗄 書類キャビネット")
st.sidebar.caption("クリアファイル・箱の単位で中身と置き場所を管理する")
c1, c2 = st.sidebar.columns(2)
c1.metric("ファイル", f"{s['files']:,}")
c2.metric("保管場所", f"{s['locations']:,}")
if s["unplaced"]:
    st.sidebar.warning(f"保管場所が未設定のファイルが {s['unplaced']} 件あります")

# ---- サイドバー: 保管場所の登録・削除 ----
with st.sidebar.expander("🗄 保管場所の登録・削除", expanded=True):
    with st.form("side_add_loc", clear_on_submit=True):
        _new_name = st.text_input("場所の名前", placeholder="本社3F 書庫A / 棚2")
        _new_note = st.text_input("メモ（任意）", placeholder="鍵は総務が管理 など")
        if st.form_submit_button("＋ この場所を追加", type="primary", use_container_width=True):
            if _new_name.strip():
                db.add_location(_new_name, _new_note)
                st.rerun()
            else:
                st.warning("場所の名前を入れてください")

    _locs = db.list_locations()
    _counts = db.location_counts()
    if not _locs:
        st.caption("まだ保管場所がありません。上の欄で追加してください。")
    else:
        # 一覧はスッキリ名前だけ。編集・削除は下の「管理」欄から選んで行う。
        st.caption("登録済み（かっこ内はファイル数）")
        for _l in _locs:
            st.markdown(
                f"📍 {_l['name']}　<span style='color:#888'>({_counts.get(_l['id'], 0)})</span>",
                unsafe_allow_html=True,
            )

        _name_of = {_l["id"]: _l["name"] for _l in _locs}
        _note_of = {_l["id"]: (_l["note"] or "") for _l in _locs}
        _sort_of = {_l["id"]: _l["sort"] for _l in _locs}

        st.divider()
        _sel = st.selectbox("編集・削除する場所", list(_name_of),
                            format_func=lambda i: _name_of[i], key="side_manage_sel")
        with st.form("side_manage_form"):
            _en = st.text_input("名前", _name_of[_sel], key=f"side_mname_{_sel}")
            _et = st.text_input("メモ", _note_of[_sel], key=f"side_mnote_{_sel}")
            m1, m2 = st.columns(2)
            _save = m1.form_submit_button("保存", type="primary", use_container_width=True)
            _del = m2.form_submit_button("削除", use_container_width=True)
        if _save:
            if _en.strip():
                db.update_location(_sel, _en, _et, _sort_of[_sel])
                st.success("保存しました")
                st.rerun()
            else:
                st.warning("名前を入れてください")
        if _del:
            st.session_state["side_del_pending"] = _sel
            st.rerun()

        _pending = st.session_state.get("side_del_pending")
        if _pending is not None and _pending in _name_of:
            st.markdown(f"**⚠️ 「{_name_of[_pending]}」を削除しますか？**")
            _pc = _counts.get(_pending, 0)
            if _pc:
                st.caption(f"この場所の {_pc} 冊は「未設定」に戻ります（ファイル自体は消えません）")
            dd1, dd2 = st.columns(2)
            if dd1.button("削除する", type="primary", use_container_width=True,
                          key="side_del_confirm"):
                db.delete_location(_pending)
                st.session_state.pop("side_del_pending", None)
                st.rerun()
            if dd2.button("やめる", use_container_width=True, key="side_del_cancel"):
                st.session_state.pop("side_del_pending", None)
                st.rerun()

if not ai_reader.claude_available():
    st.sidebar.error("claude CLI が見つかりません。AI読み取りは使えませんが、手入力での登録・検索は可能です。")

try:
    _pending_n = len(inbox.list_folders(db.get_setting("inbox", inbox.default_root())))
except Exception:
    _pending_n = 0
_add_label = f"📥 ファイルを登録（{_pending_n}）" if _pending_n else "📥 ファイルを登録"
tab_add, tab_loc, tab_pdf, tab_conf = st.tabs(
    [_add_label, "🗄 保管場所", "📄 PDFを整理", "⚙️ 設定"]
)


# ================= 登録 =================
with tab_add:
    st.subheader("ファイルを1冊登録する")
    st.caption(
        "クリアファイル1冊・バインダー1冊・箱1つが登録の単位です。"
        "中身をパラパラと数枚撮って読み込ませると、目録が自動で作られます。"
    )

    draft = st.session_state.setdefault("draft", draft_default())

    # --- 倉庫でスマホから送った写真を、フォルダ単位で拾う ---
    with st.container(border=True):
        h1, h2 = st.columns([4, 1])
        h1.markdown("**📥 スマホから送った写真を読む**")
        if h2.button("🔄 更新", use_container_width=True,
                     help="スマホから送った直後はこれを押してください"):
            st.rerun()
        st.caption(
            "倉庫でスマホから、クリアファイルの名前のフォルダ（例: `経理2014-1`）を作って"
            "中身の写真を入れておくと、ここに出ます。**フォルダ名がそのまま見出しになります。**"
        )
        root = st.text_input(
            "取り込みフォルダ", db.get_setting("inbox", inbox.default_root()),
            help="DropboxやiCloud Driveの中を指定すると、スマホから入れたものがMacに同期されます。",
        )
        if root != db.get_setting("inbox", inbox.default_root()):
            db.set_setting("inbox", root)

        if not os.path.isdir(root):
            e1, e2 = st.columns([3, 1])
            e1.info("このフォルダはまだありません。作ると、スマホから入れた写真をここで拾えます。")
            if e2.button("フォルダを作る", use_container_width=True):
                try:
                    os.makedirs(root, exist_ok=True)
                    st.rerun()
                except OSError as e:
                    st.error(f"作れませんでした: {e}")
        else:
            entries = inbox.list_folders(root)
            if not entries:
                st.caption(
                    "いま待っているものはありません。"
                    "スマホでこの中にフォルダを作り、中身の写真を入れてください。"
                )
            else:
                sel = []
                for i, ent in enumerate(entries):
                    if st.checkbox(f"📁 **{ent['name']}** — {len(ent['files'])} 枚",
                                   value=True, key=f"inbox{i}"):
                        sel.append(ent)
                n1, n2 = st.columns([1, 2])
                if n1.button(f"🤖 選んだ {len(sel)} 冊を読み取る", type="primary",
                             disabled=not sel or not ai_reader.claude_available(),
                             use_container_width=True):
                    batch = st.session_state.get("inbox_batch") or []
                    bar = st.progress(0.0, text="読み取り中…")
                    for i, ent in enumerate(sel):
                        bar.progress(i / len(sel),
                                     text=f"{ent['name']}（{i + 1}/{len(sel)}冊目）を読み取り中…")
                        msgs: list = []
                        uploads = inbox.read_files(ent)
                        got = ai_reader.read_file_contents(uploads, note=msgs.append)
                        if not got:
                            st.error(f"{ent['name']}: 読み取れませんでした（撮り直してください）")
                            continue
                        # スマホで付けた名前を見出しにする（AIの案より人が付けた名前を優先）
                        got["label"] = ent["name"]
                        thumb = f"file_{abs(hash(ent['name'] + str(len(uploads))))}.jpg"
                        if not ai_reader.make_thumb(uploads[0][0], uploads[0][1],
                                                    os.path.join(db.THUMB_DIR, thumb)):
                            thumb = ""
                        batch.append({"name": ent["name"], "path": ent["path"],
                                      "draft": got, "thumb": thumb})
                    bar.empty()
                    st.session_state["inbox_batch"] = batch
                    st.rerun()
                n2.caption(
                    "1冊あたり1〜2分かかります。10冊なら15分ほど見てください"
                    "（読み取り中はこの画面のまま待ちます）"
                )

    # --- 読み取り済みをまとめて登録する ---
    batch = st.session_state.get("inbox_batch") or []
    if batch:
        with st.container(border=True):
            st.markdown(f"**📋 読み取り済み {len(batch)} 冊 — まとめて登録**")
            st.caption(
                "保管場所を選んで「まとめて登録」を押すと、一度に台帳へ入ります。"
                "見出しと場所は表の上で直せます。"
            )
            ids, labels = location_options()
            m1, m2, m3 = st.columns([2, 2, 1])
            common = m1.selectbox(
                "保管場所（全部まとめて）", ids, format_func=lambda x: labels[x],
                key="batchloc", help="ここで選ぶと下の表の全行に入ります。行ごとに変えられます。",
            )
            common_spot = m2.text_input("場所の中の位置（全部まとめて）", key="batchspot",
                                        placeholder="例: 上から2段目 左端")
            common_imp = m3.selectbox("重要度（全部）", IMPORTANCE_OPTS,
                                      format_func=imp_label, key="batchimp")

            rows = st.data_editor(
                pd.DataFrame([{
                    "登録": True,
                    "見出し": it["draft"].get("label", it["name"]),
                    "保管場所": labels[common],
                    "位置": common_spot,
                    "重要度": common_imp,
                    "種別": "、".join(it["draft"].get("doc_types", [])),
                    "年": f'{it["draft"].get("year_from", "")}〜{it["draft"].get("year_to", "")}',
                    "確度": CONF_LABEL.get(it["draft"].get("confidence", ""), ""),
                } for it in batch]),
                key=f"batched{len(batch)}", hide_index=True, use_container_width=True,
                disabled=["種別", "年", "確度"],
                column_config={
                    "登録": st.column_config.CheckboxColumn(width="small"),
                    "保管場所": st.column_config.SelectboxColumn(
                        options=[labels[i] for i in ids], width="medium"),
                    "重要度": st.column_config.SelectboxColumn(
                        options=IMPORTANCE_OPTS, width="small"),
                    "見出し": st.column_config.TextColumn(width="large"),
                },
            )
            if any(it["draft"].get("confidence") == "low" for it in batch):
                st.warning("確度の低い読み取りがあります。物件名は登録前に確認してください。")

            with st.expander("読み取った中身を確認する"):
                for it in batch:
                    st.markdown(f"**{it['draft'].get('label', it['name'])}**")
                    st.caption("、".join(it["draft"].get("properties", [])) or "（物件名なし）")
                    st.text("\n".join(it["draft"].get("contents", [])))
                    st.divider()

            r1, r2 = st.columns([1, 3])
            if r1.button("✅ まとめて登録する", type="primary", use_container_width=True):
                name_to_id = {labels[i]: i for i in ids}
                done, kept = 0, []
                for it, (_, row) in zip(batch, rows.iterrows()):
                    if not row["登録"]:
                        kept.append(it)     # チェックを外した分は残しておく
                        continue
                    d = it["draft"]
                    db.add_file({
                        "label": str(row["見出し"] or it["name"]),
                        "kind": db.KINDS[0],
                        "location_id": name_to_id.get(str(row["保管場所"])),
                        "spot": str(row["位置"] or ""),
                        "properties": "\n".join(d.get("properties", [])),
                        "doc_types": ",".join(d.get("doc_types", [])),
                        "year_from": d.get("year_from", ""),
                        "year_to": d.get("year_to", ""),
                        "item_count": "",
                        "contents": "\n".join(d.get("contents", [])),
                        "summary": d.get("summary", ""),
                        "importance": str(row["重要度"] or ""),
                        "thumb": it.get("thumb", ""),
                    })
                    for p in d.get("properties", []):
                        db.add_property(p)
                    # 登録できてから初めてフォルダを退避する（消さずに移すだけ）
                    try:
                        inbox.archive({"name": it["name"], "path": it["path"]})
                    except OSError:
                        pass
                    done += 1
                st.session_state["inbox_batch"] = kept
                st.success(f"{done} 冊を登録しました。")
                st.rerun()
            if r2.button("読み取り結果を捨てる"):
                st.session_state["inbox_batch"] = []
                st.rerun()

    with st.container(border=True):
        st.markdown("**① 中身を撮って読み取る**（任意・手入力だけでも登録できます）")
        shots = st.file_uploader(
            "このファイルの中身の写真・PDF（複数可）",
            type=ACCEPT, accept_multiple_files=True, key="shots",
        )
        u1, u2 = st.columns([1, 3])
        go = u1.button(
            "🤖 中身を読み取る", type="primary",
            disabled=not shots or not ai_reader.claude_available(),
            use_container_width=True,
        )
        u2.caption("写真の枚数にもよりますが1〜2分ほどかかります（正確さ優先のため上位モデルを使用）")

        if go and shots:
            uploads = [(f.getvalue(), f.name) for f in shots]
            msgs: list = []
            with st.spinner("読み取り中…"):
                got = ai_reader.read_file_contents(uploads, note=msgs.append)
            if msgs:
                st.info("\n".join(msgs))
            if got:
                st.session_state["draft"] = got
                # 1枚目をサムネイルにする（一覧で見分けるため）
                safe = f"file_{abs(hash(shots[0].name + str(len(uploads))))}.jpg"
                if ai_reader.make_thumb(uploads[0][0], uploads[0][1],
                                        os.path.join(db.THUMB_DIR, safe)):
                    st.session_state["draft_thumb"] = safe
                st.rerun()
            else:
                st.error("読み取れませんでした。手入力で登録するか、撮り直してください。")

    draft = st.session_state.get("draft", draft_default())
    if draft.get("confidence"):
        lv = draft["confidence"]
        msg = f"AIの読み取り結果を反映しました（{CONF_LABEL.get(lv, '')}）"
        (st.success if lv == "high" else st.warning)(
            msg + ("" if lv == "high" else " — 物件名と固有名詞は目視で確認してください")
        )

    with st.container(border=True):
        st.markdown("**② 内容を確認して登録**")
        ids, labels = location_options()
        types = db.all_doc_types()

        f1, f2 = st.columns([3, 1])
        label = f1.text_input(
            "ファイルの見出し（背表紙の名前）*", draft.get("label", ""),
            placeholder="例: 角屋（横堤）モータープール 契約関係",
        )
        kind = f2.selectbox("入れ物の種類", db.KINDS)

        g1, g2, g3 = st.columns([2, 2, 1])
        loc = g1.selectbox("保管場所 *", ids, format_func=lambda x: labels[x])
        spot = g2.text_input("場所の中の位置", placeholder="例: 上から2段目 左端")
        with g3:
            # フォームにすると Enter でも送信され、日本語入力の確定Enterで欄が消える誤操作を防げる。
            with st.form("reg_add_loc", clear_on_submit=True):
                newloc = st.text_input("場所を追加", placeholder="本社3F 書庫A")
                if st.form_submit_button("追加", use_container_width=True) and newloc.strip():
                    db.add_location(newloc.strip())
                    st.rerun()

        h1, h2, h3, h4 = st.columns([1, 1, 1, 1])
        yf = h1.text_input("いちばん古い年", draft.get("year_from", ""), placeholder="2019")
        yt = h2.text_input("いちばん新しい年", draft.get("year_to", ""), placeholder="2026")
        cnt = h3.text_input("点数（おおよそ）", placeholder="12")
        imp = h4.selectbox("重要度", IMPORTANCE_OPTS, format_func=imp_label, key="reg_imp")

        dts = st.multiselect(
            "入っている書類の種別",
            types,
            default=[t for t in draft.get("doc_types", []) if t in types],
        )
        props = st.text_area(
            "関係する物件（1行1件）",
            "\n".join(draft.get("properties", [])),
            height=80,
            help="ここに書いた物件名で検索できます。登録すると物件マスタにも追加されます。",
        )
        contents = st.text_area(
            "中身の目録（1行1件）",
            "\n".join(draft.get("contents", [])),
            height=180,
            help="ここも検索対象です。AIが起こした目録はここに入ります。",
        )
        summary = st.text_input("ひとことメモ", draft.get("summary", ""))

        b1, b2 = st.columns([1, 4])
        if b1.button("✅ このファイルを登録", type="primary", use_container_width=True):
            if not label.strip():
                st.error("ファイルの見出しを入れてください")
            else:
                db.add_file({
                    "label": label, "kind": kind, "location_id": loc, "spot": spot,
                    "properties": props, "doc_types": ",".join(dts),
                    "year_from": yf, "year_to": yt, "item_count": cnt,
                    "contents": contents, "summary": summary, "importance": imp,
                    "thumb": st.session_state.get("draft_thumb", ""),
                })
                for p in props.splitlines():
                    db.add_property(p)
                st.session_state["draft"] = draft_default()
                st.session_state.pop("draft_thumb", None)
                st.success(f"「{label}」を登録しました")
                st.rerun()
        if b2.button("入力をクリア"):
            st.session_state["draft"] = draft_default()
            st.session_state.pop("draft_thumb", None)
            st.rerun()


# ================= PDFを整理 =================
with tab_pdf:
    st.subheader("PDFを書類ごとに整理する")
    st.caption(
        "クリアフォルダ1冊分をまとめてスキャンしたPDFを読み、中に入っている書類を"
        "1件ずつに切り分けて、種類・日付・正式なタイトルを付けます。"
    )

    if not pdf_split.available():
        st.error(
            "この機能には claude CLI と PyMuPDF が必要です。"
            "`./run.sh` で起動していれば依存は入っています。"
        )

    with st.container(border=True):
        ups = st.file_uploader(
            "スキャン済みPDF（複数可）", type=["pdf"],
            accept_multiple_files=True, key="pdfups",
        )
        c1, c2 = st.columns([1, 3])
        do_split = c2.checkbox(
            "1つのPDFに複数の書類が入っている前提で分割する", value=True,
            help="外すと「1PDF＝1書類」として扱い、種類と名前を付けるだけになります。",
        )
        if c1.button("🤖 中身を判定する", type="primary",
                     disabled=not ups or not pdf_split.available(),
                     use_container_width=True):
            items = [(f.name, f.getvalue()) for f in ups]
            jobs, msgs = [], []
            if items:
                bar = st.progress(0.0, text="判定中…")
                for i, (name, data) in enumerate(items):
                    bar.progress(i / len(items), text=f"{name} を判定中…")
                    try:
                        segs = pdf_split.analyse(data, split=do_split, note=msgs.append)
                    except pdf_split.SplitError as e:
                        st.error(f"{name}: {e}")
                        continue
                    jobs.append({"name": name, "data": data, "segs": segs})
                bar.empty()
                st.session_state["pdfmsgs"] = msgs[-6:]
                st.session_state["pdfjobs"] = jobs
                st.rerun()
        c2.caption(
            "枚数によりますが1〜数分かかります"
            "（写真・スキャン画像は誤読を避けるため正確さ優先の上位モデルを使います）"
        )

    for m in st.session_state.get("pdfmsgs", []):
        st.caption(m)

    jobs = st.session_state.get("pdfjobs") or []
    for ji, job in enumerate(jobs):
        segs = job["segs"]
        with st.container(border=True):
            st.markdown(
                f"**📄 {job['name']}** — 全{pdf_split.page_count(job['data'])}ページ / "
                f"**{len(segs)} 件の書類**を検出"
            )
            if any(s["confidence"] == "low" for s in segs):
                st.warning("確度の低い判定があります。物件名と日付は目視で確認してください。")
            st.caption("内容はこの表で直せます。直してから下のボタンを押してください。")

            edited = st.data_editor(
                pd.DataFrame([{
                    "ページ": f"{s['start_page']}-{s['end_page']}",
                    "種類": s["doc_type"],
                    "日付": s["date"],
                    "タイトル": s["title"],
                    "物件": s["property"],
                    "確度": CONF_LABEL.get(s["confidence"], ""),
                } for s in segs]),
                key=f"pdfed{ji}", hide_index=True, use_container_width=True,
                disabled=["ページ", "確度"],
                column_config={
                    "種類": st.column_config.SelectboxColumn(
                        options=db.DEFAULT_DOC_TYPES, width="medium", required=True),
                    "日付": st.column_config.TextColumn(
                        help="YYYY-MM-DD。分からなければ空のままでよい", width="small"),
                    "タイトル": st.column_config.TextColumn(width="large"),
                },
            )

            # 表の編集内容を判定結果に反映する（ページ範囲と確度は編集不可）
            fixed = []
            for s, (_, row) in zip(segs, edited.iterrows()):
                d = dict(s)
                d["doc_type"] = str(row["種類"] or pdf_split.UNCLASSIFIED)
                d["date"] = pdf_split.normalise_date(str(row["日付"] or ""))
                d["title"] = str(row["タイトル"] or "")
                d["property"] = str(row["物件"] or "")
                fixed.append(d)

            if fixed:
                st.caption("ファイル名の例: " + pdf_split.build_name(fixed[0], job["name"]))

            g1, g2, g3 = st.columns([2, 2, 1])
            if g1.button("🗜 分割したPDFを作る", key=f"mkzip{ji}", use_container_width=True):
                with st.spinner("分割中…"):
                    st.session_state[f"pdfzip{ji}"] = pdf_split.make_zip(
                        job["data"], fixed, job["name"])
                st.rerun()

            blob = st.session_state.get(f"pdfzip{ji}")
            if blob:
                g1.download_button(
                    "⬇️ ZIPをダウンロード", blob,
                    file_name=os.path.splitext(job["name"])[0] + "_整理済み.zip",
                    mime="application/zip", key=f"dlzip{ji}", use_container_width=True,
                )

            if g2.button("📥 この内容を台帳に送る", key=f"toreg{ji}", use_container_width=True):
                years = sorted({d["date"][:4] for d in fixed
                                if d["date"][:4].isdigit() and d["date"][:4] != "0000"})
                types: list = []
                for d in fixed:
                    if d["doc_type"] not in types:
                        types.append(d["doc_type"])
                st.session_state["draft"] = {
                    "label": os.path.splitext(job["name"])[0],
                    "properties": sorted({d["property"] for d in fixed if d["property"]}),
                    "doc_types": types,
                    "year_from": years[0] if years else "",
                    "year_to": years[-1] if years else "",
                    "contents": pdf_split.to_contents_lines(fixed),
                    "summary": f"{len(fixed)}件の書類（PDFの整理から）",
                    "confidence": "low" if any(d["confidence"] == "low" for d in fixed) else "high",
                }
                st.success(
                    "「📥 ファイルを登録」タブに送りました。"
                    "保管場所を選んで登録してください。"
                )

            if g3.button("消す", key=f"delpdf{ji}", use_container_width=True):
                st.session_state["pdfjobs"] = [j for k, j in enumerate(jobs) if k != ji]
                st.session_state.pop(f"pdfzip{ji}", None)
                st.rerun()


# ================= 保管場所 =================
with tab_loc:
    st.subheader("保管場所")
    st.caption("棚の中身を見る・探す・直すのは全部ここ。場所の追加・名前変更・削除は左のサイドバーから。")

    ids, labels = location_options()

    # --- 場所がまだ決まっていない分を、あとでまとめて割り当てる ---
    unplaced = db.list_unplaced()
    if unplaced:
        with st.container(border=True):
            st.markdown(f"**📦 場所がまだ決まっていないファイル — {len(unplaced)} 冊**")
            st.caption("棚に戻すときに、ここでまとめて割り当ててください。")
            real_ids = [i for i in ids if i]
            if not real_ids:
                st.info("先にサイドバーで保管場所を1つ登録してください。")
            else:
                w1, w2 = st.columns([2, 2])
                to_loc = w1.selectbox("この場所に入れる", real_ids,
                                      format_func=lambda x: labels[x], key="uploc")
                to_spot = w2.text_input("場所の中の位置", key="upspot",
                                        placeholder="例: 上から2段目 左端")
                picked = st.data_editor(
                    pd.DataFrame([{
                        "割当": False,
                        "見出し": r["label"],
                        "物件": r["properties"].replace("\n", "、"),
                        "種別": r["doc_types"].replace(",", "、"),
                        "年": f'{r["year_from"]}〜{r["year_to"]}',
                    } for r in unplaced]),
                    key="unplaced_ed", hide_index=True, use_container_width=True,
                    disabled=["見出し", "物件", "種別", "年"],
                    column_config={"割当": st.column_config.CheckboxColumn(width="small")},
                )
                chosen = [r["id"] for r, (_, row) in zip(unplaced, picked.iterrows())
                          if row["割当"]]
                v1, v2 = st.columns([1, 3])
                if v1.button(f"📍 {len(chosen)} 冊をここに置く", type="primary",
                             disabled=not chosen, use_container_width=True):
                    n = db.set_location(chosen, to_loc, to_spot)
                    st.success(f"{n} 冊を「{labels[to_loc]}」にしました。")
                    st.rerun()
                if v2.button("すべて選ぶ / すべて外す"):
                    st.session_state.pop("unplaced_ed", None)
                    st.rerun()

    # --- さがす（キーワード・保管場所・重要度で絞り込み） ---
    st.markdown("#### さがす")
    q1, q2, q3 = st.columns([3, 2, 2])
    kw = q1.text_input("キーワード（スペース区切りでAND検索）",
                       placeholder="例: 角屋 契約", key="loc_kw")
    fl = q2.selectbox("保管場所", ids,
                      format_func=lambda x: labels[x] if x else "（すべて）", key="loc_fl")
    fi = q3.selectbox("重要度", ["（すべて）"] + IMPORTANCE_OPTS[1:], key="loc_fi")

    rows = db.search_files(
        keyword=kw,
        location_id=fl,
        importance="" if fi == "（すべて）" else fi,
    )
    st.caption(f"{len(rows):,} 件　—　行を選ぶと下に詳細が出ます")

    if not rows:
        st.info("該当なし。ファイルは「📥 ファイルを登録」から追加できます。")
    else:
        table = st.dataframe(
            pd.DataFrame([{
                "重要度": IMPORTANCE_BADGE.get(r["importance"] or "", ""),
                "見出し": r["label"],
                "保管場所": r["location_name"] or "（未設定）",
                "位置": r["spot"],
                "種別": r["doc_types"].replace(",", "、"),
                "物件": r["properties"].replace("\n", "、"),
                "年": f'{r["year_from"]}〜{r["year_to"]}'.strip("〜"),
            } for r in rows]),
            hide_index=True, use_container_width=True,
            on_select="rerun", selection_mode="single-row", key="loc_table",
        )

        sel = table.selection.rows if getattr(table, "selection", None) else []
        if sel and sel[0] < len(rows):
            r = rows[sel[0]]
            st.divider()
            with st.container(border=True):
                place = r["location_name"] or "（保管場所 未設定）"
                spot = f"／{r['spot']}" if r["spot"] else ""
                head = IMPORTANCE_BADGE.get(r["importance"] or "", "")
                st.markdown(f"### {(head + '　') if head else ''}{r['label']}")
                st.markdown(f"📍 **{place}**{spot}")
                left, right = st.columns([1, 3])
                with left:
                    tp = thumb_path(r["thumb"])
                    if tp:
                        st.image(tp, use_container_width=True)
                    meta = []
                    if r["kind"]:
                        meta.append(r["kind"])
                    if r["item_count"]:
                        meta.append(f"{r['item_count']}点")
                    if r["year_from"] or r["year_to"]:
                        meta.append(f"{r['year_from']}〜{r['year_to']}")
                    if meta:
                        st.caption(" / ".join(meta))
                with right:
                    if r["summary"]:
                        st.write(r["summary"])
                    if r["properties"]:
                        st.markdown("**物件**　" + "、".join(r["properties"].split("\n")))
                    if r["doc_types"]:
                        st.markdown("**種別**　" + r["doc_types"].replace(",", "、"))
                    if r["contents"]:
                        st.markdown("**中身**")
                        st.text(r["contents"])

                with st.form(f"editfile_{r['id']}"):
                    st.markdown("**✏️ この詳細を直す**")
                    e1, e2 = st.columns([3, 1])
                    lb = e1.text_input("見出し", r["label"], key=f"e_lb_{r['id']}")
                    kd = e2.selectbox(
                        "入れ物", db.KINDS,
                        index=db.KINDS.index(r["kind"]) if r["kind"] in db.KINDS else 0,
                        key=f"e_kd_{r['id']}")
                    e3, e4, e5 = st.columns([2, 2, 1])
                    lc = e3.selectbox(
                        "保管場所", ids,
                        index=ids.index(r["location_id"]) if r["location_id"] in ids else 0,
                        format_func=lambda x: labels[x], key=f"e_lc_{r['id']}")
                    sp = e4.text_input("場所の中の位置", r["spot"], key=f"e_sp_{r['id']}")
                    ip = e5.selectbox(
                        "重要度", IMPORTANCE_OPTS,
                        index=IMPORTANCE_OPTS.index(r["importance"]) if r["importance"] in IMPORTANCE_OPTS else 0,
                        format_func=imp_label, key=f"e_ip_{r['id']}")
                    e6, e7, e8 = st.columns(3)
                    yf2 = e6.text_input("古い年", r["year_from"], key=f"e_yf_{r['id']}")
                    yt2 = e7.text_input("新しい年", r["year_to"], key=f"e_yt_{r['id']}")
                    ct2 = e8.text_input("点数", r["item_count"], key=f"e_ct_{r['id']}")
                    dt2 = st.multiselect(
                        "種別", db.all_doc_types(),
                        default=[t for t in r["doc_types"].split(",") if t],
                        key=f"e_dt_{r['id']}")
                    pr2 = st.text_area("関係する物件（1行1件）", r["properties"],
                                       height=80, key=f"e_pr_{r['id']}")
                    cn2 = st.text_area("中身の目録（1行1件）", r["contents"],
                                       height=180, key=f"e_cn_{r['id']}")
                    sm2 = st.text_input("ひとことメモ", r["summary"], key=f"e_sm_{r['id']}")
                    nt2 = st.text_area("備考", r["note"], height=68, key=f"e_nt_{r['id']}")
                    s1, s2 = st.columns(2)
                    _save_click = s1.form_submit_button(
                        "💾 保存", type="primary", use_container_width=True)
                    _del_click = s2.form_submit_button(
                        "🗑 このファイルを削除", use_container_width=True)

                if _save_click:
                    db.update_file(r["id"], {
                        "label": lb, "kind": kd, "location_id": lc, "spot": sp,
                        "properties": pr2, "doc_types": ",".join(dt2),
                        "year_from": yf2, "year_to": yt2, "item_count": ct2,
                        "contents": cn2, "summary": sm2, "importance": ip, "note": nt2,
                    })
                    for p in pr2.splitlines():
                        db.add_property(p)
                    st.success("保存しました")
                    st.rerun()
                if _del_click:
                    st.session_state["file_del_pending"] = r["id"]
                    st.rerun()

                # 削除は一段確認を挟む（誤操作で消えないように）
                if st.session_state.get("file_del_pending") == r["id"]:
                    st.markdown(f"**⚠️ 「{r['label']}」を削除しますか？**（元に戻せません）")
                    fd1, fd2 = st.columns(2)
                    if fd1.button("削除する", type="primary", use_container_width=True,
                                  key=f"fdel_yes_{r['id']}"):
                        db.delete_file(r["id"])
                        st.session_state.pop("file_del_pending", None)
                        st.warning("削除しました")
                        st.rerun()
                    if fd2.button("やめる", use_container_width=True, key=f"fdel_no_{r['id']}"):
                        st.session_state.pop("file_del_pending", None)
                        st.rerun()

        st.divider()
        exp = pd.DataFrame([
            {"重要度": r["importance"], "見出し": r["label"],
             "保管場所": r["location_name"] or "", "位置": r["spot"],
             "入れ物": r["kind"], "物件": r["properties"].replace("\n", "、"),
             "種別": r["doc_types"], "年": f'{r["year_from"]}〜{r["year_to"]}',
             "点数": r["item_count"], "中身": r["contents"].replace("\n", " / ")}
            for r in rows
        ])
        st.download_button(
            "この結果をCSVで書き出す",
            exp.to_csv(index=False).encode("utf-8-sig"),
            file_name="書類ファイル一覧.csv", mime="text/csv",
        )


# ================= 設定 =================
with tab_conf:
    st.subheader("設定")

    st.markdown("#### 物件マスタ")
    st.caption("検索の絞り込みに使います。ファイルを登録すると自動でも増えます。")

    p1, p2 = st.columns([2, 1])
    with p1:
        newp = st.text_input("物件名を追加", key="newp", placeholder="角屋（横堤）モータープール")
        if st.button("追加する") and newp.strip():
            db.add_property(newp)
            st.rerun()

        up = st.file_uploader(
            "管理物件台帳などのExcel/CSVから一括取込", type=["xlsx", "xls", "csv"], key="propfile"
        )
        if up is not None:
            try:
                if up.name.lower().endswith(".csv"):
                    pdf_ = pd.read_csv(io.BytesIO(up.getvalue()))
                else:
                    pdf_ = pd.read_excel(io.BytesIO(up.getvalue()))
                col = st.selectbox("物件名が入っている列", list(pdf_.columns), key="propcol")
                if st.button("この列を取り込む", type="primary"):
                    added = 0
                    for v in pdf_[col].dropna().astype(str):
                        if db.add_property(v.strip()):
                            added += 1
                    st.success(f"{added} 件を取り込みました")
                    st.rerun()
            except Exception as e:
                st.error(f"読み込めませんでした: {type(e).__name__}")

    with p2:
        props = db.list_properties()
        st.metric("登録物件数", len(props))
        if props:
            dele = st.selectbox("削除する物件", ["—"] + [r["name"] for r in props], key="delp")
            if dele != "—" and st.button("削除", key="delpbtn"):
                pid = next(r["id"] for r in props if r["name"] == dele)
                db.delete_property(pid)
                st.rerun()

    st.divider()
    st.markdown("#### バックアップ")
    st.caption(
        f"データは `{db.DB_PATH}` に保存されています。"
        "物件名や所在を含むため、このフォルダはGitには含めていません。"
    )
    allrows = db.search_files()
    if allrows:
        exp = pd.DataFrame([dict(r) for r in allrows])
        st.download_button(
            "全ファイルをCSVで書き出す",
            exp.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"書類キャビネット_{date.today()}.csv", mime="text/csv",
        )
    if os.path.exists(db.DB_PATH):
        with open(db.DB_PATH, "rb") as f:
            st.download_button(
                "データベースファイルをダウンロード", f.read(),
                file_name=f"cabinet_{date.today()}.db", mime="application/octet-stream",
            )
