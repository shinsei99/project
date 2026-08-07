# -*- coding: utf-8 -*-
"""書類キャビネット — 紙の書類が「どこにあるか」を管理するアプリ。

管理の単位は **ファイル1冊（クリアファイル・バインダー・箱）**。書類1枚ずつは登録しない。
中身をパラパラ数枚撮ると claude CLI が目録を起こすので、人の作業は1冊あたり1回で済む。

起動: ./run.sh → http://localhost:8528
"""

# 実行環境は system python 3.9（他アプリと同じ）。新しい型注釈を書けるようにする。
from __future__ import annotations

import io
import os
from datetime import date

import pandas as pd
import streamlit as st

import ai_reader
import db

st.set_page_config(page_title="書類キャビネット", page_icon="🗄", layout="wide")

db.init_db()

ACCEPT = ["pdf", "jpg", "jpeg", "png", "webp", "heic"]
CONF_LABEL = {"high": "確度 高", "medium": "確度 中", "low": "確度 低"}


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

if not ai_reader.claude_available():
    st.sidebar.error("claude CLI が見つかりません。AI読み取りは使えませんが、手入力での登録・検索は可能です。")

tab_add, tab_find, tab_loc, tab_conf = st.tabs(
    ["📥 ファイルを登録", "🔍 さがす", "🗄 保管場所", "⚙️ 設定"]
)


# ================= 登録 =================
with tab_add:
    st.subheader("ファイルを1冊登録する")
    st.caption(
        "クリアファイル1冊・バインダー1冊・箱1つが登録の単位です。"
        "中身をパラパラと数枚撮って読み込ませると、目録が自動で作られます。"
    )

    draft = st.session_state.setdefault("draft", draft_default())

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
            newloc = st.text_input("場所を追加", placeholder="本社3F 書庫A")
            if st.button("追加", use_container_width=True) and newloc.strip():
                db.add_location(newloc)
                st.rerun()

        h1, h2, h3 = st.columns([1, 1, 1])
        yf = h1.text_input("いちばん古い年", draft.get("year_from", ""), placeholder="2019")
        yt = h2.text_input("いちばん新しい年", draft.get("year_to", ""), placeholder="2026")
        cnt = h3.text_input("点数（おおよそ）", placeholder="12")

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
                    "contents": contents, "summary": summary,
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


