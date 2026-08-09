"""
不動産写真 AIインペインター — Streamlit UI

電柱・電線・通行人・車などを、ブラシでなぞる／クリックするだけで消去します。
消去エンジンは LaMa（IOPaint・Apache-2.0）。すべてローカル処理で API 不要。

2つの選択モード:
  🎯 AI選択(SAM)   … 物体をクリックすると輪郭を自動抽出（車・人・看板・電柱）
  ✏️ ブラシ        … 赤ブラシで手動指定。電線など細いものはこちらが確実
"""

import streamlit as st
from PIL import Image
import numpy as np
from io import BytesIO
import hashlib
import zipfile

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
    resize_to_fit, has_drawing, extract_mask_from_canvas, dilate_mask,
    sam_click_mask, inpaint_lama, inpaint_opencv,
    create_mask_overlay, LAMA_AVAILABLE, SAM_AVAILABLE,
    SAM_MODELS, default_sam_model,
)

# ── 定数 ─────────────────────────────────────────────────────────────────────
MAX_CANVAS_W = 740
MAX_CANVAS_H = 560
STROKE_COLOR = "#FF1010"
STROKE_RGB   = (255, 16, 16)

FILL_ADD    = "rgba(255, 50, 50, 0.85)"    # 追加クリック（消す）
FILL_EXCL   = "rgba(40, 120, 255, 0.85)"   # 除外クリック（残す）

MODE_BRUSH = "✏️ ブラシ（手動）"
MODE_SAM   = "🎯 AI選択（クリックで物体を切り抜き）"


