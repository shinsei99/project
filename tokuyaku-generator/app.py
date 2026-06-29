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

from clauses import CATEGORIES, find_item

CLAUDE_BIN = os.path.expanduser("~/.local/bin/claude")
CLAUDE_TIMEOUT = 120

STYLE_GUIDE = {
    "である調（契約書標準）": "文末は「〜とする」「〜するものとする」等の常体（である調）で統一する。",
    "ですます調": "文末は丁寧な敬体（ですます調）で統一する。",
}


# ── AI生成（claude CLI） ──────────────────────────────────────────────────────
def generate_clause(item: dict, ctx: dict, style: str, extra: str) -> str:
    """1つの特約項目について本文（条文）を生成する。"""
    prop = ctx.get("property", "").strip()
    seller = ctx.get("seller", "").strip()
    buyer = ctx.get("buyer", "").strip()

    parts = []
    if prop:
        parts.append(f"対象物件: {prop}")
    if seller:
        parts.append(f"売主の表記: {seller}")
    if buyer:
        parts.append(f"買主の表記: {buyer}")
    ctx_block = "\n".join(parts) if parts else "（物件情報の指定なし。一般的な表記で作成）"

    style_rule = STYLE_GUIDE.get(style, STYLE_GUIDE["である調（契約書標準）"])
    extra_block = f"\n■ 追加の事情・条件:\n{extra.strip()}" if extra.strip() else ""

    prompt = f"""あなたは不動産売買契約の特約条項作成に精通したベテラン宅地建物取引士です。
以下の項目について、不動産売買契約書にそのまま挿入できる「特約条項の本文」を作成してください。

■ 特約項目: {item['category']} ＞ {item['title']}
■ 検索キーワード: {item['hint']}
■ 物件情報:
{ctx_block}{extra_block}

【作成ルール】
- 出力は特約条項の本文のみ。見出し番号・タイトル・解説・前置き・後書きは含めない。
- できるだけ簡潔に。原則1項（1〜3文程度）でまとめ、内容上どうしても必要な場合のみ2項までとする。2項にする場合は「1.」「2.」と項番号を付ける。
- 一般的な不動産売買契約の特約文の標準的な粒度・長さに合わせ、冗長な言い回しや同義の繰り返しを避け、要点のみを端的に記載する。
- {style_rule}
- 該当する法令名・条番号があれば正確に引用する（建築基準法第42条第2項 等）。
- 物件情報が指定されていれば自然に織り込み、未指定の箇所は「本物件」「売主」「買主」等の一般表記にする。
- 不明な数値・固有名詞は創作せず、金額・距離・日数等は「〇〇」とプレースホルダにする。

特約条項の本文のみ（簡潔に）を出力してください:"""

    cmd = [
        CLAUDE_BIN, "-p", prompt,
        "--output-format", "json",
        "--dangerously-skip-permissions",
        "--model", "sonnet",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=CLAUDE_TIMEOUT)
    except FileNotFoundError:
        raise RuntimeError("`claude` コマンドが見つかりません。Claude Code CLI がインストールされているか確認してください。")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"生成が{CLAUDE_TIMEOUT}秒を超えたため中断しました。再試行してください。")

    if proc.returncode != 0:
        raise RuntimeError(f"claude コマンドが失敗しました（終了コード {proc.returncode}）\n{proc.stderr.strip()[:300]}")

    result = json.loads(proc.stdout)
    if result.get("is_error"):
        raise RuntimeError(f"Claude がエラーを返しました: {result.get('result')}")
    return result.get("result", "").strip()


# ── Word出力 ─────────────────────────────────────────────────────────────────
def _set_font(run, size_pt=10.5, bold=False, color=None, font="游明朝"):
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.name = font
    rPr = run._r.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.insert(0, rFonts)
    rFonts.set(qn("w:eastAsia"), font)
    if color:
        run.font.color.rgb = RGBColor(*color)


def build_docx(clauses: list, ctx: dict) -> bytes:
    doc = Document()

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_font(title.add_run("特 約 条 項"), size_pt=15, bold=True, font="游ゴシック")

    if ctx.get("property", "").strip():
        sub = doc.add_paragraph()
        sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _set_font(sub.add_run(f"物件：{ctx['property'].strip()}"), size_pt=10, font="游ゴシック")

    doc.add_paragraph()

    for idx, c in enumerate(clauses, 1):
        head = doc.add_paragraph()
        _set_font(head.add_run(f"第{idx}条（{c['title']}）"), size_pt=11, bold=True, font="游ゴシック")
        body_text = (c.get("text") or "（本文未生成）").strip()
        for line in body_text.split("\n"):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Pt(12)
            p.paragraph_format.space_after = Pt(4)
            _set_font(p.add_run(line), size_pt=10.5)
        doc.add_paragraph()

    note = doc.add_paragraph()
    _set_font(
        note.add_run("※本書はAIが作成した下書きです。必ず専門家によるリーガルチェックと表記統一を行ってください。"),
        size_pt=8, color=(150, 150, 150),
    )

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def assemble_text(clauses: list) -> str:
    blocks = []
    for idx, c in enumerate(clauses, 1):
        body = (c.get("text") or "（本文未生成）").strip()
        blocks.append(f"第{idx}条（{c['title']}）\n{body}")
    return "\n\n".join(blocks)


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

            # ── 出力 ──
            st.divider()
            st.subheader("③ 書き出し")
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
