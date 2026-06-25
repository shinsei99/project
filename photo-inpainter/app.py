"""
不動産写真 AIインペインター — Streamlit UI

電柱・電線・通行人などをブラシでなぞるか、クリックするだけで
OpenCV / LaMa AI が自動消去します（ローカル処理・API不要）。
"""

import streamlit as st
from PIL import Image
import numpy as np
from io import BytesIO
import hashlib

# ── streamlit-drawable-canvas 互換パッチ ────────────────────────────────────
# Streamlit 1.28+ で image_to_url が streamlit.elements.image から
# streamlit.elements.lib.image_utils へ移動し、第2引数も
# width(int) → LayoutConfig オブジェクトに変更された。
# st_canvas が旧 API を呼ぶため、旧シグネチャで受け取り新 API に橋渡しする。
import streamlit.elements.image as _st_img
if not hasattr(_st_img, "image_to_url"):
    from streamlit.elements.lib.image_utils import image_to_url as _real_image_to_url
    from streamlit.elements.lib.layout_utils import LayoutConfig as _LayoutConfig

    def _compat_image_to_url(image, width, clamp, channels, output_format, image_id, allow_emoji=False):
        layout_cfg = _LayoutConfig(width=width if isinstance(width, int) else None)
        return _real_image_to_url(image, layout_cfg, clamp, channels, output_format, image_id)

    _st_img.image_to_url = _compat_image_to_url
# ────────────────────────────────────────────────────────────────────────────

from streamlit_drawable_canvas import st_canvas
from inpainting import (
    run_pipeline, resize_to_fit, has_drawing, LAMA_AVAILABLE,
    click_auto_mask, inpaint_lama, inpaint_opencv, create_mask_overlay,
)

# ── 定数 ─────────────────────────────────────────────────────────────────────
MAX_CANVAS_W = 740
MAX_CANVAS_H = 560
STROKE_COLOR = "#FF1010"
STROKE_RGB   = (255, 16, 16)

MODE_BRUSH = "✏️ ブラシ（手動）"
MODE_CLICK = "🖱️ クリック（自動選択）"


# ── ヘルパー ─────────────────────────────────────────────────────────────────
def _image_id(raw: bytes) -> str:
    return hashlib.md5(raw).hexdigest()[:10]


