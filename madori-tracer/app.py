"""間取り図トレーサー — Gemini image-to-image で白黒図面に引き直す。"""
from __future__ import annotations

import io

import streamlit as st
from PIL import Image
from streamlit_cropper import st_cropper

from analyzer import analyze
from pdf_extractor import extract_floor_plan_from_pdf

st.set_page_config(page_title="間取り図トレーサー", page_icon="🏠", layout="wide")

st.title("🏠 間取り図トレーサー")
st.caption("間取り図をアップロードすると、AI がシンプルな白黒図面に引き直します。")

# ── セッション初期化 ──────────────────────────────────────────────────────────
for key, default in [
    ("result_bytes", None),
    ("original_image", None),
    ("cropped_image", None),
    ("last_file_id", None),
    ("is_pdf", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ── アップロード ──────────────────────────────────────────────────────────────
uploaded = st.file_uploader(
    "間取り図を選択（JPEG / PNG / WebP / PDF）",
    type=["jpg", "jpeg", "png", "webp", "pdf"],
)

floor_type = st.selectbox(
    "図面タイプ",
    ["マンション", "戸建て", "1K・1R", "その他"],
    index=0,
)

# ── ファイル変更検知 ──────────────────────────────────────────────────────────
if uploaded:
    file_id = (uploaded.name, uploaded.size)
    if file_id != st.session_state.last_file_id:
        st.session_state.last_file_id = file_id
        st.session_state.result_bytes = None
        st.session_state.cropped_image = None
        st.session_state.crop = None

        if uploaded.type == "application/pdf":
            with st.spinner("PDF を読み込み中..."):
                try:
                    page_image = extract_floor_plan_from_pdf(uploaded.read())
                    st.session_state.original_image = page_image
                    st.session_state.is_pdf = True
                except Exception as e:
                    st.error(f"PDF 読み込みエラー: {e}")
        else:
            st.session_state.original_image = Image.open(uploaded).convert("RGB")
            st.session_state.is_pdf = False

# ── PDF クロップ UI（クロップ未確定のときだけ表示）────────────────────────────
if st.session_state.is_pdf and st.session_state.original_image and st.session_state.cropped_image is None:
    st.subheader("① 間取り図の範囲をドラッグで選択してください")
    st.caption("赤枠の角・辺をドラッグして間取り図にぴったり合わせてください。")

    img = st.session_state.original_image
    max_w = 700
    if img.width > max_w:
        r = max_w / img.width
        display_img = img.resize((max_w, int(img.height * r)), Image.LANCZOS)
    else:
        display_img = img

    cropped_preview = st_cropper(
        display_img,
        realtime_update=True,
        box_color="#E01E1E",
        aspect_ratio=None,
        return_type="image",
    )

    st.caption("抽出プレビュー ↓")
    st.image(cropped_preview, width=400)

    if st.button("② この範囲で引き直しを開始する", type="primary", use_container_width=True):
        st.session_state.cropped_image = cropped_preview.copy().convert("RGB")
        st.session_state.result_bytes = None
        st.rerun()

    st.divider()

# クロップ確定後にクロッパーを再表示させるボタン
if st.session_state.is_pdf and st.session_state.cropped_image is not None:
    if st.button("✂️ 範囲を変更する", use_container_width=False):
        st.session_state.cropped_image = None
        st.session_state.result_bytes = None
        st.rerun()
    st.divider()

# ── 通常の間取り図 UI（画像 or PDF クロップ後）────────────────────────────────
source_image = st.session_state.cropped_image if st.session_state.is_pdf else st.session_state.original_image

if source_image:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("元の間取り図")
        st.image(source_image, use_container_width=True)

    with col2:
        st.subheader("引き直し結果")

        if st.session_state.result_bytes is None:
            if st.button("生成する", type="primary", use_container_width=True):
                with st.spinner("Gemini が変換中... (10〜30秒)"):
                    try:
                        result = analyze(source_image, floor_type)
                        st.session_state.result_bytes = result
                        st.rerun()
                    except Exception as e:
                        st.error(f"エラー: {e}")

        if st.session_state.result_bytes:
            result_img = Image.open(io.BytesIO(st.session_state.result_bytes))
            st.image(result_img, use_container_width=True)

            st.download_button(
                "⬇ JPEG ダウンロード",
                data=st.session_state.result_bytes,
                file_name="floor-plan.jpg",
                mime="image/jpeg",
                use_container_width=True,
            )

            st.divider()

            st.markdown("**修正して再生成**")
            correction = st.text_area(
                "間違っている点を具体的に入力してください（空欄でそのまま再生成）",
                placeholder="例：キッチンの位置がLDKではなく洋室の上に描かれている",
                height=100,
            )
            if st.button("🔄 再生成する", use_container_width=True):
                with st.spinner("修正中... (10〜30秒)"):
                    try:
                        result = analyze(
                            source_image,
                            floor_type,
                            correction=correction,
                            prev_result=st.session_state.result_bytes,
                        )
                        st.session_state.result_bytes = result
                        st.rerun()
                    except Exception as e:
                        st.error(f"エラー: {e}")