# ================= さがす =================
with tab_find:
    st.subheader("さがす")
    st.caption("物件名や書類名で引くと、それが入っているファイルと置き場所が出ます。")

    ids, labels = location_options()
    q1, q2, q3, q4 = st.columns([3, 2, 2, 2])
    kw = q1.text_input("キーワード（スペース区切りでAND検索）", placeholder="例: 角屋 契約")
    types = ["（すべて）"] + db.all_doc_types()
    ft = q2.selectbox("書類の種別", types)
    fp = q3.selectbox("物件", ["（すべて）"] + property_names())
    fl = q4.selectbox("保管場所", ids, format_func=lambda x: labels[x] if x else "（すべて）")

    rows = db.search_files(
        keyword=kw,
        doc_type="" if ft == "（すべて）" else ft,
        property_name="" if fp == "（すべて）" else fp,
        location_id=fl,
    )
    st.caption(f"{len(rows):,} 件のファイル")

    if not rows:
        st.info("該当なし。登録タブから追加してください。")
    else:
        for r in rows:
            place = r["location_name"] or "（保管場所 未設定）"
            spot = f"／{r['spot']}" if r["spot"] else ""
            with st.expander(f"📁 {r['label']}　—　📍 {place}{spot}"):
                left, right = st.columns([1, 3])
                with left:
                    tp = thumb_path(r["thumb"])
                    if tp:
                        st.image(tp, use_container_width=True)
                    st.markdown(f"**📍 {place}**")
                    if r["spot"]:
                        st.caption(r["spot"])
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

                if st.button("✏️ このファイルを編集", key=f"ed{r['id']}"):
                    st.session_state["editing"] = r["id"]
                    st.rerun()

        # --- 編集 ---
        if st.session_state.get("editing"):
            rec = db.get_file(st.session_state["editing"])
            if rec:
                st.divider()
                st.markdown(f"#### ✏️ 編集: {rec['label']}")
                eids, elabels = location_options()
                etypes = db.all_doc_types()
                with st.form("editfile"):
                    e1, e2 = st.columns([3, 1])
                    lb = e1.text_input("見出し", rec["label"])
                    kd = e2.selectbox(
                        "入れ物", db.KINDS,
                        index=db.KINDS.index(rec["kind"]) if rec["kind"] in db.KINDS else 0,
                    )
                    e3, e4 = st.columns(2)
                    lc = e3.selectbox(
                        "保管場所", eids,
                        index=eids.index(rec["location_id"]) if rec["location_id"] in eids else 0,
                        format_func=lambda x: elabels[x],
                    )
                    sp = e4.text_input("場所の中の位置", rec["spot"])
                    e5, e6, e7 = st.columns(3)
                    yf2 = e5.text_input("古い年", rec["year_from"])
                    yt2 = e6.text_input("新しい年", rec["year_to"])
                    ct2 = e7.text_input("点数", rec["item_count"])
                    dt2 = st.multiselect(
                        "種別", etypes,
                        default=[t for t in rec["doc_types"].split(",") if t in etypes],
                    )
                    pr2 = st.text_area("関係する物件（1行1件）", rec["properties"], height=80)
                    cn2 = st.text_area("中身の目録（1行1件）", rec["contents"], height=180)
                    sm2 = st.text_input("ひとことメモ", rec["summary"])
                    nt2 = st.text_area("備考", rec["note"], height=68)

                    s1, s2, s3 = st.columns(3)
                    if s1.form_submit_button("💾 保存", type="primary", use_container_width=True):
                        db.update_file(rec["id"], {
                            "label": lb, "kind": kd, "location_id": lc, "spot": sp,
                            "properties": pr2, "doc_types": ",".join(dt2),
                            "year_from": yf2, "year_to": yt2, "item_count": ct2,
                            "contents": cn2, "summary": sm2, "note": nt2,
                        })
                        for p in pr2.splitlines():
                            db.add_property(p)
                        st.session_state.pop("editing")
                        st.success("保存しました")
                        st.rerun()
                    if s2.form_submit_button("🗑 削除", use_container_width=True):
                        db.delete_file(rec["id"])
                        st.session_state.pop("editing")
                        st.warning("削除しました")
                        st.rerun()
                    if s3.form_submit_button("閉じる", use_container_width=True):
                        st.session_state.pop("editing")
                        st.rerun()

        st.divider()
        exp = pd.DataFrame([
            {"見出し": r["label"], "保管場所": r["location_name"] or "", "位置": r["spot"],
             "入れ物": r["kind"], "物件": r["properties"].replace("\n", "、"),
             "種別": r["doc_types"], "年": f"{r['year_from']}〜{r['year_to']}",
             "点数": r["item_count"], "中身": r["contents"].replace("\n", " / ")}
            for r in rows
        ])
        st.download_button(
            "この結果をCSVで書き出す",
            exp.to_csv(index=False).encode("utf-8-sig"),
            file_name="書類ファイル一覧.csv", mime="text/csv",
        )


# ================= 保管場所 =================
with tab_loc:
    st.subheader("保管場所")
    st.caption("「本社3F 書庫A / 棚2」のように、探しに行ける粒度で登録してください。")

    with st.form("add_loc"):
        a1, a2, a3 = st.columns([2, 3, 1])
        name = a1.text_input("場所の名前 *", placeholder="本社3F 書庫A / 棚2")
        note = a2.text_input("メモ", placeholder="鍵は総務が管理 など")
        a3.markdown("<br>", unsafe_allow_html=True)
        if a3.form_submit_button("追加", type="primary", use_container_width=True):
            if name.strip():
                db.add_location(name, note)
                st.rerun()
            else:
                st.error("場所の名前を入れてください")

    counts = db.location_counts()
    locs = db.list_locations()
    if not locs:
        st.info("まだ保管場所がありません。上から追加してください。")
    for r in locs:
        with st.expander(f"📍 {r['name']}　（ファイル {counts.get(r['id'], 0)} 冊）"):
            with st.form(f"loc_{r['id']}"):
                g1, g2, g3 = st.columns([2, 3, 1])
                nm = g1.text_input("名前", r["name"])
                nt = g2.text_input("メモ", r["note"])
                so = g3.number_input("並び順", value=r["sort"], step=1)
                h1, h2 = st.columns(2)
                if h1.form_submit_button("💾 保存", use_container_width=True):
                    db.update_location(r["id"], nm, nt, int(so))
                    st.rerun()
                if h2.form_submit_button("🗑 場所を削除", use_container_width=True):
                    db.delete_location(r["id"])
                    st.warning("削除しました（この場所のファイルは「未設定」になります）")
                    st.rerun()

            inner = db.search_files(location_id=r["id"])
            if inner:
                st.dataframe(
                    pd.DataFrame([
                        {"見出し": x["label"], "入れ物": x["kind"], "位置": x["spot"],
                         "物件": x["properties"].replace("\n", "、")}
                        for x in inner
                    ]),
                    use_container_width=True, hide_index=True,
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
