import io
import zipfile

import pandas as pd
import streamlit as st
from PIL import Image


def format_size(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    return f"{size_bytes / 1024:.1f} KB"


def resize_image(img: Image.Image, max_long_side: int, quality: int) -> tuple[bytes, tuple[int, int]]:
    if img.mode != "RGB":
        img = img.convert("RGB")

    w, h = img.size
    if max(w, h) > max_long_side:
        if w >= h:
            new_w = max_long_side
            new_h = round(h * max_long_side / w)
        else:
            new_h = max_long_side
            new_w = round(w * max_long_side / h)
        img = img.resize((new_w, new_h), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue(), img.size


st.set_page_config(page_title="物件写真一括リサイズ", page_icon="🏠", layout="wide")

st.title("🏠 物件写真一括リサイズ・軽量化ツール")
st.caption("ホームズ・スーモなどへの物件写真登録を効率化 ― ドラッグ＆ドロップ → ZIP一括ダウンロード")

for key in ("results", "zip_data", "total_before", "total_after"):
    if key not in st.session_state:
        st.session_state[key] = None

# ① アップロード
st.markdown("### ① 画像のアップロード")
uploaded_files = st.file_uploader(
    "JPEG / PNG 画像をドラッグ＆ドロップ（複数同時可）",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True,
)
if uploaded_files:
    st.success(f"**{len(uploaded_files)} 枚**の画像が選択されています")

    with st.expander("アップロード画像のプレビュー", expanded=True):
        cols_per_row = 5
        rows = [uploaded_files[i:i + cols_per_row] for i in range(0, len(uploaded_files), cols_per_row)]
        for row in rows:
            cols = st.columns(cols_per_row)
            for col, f in zip(cols, row):
                img = Image.open(f)
                col.image(img, caption=f.name, use_container_width=True)
                f.seek(0)

st.markdown("---")

# ② 設定
st.markdown("### ② リサイズ設定")
col_left, col_right = st.columns(2)

with col_left:
    st.markdown("**サイズ設定**")
    resize_mode = st.radio(
        "サイズ設定",
        ["ホームズ・スーモ推奨（長辺 1200px）", "カスタムサイズ"],
        label_visibility="collapsed",
    )
    if resize_mode == "カスタムサイズ":
        max_long_side = st.number_input(
            "長辺のピクセル数を指定",
            min_value=100,
            max_value=5000,
            value=1200,
            step=100,
        )
    else:
        max_long_side = 1200
        st.caption("長辺を 1200px に統一します（縦横比は完全維持）")

with col_right:
    st.markdown("**画質（Quality）**")
    quality = st.slider("Quality", min_value=1, max_value=100, value=85, label_visibility="collapsed")
    if quality >= 90:
        st.caption(f"Quality: {quality}% ― 高画質（ファイルが大きくなります）")
    elif quality <= 70:
        st.caption(f"Quality: {quality}% ― ⚠️ 低画質（画質劣化が目立つ場合があります）")
    else:
        st.caption(f"Quality: {quality}% ― バランス良好（推奨）")

st.markdown("---")

# ③ 実行
st.markdown("### ③ 一括変換の実行")

if st.button(
    "🚀 一括リサイズを実行",
    type="primary",
    disabled=not uploaded_files,
    use_container_width=True,
):
    total = len(uploaded_files)
    results = []
    raw_totals = []
    zip_buffer = io.BytesIO()

    progress_bar = st.progress(0)
    status_text = st.empty()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, file in enumerate(uploaded_files):
            status_text.markdown(f"処理中… **{total} 枚中 {i + 1} 枚目** ― `{file.name}`")

            file_bytes = file.read()
            original_size = len(file_bytes)
            original_dims = Image.open(io.BytesIO(file_bytes)).size

            img_data, new_dims = resize_image(
                Image.open(io.BytesIO(file_bytes)), int(max_long_side), quality
            )
            new_size = len(img_data)

            base_name = file.name.rsplit(".", 1)[0]
            zf.writestr(f"{base_name}.jpg", img_data)

            reduction = (1 - new_size / original_size) * 100
            results.append(
                {
                    "ファイル名": file.name,
                    "変換前サイズ": f"{original_dims[0]} × {original_dims[1]} px",
                    "変換後サイズ": f"{new_dims[0]} × {new_dims[1]} px",
                    "変換前容量": format_size(original_size),
                    "変換後容量": format_size(new_size),
                    "削減率": f"▼ {reduction:.1f}%",
                }
            )
            raw_totals.append((original_size, new_size))
            progress_bar.progress((i + 1) / total)

    zip_buffer.seek(0)
    status_text.markdown(f"✅ **完了！** {total} 枚すべて処理しました。")

    st.session_state.results = results
    st.session_state.zip_data = zip_buffer.getvalue()
    st.session_state.total_before = sum(r[0] for r in raw_totals)
    st.session_state.total_after = sum(r[1] for r in raw_totals)

# ④ 結果
if st.session_state.results:
    st.markdown("---")
    st.markdown("### ④ 変換結果と一括ダウンロード")

    tb = st.session_state.total_before
    ta = st.session_state.total_after
    total_reduction = (1 - ta / tb) * 100 if tb else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("処理枚数", f"{len(st.session_state.results)} 枚")
    c2.metric("変換前 合計", format_size(tb))
    c3.metric("変換後 合計", format_size(ta), delta=f"-{format_size(tb - ta)}", delta_color="normal")
    c4.metric("合計削減率", f"▼ {total_reduction:.1f}%")

    st.dataframe(pd.DataFrame(st.session_state.results), use_container_width=True, hide_index=True)

    st.download_button(
        label="📥 ZIP ファイルをダウンロード（全画像まとめて）",
        data=st.session_state.zip_data,
        file_name="resized_images.zip",
        mime="application/zip",
        type="primary",
        use_container_width=True,
    )
