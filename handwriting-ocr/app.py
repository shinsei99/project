import io

import pandas as pd
import streamlit as st
from PIL import Image

from excel_io import apply_cell_updates, detect_target_date, extract_compact_text, extract_excel_text, get_row_labels
from ocr import OcrError, extract_meter_readings

st.set_page_config(page_title="検針記録 → Excel転記", page_icon="✍️", layout="wide")

st.markdown(
    """
    <style>
    .stApp { background-color: #f4f8fb; }
    .step-card {
        background: white; border-radius: 14px; padding: 18px 24px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.07); margin-bottom: 18px;
    }
    h1, h2, h3 { color: #0f172a; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("✍️ 手書き検針記録 → Excel転記")
st.caption("元Excelのフォーマットを維持したまま、手書きPDFの検針値を指定列に書き込みます")

# ── セッション初期化 ──────────────────────────────────────────────────
for key, default in [
    ("excel_bytes", None),
    ("excel_text", ""),
    ("excel_compact_text", ""),
    ("excel_filename", ""),
    ("date_col_map", {}),
    ("date_list", []),
    ("target_date", None),
    ("target_col", None),
    ("updates", []),
]:
    if key not in st.session_state:
        st.session_state[key] = default


def load_excel(file):
    """Excelを読み込んでセッションに保存する（同じファイル名なら再処理しない）。"""
    if file.name == st.session_state.excel_filename:
        return  # 既に処理済み

    raw = file.read()
    if not raw:
        st.error("Excelファイルの読み込みに失敗しました（空のデータ）。")
        return

    try:
        text, date_list, date_col_map = extract_excel_text(raw)
    except Exception as e:
        st.error(f"Excelの解析に失敗しました: {e}")
        return

    st.session_state.excel_bytes = raw
    st.session_state.excel_text = text
    st.session_state.excel_compact_text = extract_compact_text(raw)
    st.session_state.excel_filename = file.name
    st.session_state.date_list = date_list
    st.session_state.date_col_map = date_col_map

    if date_list:
        # データが入っていない最初の列を自動検出
        auto = detect_target_date(raw, date_col_map)
        st.session_state.target_date = auto if auto else date_list[-1]
        st.session_state.target_col = date_col_map[st.session_state.target_date]
    else:
        st.session_state.target_date = None
        st.session_state.target_col = None


# ════════════════════════════════════════════════════════════════════
# Step 1: Excel アップロード
# ════════════════════════════════════════════════════════════════════
st.markdown("<div class='step-card'>", unsafe_allow_html=True)
st.subheader("Step 1　元Excelをアップロード")

excel_file = st.file_uploader(
    "検針記録のExcelファイル（.xlsx）",
    type=["xlsx"],
    key="excel_uploader",
)

if excel_file is not None:
    load_excel(excel_file)

# Excel 読み込み済みの場合は常に状態を表示
if st.session_state.excel_bytes:
    if st.session_state.date_list:
        st.success(f"✅ {st.session_state.excel_filename} を読み込みました（検針日 {len(st.session_state.date_list)} 件検出）")

        selected = st.selectbox(
            "書き込む検針日（自動選択済み・変更可能）",
            st.session_state.date_list,
            index=(
                st.session_state.date_list.index(st.session_state.target_date)
                if st.session_state.target_date in st.session_state.date_list
                else len(st.session_state.date_list) - 1
            ),
            key="target_date_select",
        )
        # 選択が変わったときだけセッションを更新
        if selected != st.session_state.target_date:
            st.session_state.target_date = selected
            st.session_state.target_col = st.session_state.date_col_map[selected]

        st.info(f"書き込み先: **{st.session_state.target_date}** 列（列番号: {st.session_state.target_col}）")

    else:
        st.warning(
            "検針日の列が検出できませんでした。"
            "Excelのヘッダー行に「6月18日」などの形式で検針日が入っているか確認してください。"
        )
        with st.expander("デバッグ: Excelテキスト（先頭10行）"):
            st.text(
                "\n".join(st.session_state.excel_text.splitlines()[:10])
                if st.session_state.excel_text else "（空）"
            )

st.markdown("</div>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════
# Step 2: 手書きPDF → AI解析
# ════════════════════════════════════════════════════════════════════
st.markdown("<div class='step-card'>", unsafe_allow_html=True)
st.subheader("Step 2　手書きPDF / 画像をアップロードして解析")

hw_file = st.file_uploader(
    "手書きの検針記録（.pdf / .jpg / .png）",
    type=["pdf", "jpg", "jpeg", "png"],
    key="hw_uploader",
)

if hw_file is not None:
    hw_bytes = hw_file.read()

    if not hw_file.name.lower().endswith(".pdf"):
        col_img, _ = st.columns([1, 1])
        with col_img:
            st.image(Image.open(io.BytesIO(hw_bytes)), caption="アップロード画像", use_container_width=True)

    ready = bool(st.session_state.excel_bytes) and st.session_state.target_date is not None

    if ready:
        st.info(f"解析対象: **{st.session_state.target_date}** 列")
    else:
        st.warning("先に Step 1 で Excel をアップロードしてください。")

    if st.button("AI 解析を実行", type="primary", use_container_width=True, disabled=not ready):
        with st.spinner(f"Claude AI が「{st.session_state.target_date}」列の検針値を読み取っています…（3〜5分）"):
            try:
                updates = extract_meter_readings(
                    hw_bytes,
                    hw_file.name,
                    st.session_state.excel_compact_text,
                    st.session_state.target_date,
                    st.session_state.target_col,
                )
                st.session_state.updates = updates
                st.success(f"{len(updates)} 件の検針値を認識しました。下で内容を確認してください。")
            except OcrError as e:
                st.error(f"解析に失敗しました: {e}")

st.markdown("</div>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════
# Step 3: 確認・編集 → Excel 出力
# ════════════════════════════════════════════════════════════════════
if st.session_state.updates and st.session_state.excel_bytes:
    st.markdown("<div class='step-card'>", unsafe_allow_html=True)
    st.subheader("Step 3　認識結果を確認・修正してダウンロード")

    updates = st.session_state.updates
    row_indices = [u["row"] for u in updates]
    labels = get_row_labels(st.session_state.excel_bytes, row_indices)

    display_rows = [
        {
            "行番号": u["row"],
            "行の内容（Excel）": labels.get(u["row"], f"Row {u['row']}"),
            "認識した検針値": u["value"],
        }
        for u in updates
    ]

    edited_df = st.data_editor(
        pd.DataFrame(display_rows),
        num_rows="fixed",
        use_container_width=True,
        disabled=["行番号", "行の内容（Excel）"],
        column_config={
            "認識した検針値": st.column_config.NumberColumn("認識した検針値", step=1),
        },
        key="updates_editor",
    )

    st.caption(f"書き込み先: **{st.session_state.target_date}** 列（列番号 {st.session_state.target_col}）")

    final_updates = [
        {
            "row": int(row["行番号"]),
            "col": st.session_state.target_col,
            "value": row["認識した検針値"],
        }
        for _, row in edited_df.iterrows()
        if row["認識した検針値"] not in (None, "")
    ]

    output_bytes = apply_cell_updates(st.session_state.excel_bytes, final_updates)

    st.download_button(
        f"📥 Excel ダウンロード（{st.session_state.target_date} 列に転記済み）",
        data=output_bytes,
        file_name=f"検針記録_{st.session_state.target_date}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)