# ── ヘルパー ─────────────────────────────────────────────────────────────────
def _to_png_bytes(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _photo_key(name: str, raw: bytes) -> str:
    return hashlib.md5(name.encode("utf-8") + raw).hexdigest()[:10]


def _init_session():
    if "photos" not in st.session_state:
        st.session_state.photos = {}    # key -> {name, original, working, history, edited}
    if "current" not in st.session_state:
        st.session_state.current = None


def _register(uploaded_files):
    """アップロードされたファイルを session に取り込む（既存分は保持）"""
    keys = []
    for f in uploaded_files:
        raw = f.getvalue()
        key = _photo_key(f.name, raw)
        keys.append(key)
        if key not in st.session_state.photos:
            img = Image.open(BytesIO(raw)).convert("RGB")
            st.session_state.photos[key] = {
                "name": f.name,
                "original": img,
                "working": img,      # いま編集対象になっている画像（消去を重ねると更新される）
                "history": [],       # Undo 用のスタック
                "edited": False,
            }
    # アップローダから外された写真は破棄する
    for key in list(st.session_state.photos):
        if key not in keys:
            del st.session_state.photos[key]
    if st.session_state.current not in st.session_state.photos:
        st.session_state.current = keys[0] if keys else None
    return keys


def _build_zip() -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in st.session_state.photos.values():
            if not p["edited"]:
                continue
            stem = p["name"].rsplit(".", 1)[0]
            zf.writestr(f"{stem}_inpainted.png", _to_png_bytes(p["working"]))
    return buf.getvalue()


# ── メイン ───────────────────────────────────────────────────────────────────
def main():
    st.set_page_config(page_title="不動産写真 AIインペインター", page_icon="🏠", layout="wide")
    _init_session()

    # ── サイドバー ────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("## 🎨 選択モード")
        available_modes = ([MODE_SAM] if SAM_AVAILABLE else []) + [MODE_BRUSH]
        mode = st.radio("モード", available_modes, index=0, label_visibility="collapsed")

        st.divider()
        stroke_width, exclude_mode = 28, False
        sam_model = None

        if mode == MODE_SAM:
            st.markdown("## 🎯 AI選択の設定")
            exclude_mode = st.toggle(
                "🔵 除外モード（残したい所をクリック）",
                help="選択が広がりすぎたとき、残したい部分を青くクリックすると選択から外れます。",
            )
            st.caption(
                "消したい物体をクリック。1回で足りなければ**同じ物体の別の場所を追加クリック**して"
                "範囲を広げます（車のタイヤ・ルーフなど）。"
            )

            # 既定はマシン判定（Apple Silicon=vit_b / Intel=mobile_sam）。大きいほど選択が正確
            names = list(SAM_MODELS.values())
            default_name = default_sam_model()
            label = st.selectbox(
                "選択AIの精度",
                list(SAM_MODELS.keys()),
                index=names.index(default_name),
                help="大きいモデルほど輪郭が正確になります（消し跡のハローが減る）。"
                     "ただし『広く取れる』わけではなく、むしろドア1枚のような意味のまとまりで"
                     "選ぶため、車1台なら数クリック必要です。初回はモデルDLと解析に時間がかかります。"
                     "既定はこのMacに合わせて自動選択しています。",
            )
            sam_model = SAM_MODELS[label]
            if sam_model != default_name:
                st.caption("⚠️ 既定から変更中。初回クリック時にモデルのダウンロードが走ります。")
        else:
            st.markdown("## ✏️ ブラシ設定")
            stroke_width = st.slider("ブラシの太さ（px）", 5, 100, 28, step=1)
            st.caption("💡 電線のように細いものは、太めのブラシで端から端まで途切れなくなぞるのが確実です。")

        st.divider()
        st.markdown("## 🤖 消去エンジン")
        engine_options = []
        if LAMA_AVAILABLE:
            engine_options.append("✨ LaMa AI（高品質・推奨）")
        engine_options.append("⚡ OpenCV（高速・軽量）")
        engine = st.radio("エンジン選択", engine_options, index=0)
        use_lama = "LaMa" in engine

        if use_lama:
            st.success("✨ LaMa AI モード")
            st.caption("長辺800px超はマスク周辺だけを切り出して推論するため、原寸のまま数秒で終わります。")
            dilate = st.slider("マスク拡張（塗り残し補正）", 0, 5, 3)
            method, radius = "telea", 7
        else:
            st.info("⚡ OpenCV モード（即時・仕上がりは中程度）")
            algo_label = st.radio(
                "アルゴリズム",
                ["TELEA（電線・電柱・細いもの向き）", "Navier-Stokes（通行人・看板など広い面積向き）"],
            )
            method = "telea" if "TELEA" in algo_label else "ns"
            radius = st.slider("インペイント半径（px）", 3, 30, 7)
            dilate = st.slider("マスク拡張（塗り残し補正）", 0, 5, 2)

        if not LAMA_AVAILABLE:
            st.error(
                "LaMa が読み込めません。`pip install -r requirements.txt` を実行してください。"
                "（Intel Mac は torch==2.2.2 の固定が必要です）"
            )

    # ── メインエリア ──────────────────────────────────────────────────────────
    st.title("🏠 不動産写真 AIインペインター")
    st.caption("電柱・電線・通行人・車などを消去します（ローカル処理・API不要）")
    st.divider()

    uploaded_files = st.file_uploader(
        "📷 物件写真をアップロード（複数選択可・JPEG / PNG）",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        help="複数枚まとめて読み込み、1枚ずつ加工して最後にZIPで一括ダウンロードできます。",
    )

    if not uploaded_files:
        st.info(
            "👆 写真をアップロードすると、不要なものを消去できます。\n\n"
            "**対応対象:** 電柱・電線・通行人・看板・不要な車・室内の家具など\n\n"
            "**モード（左サイドバー）:**\n"
            "- 🎯 **AI選択**: 消したい物をクリック → 輪郭を自動で切り抜き（車・人・看板・電柱）\n"
            "- ✏️ **ブラシ**: 赤ブラシでなぞって手動指定（電線など細いものはこちら）"
        )
        return

    keys = _register(uploaded_files)

    # ── 写真の切り替え ────────────────────────────────────────────────────────
    if len(keys) > 1:
        labels = {
            k: f"{'✅ ' if st.session_state.photos[k]['edited'] else ''}{st.session_state.photos[k]['name']}"
            for k in keys
        }
        st.session_state.current = st.radio(
            f"編集する写真（{len(keys)}枚）",
            keys,
            format_func=lambda k: labels[k],
            horizontal=True,
            index=keys.index(st.session_state.current) if st.session_state.current in keys else 0,
        )

    key = st.session_state.current
    photo = st.session_state.photos[key]
    working = photo["working"]
    step = len(photo["history"])          # 何回消去を重ねたか
    canvas_key = f"canvas_{mode}_{key}_{step}"

    disp_img = resize_to_fit(working, MAX_CANVAS_W, MAX_CANVAS_H)
    disp_w, disp_h = disp_img.size

    size_caption = (
        f"📐 元サイズ: **{working.width} × {working.height} px**　"
        f"表示: {disp_w} × {disp_h} px"
        + (f"　| 🔁 {step} 回消去済み" if step else "")
    )

    mask_preview = None

    # ── キャンバス ────────────────────────────────────────────────────────────
    if mode == MODE_SAM:
        st.subheader("🎯 消したい物体をクリックしてください")
        st.caption(size_caption + "　| 🔴=消す　🔵=残す（除外モード）")
        canvas_result = st_canvas(
            fill_color=FILL_EXCL if exclude_mode else FILL_ADD,
            stroke_width=1,
            stroke_color="#FFFFFF",
            background_color="#e8e8e8",
            background_image=disp_img,
            update_streamlit=True,
            height=disp_h, width=disp_w,
            drawing_mode="point",
            point_display_radius=6,
            key=canvas_key,
        )
        pos_points, neg_points = [], []
        if canvas_result.json_data and "objects" in canvas_result.json_data:
            for obj in canvas_result.json_data["objects"]:
                if obj.get("type") != "circle":
                    continue
                (neg_points if obj.get("fill") == FILL_EXCL else pos_points).append(
                    (obj["left"], obj["top"])
                )
        has_draw = len(pos_points) > 0

        if has_draw:
            with st.spinner("🎯 AIが輪郭を抽出中…（そのモデルの初回だけモデルDLがあります）"):
                mask_preview = sam_click_mask(
                    working, pos_points, (disp_w, disp_h),
                    image_key=f"{key}_{step}",
                    negative_points=neg_points,
                    dilate_iters=dilate,
                    model_name=sam_model,
                )
            st.caption(
                f"🔴 赤い範囲が消去対象です（画像の {100 * mask_preview.mean() / 255:.1f}%）"
                "　— 足りなければ追加クリック、広すぎれば除外モードでクリック"
            )
            st.image(create_mask_overlay(disp_img, mask_preview), width=disp_w)

    else:
        st.subheader("✏️ 消したい部分を赤ブラシでなぞってください")
        st.caption(size_caption + f"　ブラシ: {stroke_width} px（スマホはタッチ操作対応）")
        canvas_result = st_canvas(
            fill_color="rgba(0, 0, 0, 0)",
            stroke_width=stroke_width,
            stroke_color=STROKE_COLOR,
            background_color="#e8e8e8",
            background_image=disp_img,
            update_streamlit=True,
            height=disp_h, width=disp_w,
            drawing_mode="freedraw",
            point_display_radius=0,
            key=canvas_key,
        )
        has_draw = has_drawing(canvas_result.image_data, stroke_rgb=STROKE_RGB)
        if has_draw:
            mask_preview = extract_mask_from_canvas(
                canvas_result.image_data, (working.width, working.height), (disp_w, disp_h),
                stroke_rgb=STROKE_RGB,
            )
            mask_preview = dilate_mask(mask_preview, iterations=dilate)

    # ── ボタン群 ──────────────────────────────────────────────────────────────
    col_run, col_undo, col_reset = st.columns([4, 1, 1])
    with col_run:
        run_btn = st.button("🤖　AIで不要なものを消去する", type="primary", use_container_width=True)
    with col_undo:
        undo_btn = st.button(
            "↩️ 元に戻す", use_container_width=True, disabled=step == 0,
            help="直前の消去を取り消します",
        )
    with col_reset:
        reset_btn = st.button(
            "🔄 最初から", use_container_width=True, disabled=step == 0,
            help="この写真の消去をすべて取り消してアップロード直後の状態に戻します",
        )

    if undo_btn:
        photo["working"] = photo["history"].pop()
        photo["edited"] = len(photo["history"]) > 0
        st.rerun()

    if reset_btn:
        photo["working"] = photo["original"]
        photo["history"] = []
        photo["edited"] = False
        st.rerun()

    # ── 消去処理 ──────────────────────────────────────────────────────────────
    if run_btn:
        if not has_draw or mask_preview is None or mask_preview.max() == 0:
            st.warning("⚠️ 消去する範囲が選択されていません。画像の上をクリック／ブラシでなぞってください。")
        else:
            spinner_msg = "✨ LaMa AI が処理中…" if use_lama else "⚡ OpenCV で処理中…"
            with st.spinner(spinner_msg):
                try:
                    if use_lama:
                        result = inpaint_lama(working, mask_preview)
                    else:
                        result = inpaint_opencv(working, mask_preview, method=method, radius=radius)

                    # 結果を working に反映。もう一度消したいときはそのまま重ねられる
                    photo["history"].append(working)
                    photo["working"] = result
                    photo["edited"] = True
                    st.success(
                        f"✅ 消去完了！　{working.width}×{working.height}px　"
                        f"エンジン: {'LaMa AI' if use_lama else ('TELEA' if method == 'telea' else 'Navier-Stokes')}"
                        "　— 続けて別の物を消す場合はそのままクリックしてください"
                    )
                    st.rerun()
                except Exception as ex:
                    st.error(f"❌ 処理中にエラーが発生しました: {ex}")

    # ── 結果表示 ──────────────────────────────────────────────────────────────
    if photo["edited"]:
        st.divider()
        st.subheader("📊 処理結果")

        tab_compare, tab_after = st.tabs(["🔀 Before / After 比較", "✅ 加工後（拡大表示）"])
        with tab_compare:
            col_b, col_a = st.columns(2)
            with col_b:
                st.markdown("**Before（アップロード時）**")
                st.image(photo["original"], width="stretch")
            with col_a:
                st.markdown(f"**After（{step} 回消去）**")
                st.image(photo["working"], width="stretch")
        with tab_after:
            st.image(photo["working"], width="stretch")

        st.divider()
        stem = photo["name"].rsplit(".", 1)[0]
        col_one, col_all = st.columns(2)
        with col_one:
            st.download_button(
                f"📥 この1枚をダウンロード（PNG・原寸 {photo['working'].width}×{photo['working'].height}px）",
                data=_to_png_bytes(photo["working"]),
                file_name=f"{stem}_inpainted.png",
                mime="image/png",
                use_container_width=True,
                type="primary",
            )
        with col_all:
            done = sum(1 for p in st.session_state.photos.values() if p["edited"])
            st.download_button(
                f"🗂 加工済み {done} 枚をZIPで一括ダウンロード",
                data=_build_zip(),
                file_name="inpainted_photos.zip",
                mime="application/zip",
                use_container_width=True,
                disabled=done == 0,
            )


if __name__ == "__main__":
    main()