def _to_png_bytes(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _init_session():
    defaults = {
        "img_id": None,
        "original": None,
        "result": None,
        "mask": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ── メイン ───────────────────────────────────────────────────────────────────
def main():
    st.set_page_config(
        page_title="不動産写真 AIインペインター",
        page_icon="🏠",
        layout="wide",
    )
    _init_session()

    # ── サイドバー ────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("## 🎨 描画モード")
        mode = st.radio("モード", [MODE_BRUSH, MODE_CLICK], label_visibility="collapsed")
        is_click = (mode == MODE_CLICK)
        st.divider()

        if not is_click:
            st.markdown("## ✏️ ブラシ設定")
            stroke_width = st.slider("ブラシの太さ（px）", 5, 100, 28, step=1)
            tolerance = 25  # ブラシモードでは未使用
        else:
            stroke_width = 6  # クリックモードでは未使用
            st.markdown("## 🖱️ クリック設定")
            tolerance = st.slider(
                "色の許容範囲", 5, 80, 20, step=5,
                help="クリックした点と色が近いピクセルを選択します。小さいほど厳密。電線は15〜25、人物は35〜50がおすすめ。",
            )
            st.caption("💡 クリックを重ねて消去範囲を追加できます")

        st.divider()
        st.markdown("## 🤖 消去アルゴリズム")

        engine_options = ["⚡ OpenCV（高速・軽量）"]
        if LAMA_AVAILABLE:
            engine_options.append("✨ LaMa AI（高品質・推奨）")

        engine = st.radio(
            "エンジン選択",
            engine_options,
            index=1 if LAMA_AVAILABLE else 0,
            help="LaMa AI は自然な仕上がりで電線・通行人どちらにも効果的です。初回のみモデルダウンロード（約200MB）があります。",
        )
        use_lama = "LaMa" in engine

        if use_lama:
            st.success("✨ LaMa AI モード（初回のみモデルDL あり）")
            dilate = st.slider("マスク拡張（塗り残し補正）", 0, 5, 3)
            method, radius = "telea", 7
        else:
            st.info("⚡ OpenCV モード（即時処理・仕上がりは中程度）")
            if not is_click:
                algo_label = st.radio(
                    "アルゴリズム",
                    [
                        "TELEA（電線・電柱・細いもの向き）",
                        "Navier-Stokes（通行人・看板など広い面積向き）",
                    ],
                )
                method = "telea" if "TELEA" in algo_label else "ns"
                radius = st.slider("インペイント半径（px）", 3, 30, 7)
            else:
                method, radius = "telea", 7
            dilate = st.slider("マスク拡張（塗り残し補正）", 0, 5, 2)

        st.divider()
        st.markdown("### 💡 使い方のコツ")
        if is_click:
            st.markdown(
                "- 消したいものを **クリック** するだけ\n"
                "- 複数クリックで消去範囲を追加できます\n"
                "- 赤いプレビューで選択範囲を確認\n"
                "- 選択が足りない場合はマスク拡張を増やす\n"
                "- **電線**: 線の上を直接クリック\n"
                "- **人物**: 胴体や服をクリック"
            )
        else:
            st.markdown(
                "- ブラシを **太め** にして確実に赤く塗る\n"
                "- 電線は端から端まで途切れなくなぞる\n"
                "- うまくいかない場合はマスク拡張を増やす\n"
                "- **LaMa AI** は空・建物どちらの背景でも自然に仕上がる"
            )

    # ── メインエリア ──────────────────────────────────────────────────────────
    st.title("🏠 不動産写真 AIインペインター")
    st.caption(
        "電柱・電線・通行人などを消去します　"
        "（ローカル処理・API不要）"
    )
    st.divider()

    # ── 画像アップロード ──────────────────────────────────────────────────────
    uploaded = st.file_uploader(
        "📷 物件写真をアップロード（JPEG / PNG）",
        type=["jpg", "jpeg", "png"],
        help="外観・内装などの物件写真をアップロードしてください。",
    )

    if uploaded is None:
        st.info(
            "👆 写真をアップロードすると、不要なものを消去できます。\n\n"
            "**対応対象:** 電柱・電線・通行人・看板・不要な車・影など\n\n"
            "**モード（左サイドバー）:**\n"
            "- ✏️ **ブラシ**: 赤いブラシでなぞって手動で範囲を指定\n"
            "- 🖱️ **クリック**: クリックするだけで色の近い領域を自動選択"
        )
        return

    # 画像ロード
    raw_bytes = uploaded.read()
    img_id = _image_id(raw_bytes)
    original = Image.open(BytesIO(raw_bytes)).convert("RGB")

    if st.session_state.img_id != img_id:
        st.session_state.img_id = img_id
        st.session_state.original = original
        st.session_state.result = None
        st.session_state.mask = None

    disp_img = resize_to_fit(original, MAX_CANVAS_W, MAX_CANVAS_H)
    disp_w, disp_h = disp_img.size

    # ── キャンバス ────────────────────────────────────────────────────────────
    if is_click:
        st.subheader("🖱️ 消したい部分をクリックしてください")
        st.caption(
            f"📐 元サイズ: **{original.width} × {original.height} px**　"
            f"表示: {disp_w} × {disp_h} px　"
            "| クリックするたびに下のプレビューで選択範囲が更新されます"
        )
        canvas_result = st_canvas(
            fill_color="rgba(255, 50, 50, 0.85)",
            stroke_width=1,
            stroke_color="#FF3232",
            background_color="#e8e8e8",
            background_image=disp_img,
            update_streamlit=True,
            height=disp_h,
            width=disp_w,
            drawing_mode="point",
            point_display_radius=6,
            key=f"canvas_click_{img_id}",
        )

        # クリック点をキャンバスの JSON から抽出
        click_points = []
        if canvas_result.json_data and "objects" in canvas_result.json_data:
            for obj in canvas_result.json_data["objects"]:
                if obj.get("type") == "circle":
                    click_points.append((obj["left"], obj["top"]))

        has_draw = len(click_points) > 0

        # クリック後にマスクプレビューをリアルタイム表示
        if has_draw:
            preview_mask = click_auto_mask(
                original, click_points, (disp_w, disp_h),
                tolerance=tolerance, dilate_iters=dilate,
            )
            overlay_img = create_mask_overlay(disp_img, preview_mask)
            st.caption("🔴 赤い範囲が消去対象のプレビューです（「消去する」ボタンで実行）")
            st.image(overlay_img, width=disp_w)

    else:
        st.subheader("✏️ 消したい部分を赤ブラシでなぞってください")
        st.caption(
            f"📐 元サイズ: **{original.width} × {original.height} px**　"
            f"表示: {disp_w} × {disp_h} px　"
            f"ブラシ: {stroke_width} px（スマホはタッチ操作対応）"
        )
        canvas_result = st_canvas(
            fill_color="rgba(0, 0, 0, 0)",
            stroke_width=stroke_width,
            stroke_color=STROKE_COLOR,
            background_color="#e8e8e8",
            background_image=disp_img,
            update_streamlit=True,
            height=disp_h,
            width=disp_w,
            drawing_mode="freedraw",
            point_display_radius=0,
            key=f"canvas_brush_{img_id}",
        )
        has_draw = has_drawing(canvas_result.image_data, stroke_rgb=STROKE_RGB)
        click_points = []

    # ── ボタン群 ──────────────────────────────────────────────────────────────
    col_run, col_reset = st.columns([4, 1])
    with col_run:
        run_btn = st.button(
            "🤖　AIで不要なものを消去する",
            type="primary",
            use_container_width=True,
        )
    with col_reset:
        if st.button("🔄 リセット", use_container_width=True, help="描画・クリックをリセットして結果を消去します"):
            st.session_state.result = None
            st.session_state.mask = None
            st.rerun()

    # ── 消去処理 ──────────────────────────────────────────────────────────────
    if run_btn:
        if not has_draw:
            if is_click:
                st.warning("⚠️ 画像の上をクリックして消去したい場所を選択してください。")
            else:
                st.warning("⚠️ キャンバスに何も描かれていません。消したい部分を赤ブラシでなぞってください。")
        else:
            spinner_msg = (
                "✨ LaMa AI が処理中... 初回のみモデルDL（約200MB）があります。しばらくお待ちください。"
                if use_lama else "⚡ OpenCV で処理中..."
            )
            with st.spinner(spinner_msg):
                try:
                    if is_click:
                        mask = click_auto_mask(
                            st.session_state.original,
                            click_points,
                            (disp_w, disp_h),
                            tolerance=tolerance,
                            dilate_iters=dilate,
                        )
                        if use_lama:
                            result = inpaint_lama(st.session_state.original, mask)
                        else:
                            result = inpaint_opencv(st.session_state.original, mask, method=method, radius=radius)
                    else:
                        result, mask = run_pipeline(
                            st.session_state.original,
                            canvas_result.image_data,
                            (disp_w, disp_h),
                            method=method,
                            radius=radius,
                            dilate_iters=dilate,
                            use_lama=use_lama,
                        )

                    st.session_state.result = result
                    st.session_state.mask = mask
                    engine_label = "LaMa AI" if use_lama else ("TELEA" if method == "telea" else "Navier-Stokes")
                    st.success(
                        f"✅ 消去完了！　"
                        f"処理サイズ: {original.width}×{original.height}px　"
                        f"エンジン: {engine_label}"
                    )
                except Exception as ex:
                    st.error(f"❌ 処理中にエラーが発生しました: {ex}")

    # ── 結果表示 ──────────────────────────────────────────────────────────────
    if st.session_state.result is not None:
        st.divider()
        st.subheader("📊 処理結果")

        tab_compare, tab_after, tab_mask = st.tabs([
            "🔀 Before / After 比較",
            "✅ 加工後（拡大表示）",
            "🔍 マスク確認",
        ])

        with tab_compare:
            col_b, col_a = st.columns(2)
            with col_b:
                st.markdown("**Before（加工前）**")
                st.image(st.session_state.original, use_container_width=True)
            with col_a:
                st.markdown("**After（加工後）**")
                st.image(st.session_state.result, use_container_width=True)

        with tab_after:
            st.image(st.session_state.result, use_container_width=True)

        with tab_mask:
            st.caption("白=消去した範囲　黒=保持した範囲")
            st.image(st.session_state.mask, use_container_width=True, clamp=True)

        st.divider()
        result_bytes = _to_png_bytes(st.session_state.result)
        base_name = uploaded.name.rsplit(".", 1)[0]
        st.download_button(
            label=f"📥 加工後の写真をダウンロード（PNG・原寸 {original.width}×{original.height}px）",
            data=result_bytes,
            file_name=f"{base_name}_inpainted.png",
            mime="image/png",
            use_container_width=True,
            type="primary",
        )


if __name__ == "__main__":
    main()
