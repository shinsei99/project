# -*- coding: utf-8 -*-
"""書類キャビネット — 紙の書類が「どこにあるか」を管理するアプリ。

写真やPDFを放り込むと claude CLI が中身を読んで種別・物件名・日付を自動で埋めるので、
入力は「保管場所を選ぶだけ」で済む。スキャン代行から返ってきたPDFの一括取込にも対応。

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


# ---------------- 共通の小道具 ----------------

def location_options() -> tuple[list[int | None], dict]:
    """保管場所のselectbox用（先頭は未設定）。"""
    locs = db.list_locations()
    ids: list[int | None] = [None] + [r["id"] for r in locs]
    labels = {None: "（未設定）"}
    labels.update({r["id"]: r["name"] for r in locs})
    return ids, labels


def property_names() -> list[str]:
    return [r["name"] for r in db.list_properties()]


def thumb_path(name: str) -> str | None:
    if not name:
        return None
    p = os.path.join(db.THUMB_DIR, name)
    return p if os.path.exists(p) else None


# ---------------- サイドバー ----------------

s = db.stats()
st.sidebar.title("🗄 書類キャビネット")
st.sidebar.caption("紙の書類の置き場所を記録・検索する")
c1, c2 = st.sidebar.columns(2)
c1.metric("登録書類", f"{s['documents']:,}")
c2.metric("保管場所", f"{s['locations']:,}")
if s["unplaced"]:
    st.sidebar.warning(f"保管場所が未設定の書類が {s['unplaced']} 件あります")

if not ai_reader.claude_available():
    st.sidebar.error(
        "claude CLI が見つかりません。AI読み取りは使えませんが、手入力での登録・検索は可能です。"
    )

tab_add, tab_find, tab_loc, tab_conf = st.tabs(
    ["📥 登録", "🔍 さがす", "🗄 保管場所", "⚙️ 設定"]
)


# ================= 登録 =================
with tab_add:
    st.subheader("書類を登録する")
    st.caption(
        "写真やPDFをまとめて放り込むと、AIが1件ずつ「何の書類か」を読み取ります。"
        "スキャン代行から返ってきたPDFもそのまま投入できます。"
    )

    files = st.file_uploader(
        "書類の写真・PDF（複数可）",
        type=ACCEPT,
        accept_multiple_files=True,
        key="uploader",
    )

    col_a, col_b = st.columns([1, 3])
    with col_a:
        run = st.button(
            "🤖 AIで読み取る",
            type="primary",
            disabled=not files or not ai_reader.claude_available(),
            use_container_width=True,
        )
    with col_b:
        st.caption(
            "※ 1件あたり数十秒かかります（スキャン画像は向きの自動補正が入るためもう少し）"
        )

    if run and files:
        pending = []
        bar = st.progress(0.0, text="読み取りを開始します…")
        for i, f in enumerate(files):
            data = f.getvalue()
            msgs: list[str] = []
            bar.progress(i / len(files), text=f"{f.name} を読み取り中…（{i + 1}/{len(files)}）")
            parsed = ai_reader.read_document(data, f.name, note=msgs.append)

            # サムネイルは読み取りの成否にかかわらず作る（一覧で見分けるため）
            thumb_name = ""
            safe = f"doc_{abs(hash(f.name + str(i)))}.jpg"
            if ai_reader.make_thumb(data, f.name, os.path.join(db.THUMB_DIR, safe)):
                thumb_name = safe

            pending.append(
                {
                    "filename": f.name,
                    "thumb": thumb_name,
                    "messages": msgs,
                    "data": parsed
                    or {
                        "doc_type": "",
                        "title": os.path.splitext(f.name)[0],
                        "property_name": "",
                        "doc_date": "",
                        "counterparty": "",
                        "summary": "",
                        "confidence": "low",
                    },
                    "ok": parsed is not None,
                }
            )
        bar.progress(1.0, text="読み取り完了")
        st.session_state["pending"] = pending

    pending = st.session_state.get("pending", [])

    if pending:
        st.divider()
        ng = [p for p in pending if not p["ok"]]
        st.success(f"{len(pending)} 件を読み取りました" + (f"（うち {len(ng)} 件は自動判別できず）" if ng else ""))

        st.markdown("#### 保管場所（まとめて指定）")
        ids, labels = location_options()
        lc1, lc2, lc3 = st.columns([2, 2, 1])
        bulk_loc = lc1.selectbox(
            "保管場所", ids, format_func=lambda x: labels[x], key="bulk_loc"
        )
        bulk_container = lc2.text_input(
            "ファイル名・箱番号", key="bulk_container", placeholder="例: 契約書ファイル①"
        )
        with lc3:
            st.caption("場所が未登録なら")
            new_loc = st.text_input("新しい場所", key="new_loc_inline", label_visibility="collapsed",
                                    placeholder="本社3F 書庫A")
            if st.button("追加", key="add_loc_inline", use_container_width=True) and new_loc.strip():
                db.add_location(new_loc)
                st.rerun()

        st.markdown("#### 読み取り結果（必要なら直してください）")
        types = db.all_doc_types()
        props = property_names()

        for idx, p in enumerate(pending):
            d = p["data"]
            mark = "" if p["ok"] else "⚠️ "
            conf = {"high": "確度 高", "medium": "確度 中", "low": "確度 低"}.get(
                d.get("confidence", "medium"), ""
            )
            with st.expander(
                f"{mark}{idx + 1}. {d.get('title') or p['filename']}　—　{d.get('doc_type') or '種別不明'}"
                f"　/　{d.get('property_name') or '物件不明'}　（{conf}）",
                expanded=(len(pending) <= 3 or not p["ok"]),
            ):
                if p["messages"]:
                    st.info("\n".join(p["messages"]))

                img_col, form_col = st.columns([1, 3])
                with img_col:
                    tp = thumb_path(p["thumb"])
                    if tp:
                        st.image(tp, use_container_width=True)
                    st.caption(p["filename"])

                with form_col:
                    r1c1, r1c2 = st.columns(2)
                    d["title"] = r1c1.text_input("表題", d.get("title", ""), key=f"t{idx}")
                    tsel = d.get("doc_type", "")
                    d["doc_type"] = r1c2.selectbox(
                        "種別",
                        types,
                        index=types.index(tsel) if tsel in types else types.index("その他"),
                        key=f"ty{idx}",
                    )

                    r2c1, r2c2, r2c3 = st.columns([2, 1, 2])
                    d["property_name"] = r2c1.text_input(
                        "物件名", d.get("property_name", ""), key=f"p{idx}",
                        help="登録済みの物件名は設定タブで管理できます",
                    )
                    if props:
                        pick = r2c2.selectbox(
                            "候補から", ["—"] + props, key=f"pp{idx}", label_visibility="visible"
                        )
                        if pick != "—":
                            d["property_name"] = pick
                    d["doc_date"] = r2c3.text_input(
                        "日付", d.get("doc_date", ""), key=f"dt{idx}", placeholder="2026-08-07"
                    )

                    d["counterparty"] = st.text_input(
                        "相手先・当事者", d.get("counterparty", ""), key=f"c{idx}"
                    )
                    d["summary"] = st.text_area(
                        "内容メモ", d.get("summary", ""), key=f"s{idx}", height=68
                    )

        st.divider()
        b1, b2 = st.columns([1, 4])
        if b1.button("✅ すべて登録する", type="primary", use_container_width=True):
            n = 0
            for p in pending:
                d = dict(p["data"])
                d["location_id"] = st.session_state.get("bulk_loc")
                d["container"] = st.session_state.get("bulk_container", "")
                d["thumb"] = p["thumb"]
                db.add_document(d)
                # 物件名が新規ならマスタにも足しておく（次回から候補に出る）
                if d.get("property_name"):
                    db.add_property(d["property_name"])
                n += 1
            st.session_state["pending"] = []
            st.success(f"{n} 件を登録しました")
            st.rerun()
        if b2.button("破棄", use_container_width=False):
            st.session_state["pending"] = []
            st.rerun()

    # --- 手入力 ---
    st.divider()
    with st.expander("✍️ 写真を使わず手入力で1件だけ登録する"):
        ids, labels = location_options()
        with st.form("manual"):
            m1, m2 = st.columns(2)
            title = m1.text_input("表題 *")
            types = db.all_doc_types()
            doc_type = m2.selectbox("種別", types, index=types.index("その他"))
            m3, m4, m5 = st.columns(3)
            prop = m3.text_input("物件名")
            ddate = m4.text_input("日付", placeholder="2026-08-07")
            cp = m5.text_input("相手先")
            m6, m7, m8 = st.columns(3)
            loc = m6.selectbox("保管場所", ids, format_func=lambda x: labels[x])
            cont = m7.text_input("ファイル名・箱番号")
            qty = m8.text_input("部数など")
            memo = st.text_area("メモ", height=68)
            if st.form_submit_button("登録する", type="primary"):
                if not title.strip():
                    st.error("表題を入れてください")
                else:
                    db.add_document({
                        "title": title, "doc_type": doc_type, "property_name": prop,
                        "doc_date": ddate, "counterparty": cp, "summary": memo,
                        "location_id": loc, "container": cont, "quantity": qty,
                    })
                    if prop.strip():
                        db.add_property(prop)
                    st.success("登録しました")
                    st.rerun()


# ================= さがす =================
with tab_find:
    st.subheader("書類をさがす")

    ids, labels = location_options()
    f1, f2, f3, f4 = st.columns([3, 2, 2, 2])
    kw = f1.text_input("キーワード（スペース区切りでAND検索）", placeholder="例: 角屋 契約")
    types = ["（すべて）"] + db.all_doc_types()
    ft = f2.selectbox("種別", types)
    fp = f3.selectbox("物件", ["（すべて）"] + property_names())
    fl = f4.selectbox("保管場所", ids, format_func=lambda x: labels[x] if x else "（すべて）")

    rows = db.search_documents(
        keyword=kw,
        doc_type="" if ft == "（すべて）" else ft,
        property_name="" if fp == "（すべて）" else fp,
        location_id=fl,
    )

    st.caption(f"{len(rows):,} 件")

    if not rows:
        st.info("該当する書類がありません。登録タブから追加してください。")
    else:
        df = pd.DataFrame(
            [
                {
                    "id": r["id"],
                    "表題": r["title"],
                    "種別": r["doc_type"],
                    "物件": r["property_name"],
                    "日付": r["doc_date"],
                    "📍保管場所": r["location_name"] or "（未設定）",
                    "ファイル・箱": r["container"],
                    "相手先": r["counterparty"],
                }
                for r in rows
            ]
        )
        st.dataframe(
            df.drop(columns=["id"]),
            use_container_width=True,
            hide_index=True,
            height=min(460, 60 + 35 * len(df)),
        )

        st.download_button(
            "この結果をCSVで書き出す",
            df.drop(columns=["id"]).to_csv(index=False).encode("utf-8-sig"),
            file_name="書類一覧.csv",
            mime="text/csv",
        )

        st.divider()
        st.markdown("#### 詳細・編集")
        pick = st.selectbox(
            "書類を選ぶ",
            [r["id"] for r in rows],
            format_func=lambda i: next(
                f"{r['title']}（{r['property_name'] or '物件なし'}）" for r in rows if r["id"] == i
            ),
        )
        doc = db.get_document(pick)
        if doc:
            dcol1, dcol2 = st.columns([1, 3])
            with dcol1:
                tp = thumb_path(doc["thumb"])
                if tp:
                    st.image(tp, use_container_width=True)
                st.metric("📍 保管場所", doc["location_name"] or "未設定")
                if doc["container"]:
                    st.caption(f"ファイル・箱: {doc['container']}")

            with dcol2:
                with st.form(f"edit_{pick}"):
                    e1, e2 = st.columns(2)
                    title = e1.text_input("表題", doc["title"])
                    tlist = db.all_doc_types()
                    doc_type = e2.selectbox(
                        "種別", tlist,
                        index=tlist.index(doc["doc_type"]) if doc["doc_type"] in tlist else tlist.index("その他"),
                    )
                    e3, e4, e5 = st.columns(3)
                    prop = e3.text_input("物件名", doc["property_name"])
                    ddate = e4.text_input("日付", doc["doc_date"])
                    cp = e5.text_input("相手先", doc["counterparty"])
                    e6, e7, e8 = st.columns(3)
                    lids, llabels = location_options()
                    loc = e6.selectbox(
                        "保管場所", lids,
                        index=lids.index(doc["location_id"]) if doc["location_id"] in lids else 0,
                        format_func=lambda x: llabels[x],
                    )
                    cont = e7.text_input("ファイル名・箱番号", doc["container"])
                    qty = e8.text_input("部数など", doc["quantity"])
                    memo = st.text_area("内容メモ", doc["summary"], height=80)
                    note = st.text_area("備考", doc["note"], height=68)

                    s1, s2 = st.columns([1, 1])
                    if s1.form_submit_button("💾 保存", type="primary", use_container_width=True):
                        db.update_document(pick, {
                            "title": title, "doc_type": doc_type, "property_name": prop,
                            "doc_date": ddate, "counterparty": cp, "summary": memo,
                            "location_id": loc, "container": cont, "quantity": qty, "note": note,
                        })
                        st.success("保存しました")
                        st.rerun()
                    if s2.form_submit_button("🗑 削除", use_container_width=True):
                        db.delete_document(pick)
                        st.warning("削除しました")
                        st.rerun()


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
        with st.expander(f"📍 {r['name']}　（{counts.get(r['id'], 0)} 件）"):
            with st.form(f"loc_{r['id']}"):
                g1, g2, g3 = st.columns([2, 3, 1])
                nm = g1.text_input("名前", r["name"])
                nt = g2.text_input("メモ", r["note"])
                so = g3.number_input("並び順", value=r["sort"], step=1)
                h1, h2 = st.columns([1, 1])
                if h1.form_submit_button("💾 保存", use_container_width=True):
                    db.update_location(r["id"], nm, nt, int(so))
                    st.rerun()
                if h2.form_submit_button("🗑 場所を削除", use_container_width=True):
                    db.delete_location(r["id"])
                    st.warning("削除しました（この場所の書類は「未設定」になります）")
                    st.rerun()

            inner = db.search_documents(location_id=r["id"])
            if inner:
                st.dataframe(
                    pd.DataFrame([
                        {"表題": x["title"], "種別": x["doc_type"], "物件": x["property_name"],
                         "日付": x["doc_date"], "ファイル・箱": x["container"]}
                        for x in inner
                    ]),
                    use_container_width=True, hide_index=True,
                )


# ================= 設定 =================
with tab_conf:
    st.subheader("設定")

    st.markdown("#### 物件マスタ")
    st.caption("登録しておくと、書類登録のときに候補から選べます。書類を登録すると自動でも増えます。")

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
                        v = v.strip()
                        if v and db.add_property(v):
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
        "物件名や書類の所在を含むため、このフォルダはGitには含めていません。"
    )
    allrows = db.search_documents()
    if allrows:
        exp = pd.DataFrame([dict(r) for r in allrows])
        st.download_button(
            "全書類をCSVで書き出す",
            exp.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"書類キャビネット_{date.today()}.csv",
            mime="text/csv",
        )
    if os.path.exists(db.DB_PATH):
        with open(db.DB_PATH, "rb") as f:
            st.download_button(
                "データベースファイルをダウンロード",
                f.read(),
                file_name=f"cabinet_{date.today()}.db",
                mime="application/octet-stream",
            )
