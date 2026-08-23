# -*- coding: utf-8 -*-
"""特約条項ジェネレーター

不動産売買契約の特約条項を、目次から選んで本文をAI生成し、
順番に組み立てて Word / テキストで書き出す業務支援アプリ。

- AI生成はローカルの `claude` CLI を subprocess で呼び出す（APIキー不要）。
- 元資料「特約文目次（資料9-1）」の31カテゴリ・約160項目を内蔵（clauses.py）。
"""

import streamlit as st
import subprocess
import json
import os
from io import BytesIO
from datetime import datetime

from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# 本文生成・Word組版は直下の共有モジュール（重説アプリと同じ実体）。
# ここに再実装しないこと。2箇所に分かれると片方だけ直した特約が契約書に載る。
import os as _os
import sys as _sys

_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)

from tokuyaku_clauses import CATEGORIES, find_item  # noqa: F401
import law_citations  # 引用した法令が実在するかを e-Gov で確かめる（直下の共有モジュール）
from tokuyaku_core import (  # noqa: F401
    CLAUDE_BIN,
    CLAUDE_TIMEOUT,
    STYLE_GUIDE,
    assemble_text,
    build_docx,
    generate_clause,
)


# ── State helpers ────────────────────────────────────────────────────────────
# 本文は条項ごとのウィジェットキー `body_<no>` を唯一の保存先とする。
# AI生成結果は `pending_<no>` に置き、ウィジェット生成前に本文へ反映する
# （Streamlit はウィジェット生成後に同キーの session_state を変更できないため）。
def _txt_key(no: str) -> str:
    return f"body_{no}"


def get_text(no: str) -> str:
    return st.session_state.get(_txt_key(no), "")


def _seed_template(no: str):
    """定型条項の雛形本文を未設定のときだけセットする。"""
    item = find_item(no)
    if item and item.get("body"):
        st.session_state.setdefault(_txt_key(no), item["body"])


def _apply_state_ops():
    """ウィジェット生成前に行う状態操作（全クリア・AI生成結果の反映）。"""
    if st.session_state.pop("_clear_texts", False):
        for k in [k for k in list(st.session_state.keys())
                  if k.startswith(("body_", "extra_", "pending_"))]:
            del st.session_state[k]
        st.session_state.order = []
    for k in [k for k in list(st.session_state.keys()) if k.startswith("pending_")]:
        no = k[len("pending_"):]
        st.session_state[_txt_key(no)] = st.session_state.pop(k)


def _init_state():
    st.session_state.setdefault("order", [])      # list of clause "no"


def add_clause(no: str):
    if no not in st.session_state.order:
        st.session_state.order.append(no)
        _seed_template(no)


def remove_clause(no: str):
    if no in st.session_state.order:
        st.session_state.order.remove(no)


