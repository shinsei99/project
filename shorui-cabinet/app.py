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

if not ai_reader.claude_available():
    st.sidebar.error("claude CLI が見つかりません。AI読み取りは使えませんが、手入力での登録・検索は可能です。")

_inbox_n = len(list_inbox_batches())
_inbox_label = f"📁 取込（{_inbox_n}）" if _inbox_n else "📁 取込"
tab_add, tab_inbox, tab_find, tab_pdf, tab_loc, tab_conf = st.tabs(
    ["📥 ファイルを登録", _inbox_label, "🔍 さがす", "📄 PDFを整理", "🗄 保管場所", "⚙️ 設定"]
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
            m1, m2 = st.columns([2, 2])
            common = m1.selectbox(
                "保管場所（全部まとめて）", ids, format_func=lambda x: labels[x],
                key="batchloc", help="ここで選ぶと下の表の全行に入ります。行ごとに変えられます。",
            )
            common_spot = m2.text_input("場所の中の位置（全部まとめて）", key="batchspot",
                                        placeholder="例: 上から2段目 左端")

            rows = st.data_editor(
                pd.DataFrame([{
                    "登録": True,
                    "見出し": it["draft"].get("label", it["name"]),
                    "保管場所": labels[common],
                    "位置": common_spot,
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


# ================= 取込（スマホから届いた束） =================
with tab_inbox:
    st.subheader("スマホから届いた束を取り込む")
    st.caption(
        "スマホ用アプリ（shorui-mobile）が Dropbox の「書類取込」に送った束を、"
        "1冊ずつ読み取って登録します。登録した束は自動で「_済」へ移します。"
    )
    st.caption(f"監視フォルダ: `{INBOX_DIR}`")

    if not os.path.isdir(INBOX_DIR):
        st.warning(
            "取込フォルダが見つかりません。Dropboxの同期先が違う場合は、環境変数 "
            "`SHORUI_INBOX` にフォルダのパスを設定してください。"
        )
    else:
        batches = list_inbox_batches()
        r1, r2 = st.columns([1, 4])
        if r1.button("🔄 更新", use_container_width=True):
            st.rerun()
        if not batches:
            st.info("未処理の束はありません。スマホから撮って送ると、ここに出ます。")
        else:
            names = [b["name"] for b in batches]
            def _blabel(n: str) -> str:
                b = next(x for x in batches if x["name"] == n)
                prop = (b["meta"].get("property") or "").strip()
                return f"{n}　—　{prop}（{len(b['images'])}枚）" if prop else f"{n}（{len(b['images'])}枚）"

            pick = st.selectbox("取り込む束", names, format_func=_blabel)
            batch = next(x for x in batches if x["name"] == pick)
            meta = batch["meta"]

            with st.container(border=True):
                if meta.get("property"):
                    st.markdown(f"**物件名・件名:** {meta['property']}")
                if meta.get("memo"):
                    st.caption(f"メモ: {meta['memo']}")
                if meta.get("capturedAt"):
                    st.caption(f"撮影: {meta['capturedAt']}")

                cols = st.columns(4)
                for i, fn in enumerate(batch["images"][:8]):
                    if fn.lower().endswith(".pdf"):
                        cols[i % 4].caption(f"📄 {fn}")
                        continue
                    try:
                        cols[i % 4].image(os.path.join(batch["path"], fn), use_container_width=True)
                    except Exception:
                        cols[i % 4].caption(fn)

            dkey = f"inbox_draft_{pick}"
            g1, g2 = st.columns([1, 3])
            read = g1.button(
                "🤖 読み取って目録化", type="primary",
                disabled=not ai_reader.claude_available(),
                use_container_width=True,
            )
            g2.caption("写真の枚数により1〜2分ほどかかります（正確さ優先で上位モデルを使用）")

            if read:
                uploads = []
                for fn in batch["images"]:
                    with open(os.path.join(batch["path"], fn), "rb") as fh:
                        uploads.append((fh.read(), fn))
                msgs: list = []
                with st.spinner("読み取り中…"):
                    got = ai_reader.read_file_contents(uploads, note=msgs.append)
                if msgs:
                    st.info("\n".join(msgs))
                if got:
                    # 物件名がスマホ入力にあればAI結果に補う
                    prop = (meta.get("property") or "").strip()
                    if prop and prop not in got.get("properties", []):
                        got["properties"] = [prop] + got.get("properties", [])
                    st.session_state[dkey] = got
                    st.rerun()
                else:
                    st.error("読み取れませんでした。手入力で登録するか、撮り直してください。")

            draft = st.session_state.get(dkey)
            if draft is not None:
                if draft.get("confidence"):
                    lv = draft["confidence"]
                    (st.success if lv == "high" else st.warning)(
                        f"AIの読み取り結果を反映しました（{CONF_LABEL.get(lv, '')}）"
                        + ("" if lv == "high" else " — 物件名と固有名詞は目視で確認してください")
                    )
                with st.container(border=True):
                    st.markdown("**内容を確認して登録**")
                    ids, labels = location_options()
                    types = db.all_doc_types()

                    f1, f2 = st.columns([3, 1])
                    label = f1.text_input("ファイルの見出し *", draft.get("label", ""), key=f"lbl_{pick}")
                    kind = f2.selectbox("入れ物の種類", db.KINDS, key=f"knd_{pick}")

                    p1, p2, p3 = st.columns([2, 2, 1])
                    loc = p1.selectbox("保管場所 *", ids, format_func=lambda x: labels[x], key=f"loc_{pick}")
                    spot = p2.text_input("場所の中の位置", key=f"spt_{pick}", placeholder="例: 上から2段目 左端")
                    with p3:
                        newloc = st.text_input("場所を追加", key=f"nl_{pick}", placeholder="本社3F 書庫A")
                        if st.button("追加", key=f"nlb_{pick}", use_container_width=True) and newloc.strip():
                            db.add_location(newloc)
                            st.rerun()

                    q1, q2, q3 = st.columns(3)
                    yf = q1.text_input("いちばん古い年", draft.get("year_from", ""), key=f"yf_{pick}")
                    yt = q2.text_input("いちばん新しい年", draft.get("year_to", ""), key=f"yt_{pick}")
                    cnt = q3.text_input("点数（おおよそ）", key=f"cnt_{pick}")

                    dts = st.multiselect(
                        "入っている書類の種別", types,
                        default=[t for t in draft.get("doc_types", []) if t in types],
                        key=f"dts_{pick}",
                    )
                    props = st.text_area(
                        "関係する物件（1行1件）", "\n".join(draft.get("properties", [])),
                        height=80, key=f"prp_{pick}",
                    )
                    contents = st.text_area(
                        "中身の目録（1行1件）", "\n".join(draft.get("contents", [])),
                        height=180, key=f"cnt2_{pick}",
                    )
                    summary = st.text_input("ひとことメモ", draft.get("summary", ""), key=f"sum_{pick}")

                    if st.button("✅ 登録して束を「_済」へ移す", type="primary", key=f"reg_{pick}",
                                 use_container_width=True):
                        if not label.strip():
                            st.error("ファイルの見出しを入れてください")
                        else:
                            # 1枚目をサムネイルにする
                            thumb = ""
                            first = batch["images"][0]
                            if not first.lower().endswith(".pdf"):
                                safe = f"file_{abs(hash(pick))}.jpg"
                                with open(os.path.join(batch["path"], first), "rb") as fh:
                                    if ai_reader.make_thumb(fh.read(), first,
                                                            os.path.join(db.THUMB_DIR, safe)):
                                        thumb = safe
                            db.add_file({
                                "label": label, "kind": kind, "location_id": loc, "spot": spot,
                                "properties": props, "doc_types": ",".join(dts),
                                "year_from": yf, "year_to": yt, "item_count": cnt,
                                "contents": contents, "summary": summary, "thumb": thumb,
                            })
                            for p in props.splitlines():
                                db.add_property(p)
                            # 束を _済 へ退避
                            os.makedirs(INBOX_DONE, exist_ok=True)
                            dest = os.path.join(INBOX_DONE, pick)
                            if os.path.exists(dest):
                                dest = dest + f"_{abs(hash(pick)) % 10000}"
                            try:
                                shutil.move(batch["path"], dest)
                            except Exception as e:
                                st.warning(f"登録は済みましたが、束の移動に失敗しました（{type(e).__name__}）。手で「_済」へ移してください。")
                            st.session_state.pop(dkey, None)
                            st.success(f"「{label}」を登録しました")
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
    st.caption("「本社3F 書庫A / 棚2」のように、探しに行ける粒度で登録してください。")

    # --- 棚番号を後回しにして登録した分を、あとでまとめて割り当てる ---
    unplaced = db.list_unplaced()
    if unplaced:
        with st.container(border=True):
            st.markdown(f"**📦 場所がまだ決まっていないファイル — {len(unplaced)} 冊**")
            st.caption(
                "登録のときに場所を決めなくても構いません。"
                "棚に戻すときに、ここでまとめて割り当ててください。"
            )
            uids, ulabels = location_options()
            real_ids = [i for i in uids if i]
            if not real_ids:
                st.info("先に下の欄で保管場所を1つ登録してください。")
            else:
                w1, w2 = st.columns([2, 2])
                to_loc = w1.selectbox("この場所に入れる", real_ids,
                                      format_func=lambda x: ulabels[x], key="uploc")
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
                    st.success(f"{n} 冊を「{ulabels[to_loc]}」にしました。")
                    st.rerun()
                if v2.button("すべて選ぶ / すべて外す"):
                    st.session_state.pop("unplaced_ed", None)
                    st.rerun()

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