def move_clause(no: str, delta: int):
    order = st.session_state.order
    i = order.index(no)
    j = i + delta
    if 0 <= j < len(order):
        order[i], order[j] = order[j], order[i]


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    st.set_page_config(page_title="特約条項ジェネレーター", page_icon="📑", layout="wide")
    _init_state()
    _apply_state_ops()

    st.title("📑 特約条項ジェネレーター")
    st.caption("不動産売買契約の特約条項を、目次から選んでAIで本文生成 → 並べ替え → Word / テキスト出力")

    with st.sidebar:
        st.header("物件・当事者情報")
        st.caption("入力すると生成本文に反映されます（任意）")
        prop = st.text_input("対象物件（所在地・物件名）", placeholder="例：東京都〇〇区〇〇1-2-3")
        seller = st.text_input("売主の表記", value="売主", placeholder="売主 / 甲")
        buyer = st.text_input("買主の表記", value="買主", placeholder="買主 / 乙")
        st.divider()
        style = st.radio("文体", list(STYLE_GUIDE.keys()), index=0)
        st.divider()
        st.markdown(
            "**⚠️ リーガルチェック必須**\n\n"
            "AIは誤ることがあり、直近の法改正に未対応の場合があります。"
            "生成結果は必ず専門家が確認し、契約書本文と表記を統一してください。"
        )

    ctx = {"property": prop, "seller": seller, "buyer": buyer}
    col_catalog, col_selected = st.columns([1, 1.2], gap="large")

    # ── 左：目次カタログ ──
    with col_catalog:
        st.subheader("① 特約項目を選ぶ")
        q = st.text_input("🔍 キーワード検索", placeholder="例：道路 / 越境 / オーナーチェンジ")
        ql = q.strip().lower()

        std_cat = next((c for c in CATEGORIES if c["no"] == "定"), None)
        if std_cat and st.button("🟢 定型特約をまとめて追加", use_container_width=True):
            for it in std_cat["items"]:
                add_clause(it["no"])
            st.rerun()
        st.caption("🟢＝本文があらかじめ入る定型条項（AI生成不要・そのまま編集可）")

        for cat in CATEGORIES:
            items = cat["items"]
            if ql:
                items = [
                    it for it in items
                    if ql in it["title"].lower() or ql in it["hint"].lower() or ql in cat["name"].lower()
                ]
            if not items:
                continue
            is_std = cat["no"] == "定"
            with st.expander(f"{cat['no']}. {cat['name']}（{len(items)}）", expanded=is_std or bool(ql)):
                for it in items:
                    no = it["no"]
                    has_body = bool(it.get("body"))
                    if has_body:
                        _seed_template(no)
                    selected = no in st.session_state.order
                    c1, c2, c3 = st.columns([5, 1, 1.4])
                    badge = "🟢 " if has_body else ""
                    c1.markdown(f"{badge}**{no}** {it['title']}")
                    if selected:
                        c2.button("✓", key=f"add_{no}", disabled=True, help="追加済み")
                    else:
                        if c2.button("＋", key=f"add_{no}", help="特約に追加"):
                            add_clause(no)
                            st.rerun()

                    # 本文（プレビュー・編集）はポップオーバーに格納
                    if has_body or selected:
                        with c3.popover("📄 本文", use_container_width=True):
                            full = find_item(no)
                            ec1, ec2 = st.columns([3, 1])
                            extra = ec1.text_input(
                                "追加の事情（AI生成に反映）", key=f"extra_{no}",
                                placeholder="例：後退2m / 解除条件付 / 上限300万円",
                                label_visibility="collapsed",
                            )
                            glabel = "🔄 書き換え" if get_text(no).strip() else "🤖 生成"
                            if ec2.button(glabel, key=f"gen_{no}", use_container_width=True):
                                ok = False
                                with st.spinner(f"{it['title']} を生成中..."):
                                    try:
                                        st.session_state[f"pending_{no}"] = generate_clause(full, ctx, style, extra)
                                        ok = True
                                    except Exception as e:
                                        st.error(str(e))
                                if ok:
                                    add_clause(no)
                                    st.rerun()
                            st.text_area(
                                "本文", key=_txt_key(no), height=220,
                                label_visibility="collapsed",
                                placeholder="定型は雛形が入っています。AI生成または直接編集できます。",
                            )

    # ── 右：選択中の特約 ──
    with col_selected:
        st.subheader(f"② 選択中の特約（{len(st.session_state.order)}件）")
        if not st.session_state.order:
            st.info("左の目次から「＋」で特約項目を追加してください。")
        else:
            st.caption("並べ替え（↑↓）・削除はここで。本文の編集／AI生成は左の各条項の「本文」欄で行います。")
            top = st.columns([1, 1])
            if top[0].button("🤖 未生成を一括生成", use_container_width=True):
                pending = [n for n in st.session_state.order if not get_text(n).strip()]
                if pending:
                    prog = st.progress(0.0)
                    for k, no in enumerate(pending):
                        try:
                            st.session_state[f"pending_{no}"] = generate_clause(
                                find_item(no), ctx, style, st.session_state.get(f"extra_{no}", ""))
                        except Exception as e:
                            st.warning(f"{no} の生成失敗: {e}")
                        prog.progress((k + 1) / len(pending))
                    st.rerun()
                else:
                    st.toast("未生成の条項はありません。")
            if top[1].button("🗑 全てクリア", use_container_width=True):
                st.session_state["_clear_texts"] = True
                st.rerun()

            for pos, no in enumerate(list(st.session_state.order)):
                item = find_item(no)
                with st.container(border=True):
                    h = st.columns([6, 1, 1, 1])
                    h[0].markdown(f"**第{pos+1}条（{item['title']}）**　<small>{item['category']}</small>", unsafe_allow_html=True)
                    if h[1].button("↑", key=f"up_{no}", disabled=(pos == 0)):
                        move_clause(no, -1); st.rerun()
                    if h[2].button("↓", key=f"dn_{no}", disabled=(pos == len(st.session_state.order) - 1)):
                        move_clause(no, +1); st.rerun()
                    if h[3].button("✕", key=f"rm_{no}"):
                        remove_clause(no); st.rerun()

                    body = get_text(no).strip()
                    if body:
                        st.text(body)
                    else:
                        st.caption("⚠️ 本文未生成 — 左の一覧の「本文」欄で編集／AI生成してください。")

            # ── 根拠条文の照合 ──
            st.divider()
            st.subheader("③ 根拠条文の照合（e-Gov）")
            st.caption("生成した本文に出てくる法令の引用を、**現行条文と突き合わせます**。"
                       "AIは条番号を記憶で書くので、改正で条がずれていることがあります。"
                       "直すのは人で、このボタンは本文を書き換えません。")
            all_text = "\n".join(get_text(n) for n in st.session_state.order)
            if st.button("⚖️ 引用した条文を確かめる", use_container_width=False,
                         disabled=not all_text.strip()):
                with st.spinner("e-Gov で条文を照合中…"):
                    st.session_state["law_check"] = law_citations.verify_citations(all_text)
            checked = st.session_state.get("law_check")
            if checked is not None:
                if not checked:
                    st.info("本文に法令の引用はありませんでした。")
                else:
                    counts = law_citations.summarize(checked)
                    st.write("　".join(f"{m} **{counts.get(k, 0)}**" for k, m in
                                       (("実在", "✅ 実在"), ("無い", "⚠️ 見つからない"),
                                        ("不明", "❔ 引けない"))))
                    st.dataframe(
                        [{"引用": r["raw"], "判定": {"実在": "✅", "無い": "⚠️", "不明": "❔"}[r["status"]],
                          "現行条文": r["message"], "原文（冒頭）": r["snippet"],
                          "施行日": r["enforced"]} for r in checked],
                        use_container_width=True, hide_index=True)
                    if counts.get("無い") or counts.get("不明"):
                        st.warning("⚠️ の行は条番号が現行法と合っていない可能性があります。"
                                   "契約書に載せる前に確かめてください。")

            # ── 出力 ──
            st.divider()
            st.subheader("④ 書き出し")
            clauses = [
                {"no": n, "title": find_item(n)["title"], "text": get_text(n)}
                for n in st.session_state.order
            ]
            stamp = datetime.now().strftime("%Y%m%d")
            d1, d2 = st.columns(2)
            d1.download_button(
                "📝 Word（.docx）をダウンロード",
                data=build_docx(clauses, ctx),
                file_name=f"特約条項_{stamp}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
            d2.download_button(
                "📄 テキスト（.txt）をダウンロード",
                data=assemble_text(clauses).encode("utf-8"),
                file_name=f"特約条項_{stamp}.txt",
                mime="text/plain",
                use_container_width=True,
            )
            with st.expander("プレビュー（全文テキスト）"):
                st.text(assemble_text(clauses))


if __name__ == "__main__":
    main()
