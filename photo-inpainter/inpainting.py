"""
不動産写真インペインティング — 画像処理ロジック

UI に依存しない純粋な処理関数のみを収録。
将来的な iPhone (Swift/CoreImage) / Flutter (dart:ffi + OpenCV) 移植や
LaMa 等の高精度モデルへのアップグレードを想定した設計。

移植時の対応表:
  pil_to_cv2 / cv2_to_pil   → UIImage ↔ Mat 変換
  extract_mask_from_canvas   → タッチイベントの描画バッファ → マスク変換
  inpaint_opencv             → cv::inpaint() or CoreImage CIInpaintingFilter
  run_pipeline               → 処理エントリーポイント（そのまま移植可）
"""

import cv2
import numpy as np
from PIL import Image
from typing import Literal, List, Tuple

# ── AI バックエンド（IOPaint）の利用可能チェック ───────────────────────────────
# LaMa 本体と Segment Anything は IOPaint（Apache-2.0）の実装を利用する。
# 旧実装は simple-lama-inpainting に依存していたが、これは requirements.txt に
# 一度も含まれていなかったため常に ImportError → OpenCV へフォールバックしていた。
try:
    from iopaint.model_manager import ModelManager as _ModelManager
    from iopaint.schema import InpaintRequest as _InpaintRequest, HDStrategy as _HDStrategy
    LAMA_AVAILABLE = True
except ImportError:
    LAMA_AVAILABLE = False

try:
    from iopaint.plugins.interactive_seg import InteractiveSeg as _InteractiveSeg
    SAM_AVAILABLE = True
except ImportError:
    SAM_AVAILABLE = False

# 選べる Segment Anything モデル（表示名 → IOPaint のモデル名）。
#
# 実測（1600x1067 の軽バンを1クリック / Intel CPU）:
#   mobile_sam … 選択 14.2% / 1.8s  輪郭がギザギザで車体外にはみ出し、穴も空く
#   vit_b      … 選択  5.6% / 24.1s スライドドア1枚を境界正確に選択
# つまり大きいモデル＝広く取れる、ではない。「意味のまとまり」で正確に切る方向に効く。
# インペイントは輪郭が汚いと消し跡にハローが残るため、実用上は大きい方が有利だが、
# 車1台のような複合物は追加クリックで足していく前提になる。
# いま結果の質を最も左右しているのは LaMa ではなく「マスクの精度」なので、
# マシンに余裕があるならここを上げるのが一番効く。
SAM_MODELS = {
    "軽量 mobile_sam（40MB・Intel/CPU向き）": "mobile_sam",
    "標準 vit_b（375MB）": "vit_b",
    "高精度 vit_l（1.2GB）": "vit_l",
    "最高精度 vit_h（2.4GB）": "vit_h",
}


def default_sam_model() -> str:
    """
    実行中のマシンに合わせた既定の SAM モデルを返す。

    Apple Silicon（MPS あり）は余裕があるので vit_b、
    Intel Mac は CPU 推論しかできないため mobile_sam を既定にする。
    環境変数 SAM_MODEL で明示的に上書きできる。
    """
    import os
    override = os.environ.get("SAM_MODEL")
    if override in SAM_MODELS.values():
        return override
    import torch
    return "vit_b" if torch.backends.mps.is_available() else "mobile_sam"


_lama_instance = None   # シングルトン（モデルのロードは重いため1回だけ）
_sam_instance = None


def _pick_device():
    """macOS は CUDA 非対応。MPS（Apple Silicon）があれば使い、なければ CPU。"""
    import torch
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _get_lama():
    global _lama_instance
    if _lama_instance is None:
        _lama_instance = _ModelManager(name="lama", device=_pick_device())
    return _lama_instance


def _get_sam(model_name: str = None):
    """SAM を取得する。モデルを切り替えた場合は載せ替える（埋め込みキャッシュもリセットされる）。"""
    global _sam_instance
    import torch
    model_name = model_name or default_sam_model()
    if _sam_instance is None:
        # SAM は MPS で不安定な報告があるため CPU 固定
        _sam_instance = _InteractiveSeg(model_name, torch.device("cpu"))
    elif _sam_instance.model_name != model_name:
        _sam_instance.switch_model(model_name)
    return _sam_instance


# ── 型エイリアス ─────────────────────────────────────────────────────────────
ImageRGB = Image.Image          # PIL Image (RGB モード)
MaskArr  = np.ndarray           # uint8 (H, W) — 255=消去対象, 0=保持
CanvasArr = np.ndarray          # uint8 (H, W, 4) RGBA — st_canvas の image_data
Size2D   = Tuple[int, int]      # (width, height)


# ── 変換ユーティリティ ────────────────────────────────────────────────────────

def pil_to_cv2(img: ImageRGB) -> np.ndarray:
    """PIL Image (RGB) → OpenCV ndarray (BGR)"""
    arr = np.array(img.convert("RGB"), dtype=np.uint8)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def cv2_to_pil(arr: np.ndarray) -> ImageRGB:
    """OpenCV ndarray (BGR) → PIL Image (RGB)"""
    rgb = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def resize_to_fit(img: ImageRGB, max_w: int, max_h: int) -> ImageRGB:
    """アスペクト比を保ちつつ max_w × max_h に収まるようリサイズ（縮小のみ）"""
    ratio = min(max_w / img.width, max_h / img.height, 1.0)
    if ratio >= 1.0:
        return img.copy()
    new_w, new_h = int(img.width * ratio), int(img.height * ratio)
    return img.resize((new_w, new_h), Image.LANCZOS)


# ── マスク生成 ────────────────────────────────────────────────────────────────

def extract_mask_from_canvas(
    canvas_rgba: CanvasArr,
    original_wh: Size2D,
    canvas_wh: Size2D,
    stroke_rgb: Tuple[int, int, int] = (255, 16, 16),
    tolerance: int = 60,
) -> MaskArr:
    """
    st_canvas の描画データ（RGBA）から消去対象マスクを生成する。

    ブラシ色 (stroke_rgb) との色差で描画領域を検出し、
    元画像サイズにアップスケールして返す。

    Args:
        canvas_rgba : (H, W, 4) uint8 — canvas_result.image_data
        original_wh : 元画像の (width, height)
        canvas_wh   : キャンバスの (width, height) — canvas_rgba の W,H
        stroke_rgb  : ブラシ色 (R, G, B)。デフォルトは赤 (#FF1010)
        tolerance   : 色一致の許容幅（0〜255）

    Returns:
        (H_orig, W_orig) uint8 マスク配列
    """
    sr, sg, sb = stroke_rgb
    r = canvas_rgba[:, :, 0].astype(np.int16)
    g = canvas_rgba[:, :, 1].astype(np.int16)
    b = canvas_rgba[:, :, 2].astype(np.int16)

    # ブラシ色との色距離（チェビシェフ距離）
    dist = np.maximum(np.maximum(np.abs(r - sr), np.abs(g - sg)), np.abs(b - sb))
    mask = (dist < tolerance).astype(np.uint8) * 255

    # 元画像サイズにリサイズ（描画キャンバスと元画像のスケールが異なる場合）
    if canvas_wh != original_wh:
        mask = cv2.resize(mask, original_wh, interpolation=cv2.INTER_NEAREST)
        _, mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)

    return mask


def create_mask_overlay(
    base_img: ImageRGB,
    mask: MaskArr,
    alpha: float = 0.45,
) -> ImageRGB:
    """
    マスクを base_img サイズにリサイズして赤オーバーレイで合成したプレビューを返す。
    クリックモードで消去対象範囲を視覚的に確認するために使用する。
    """
    base_np = np.array(base_img.convert("RGB"))
    h, w = base_np.shape[:2]
    mask_resized = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
    overlay = base_np.copy()
    overlay[mask_resized > 127] = [220, 50, 50]
    blended = (base_np * (1 - alpha) + overlay * alpha).astype(np.uint8)
    return Image.fromarray(blended)


def dilate_mask(mask: MaskArr, iterations: int = 2, kernel_size: int = 5) -> MaskArr:
    """
    マスクをわずかに膨張させて塗り残し・エッジのアーティファクトを低減する。

    電線のように細い対象でも確実に消去領域をカバーするために使用。
    iterations を増やすと膨張量が増えるが、過剰に膨張すると
    消去範囲が広がりすぎるので注意。
    """
    if iterations == 0:
        return mask
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    return cv2.dilate(mask, kernel, iterations=iterations)


# ── インペインティング ────────────────────────────────────────────────────────

def inpaint_opencv(
    image: ImageRGB,
    mask: MaskArr,
    method: Literal["telea", "ns"] = "telea",
    radius: int = 7,
) -> ImageRGB:
    """
    OpenCV のインペインティングでマスク領域を背景で補完する。

    Args:
        image  : 入力 PIL 画像 (RGB)
        mask   : uint8 マスク — 255=消去対象, 0=保持
        method :
            "telea" — 勾配ベース（Fast Marching Method）。
                      電線・電柱・文字など細い構造物の消去に強い。
            "ns"    — ナビエ・ストークス流体力学ベース。
                      通行人・看板など面積の大きい物体の消去に向く。
        radius : 補完参照半径（ピクセル）。
                 小さいほど高速・狭い参照。大きいほど広い背景を参照するが遅い。

    Returns:
        処理済み PIL 画像 (RGB)

    移植メモ:
        Swift: CIFilter(name: "CIInpaintingFilter") または Metal Shader
        Flutter: ffi 経由で OpenCV cv::inpaint を呼ぶか、
                 将来は lama-cleaner 等の ONNX モデルに置き換え可
    """
    cv2_img = pil_to_cv2(image)
    flag = cv2.INPAINT_TELEA if method == "telea" else cv2.INPAINT_NS
    result = cv2.inpaint(cv2_img, mask, inpaintRadius=radius, flags=flag)
    return cv2_to_pil(result)


def inpaint_lama(image: ImageRGB, mask: MaskArr) -> ImageRGB:
    """
    LaMa（Large Mask Inpainting）モデルで高品質にマスク領域を補完する。

    OpenCV より大幅に高品質。初回実行時にモデル（big-lama.pt・約200MB）を自動
    ダウンロードし、以後は ~/.cache/torch/hub/checkpoints にキャッシュされる。

    長辺が 800px を超える画像は HD ストラテジ CROP で処理する。
    マスク周辺だけを切り出して推論するため、4000px 級の写真でも
    原寸のまま数秒で終わり、マスク外の画質は一切劣化しない。

    Args:
        image : 入力 PIL 画像 (RGB)
        mask  : uint8 マスク — 255=消去対象, 0=保持

    Returns:
        処理済み PIL 画像 (RGB)
    """
    if not LAMA_AVAILABLE:
        raise RuntimeError(
            "IOPaint がインストールされていません。"
            "`pip install -r requirements.txt` を実行してください。"
        )

    model = _get_lama()
    rgb = np.array(image.convert("RGB"), dtype=np.uint8)

    # マスクは画像と同サイズの 2値（0/255）に正規化してから渡す
    if mask.shape[:2] != rgb.shape[:2]:
        mask = cv2.resize(mask, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_NEAREST)
    mask = np.where(mask >= 127, 255, 0).astype(np.uint8)

    config = _InpaintRequest(
        hd_strategy=_HDStrategy.CROP,
        hd_strategy_crop_trigger_size=800,
        hd_strategy_crop_margin=128,
    )
    bgr = model(rgb, mask, config)          # 返り値は BGR
    return cv2_to_pil(np.clip(bgr, 0, 255).astype(np.uint8))


# ── Segment Anything によるクリック選択 ───────────────────────────────────────

def sam_click_mask(
    image: ImageRGB,
    click_points: List[Tuple[float, float]],
    canvas_wh: Size2D,
    image_key: str = "",
    negative_points: List[Tuple[float, float]] = None,
    dilate_iters: int = 1,
    model_name: str = None,
) -> MaskArr:
    """
    Segment Anything（mobile_sam）で、クリックした物体の輪郭を丸ごと選択する。

    電柱・通行人・車・看板など **面のある物体** を1〜数クリックで切り抜ける。
    電線のように細い線状のものは苦手なので、その場合はブラシでなぞる。

    Args:
        image           : 元 PIL 画像 (RGB)
        click_points    : 消したい物体の上のクリック点（キャンバス座標）
        canvas_wh       : キャンバスの表示サイズ (width, height)
        image_key       : 画像の識別子。同じ画像なら埋め込み計算を再利用して高速化する
        negative_points : 選択から除外したい点（キャンバス座標）
        dilate_iters    : マスク膨張の反復回数
        model_name      : SAM_MODELS の値。None ならマシンに応じた既定（default_sam_model）

    Returns:
        (H_orig, W_orig) uint8 マスク配列
    """
    if not SAM_AVAILABLE:
        raise RuntimeError(
            "Segment Anything が利用できません。"
            "`pip install -r requirements.txt` を実行してください。"
        )
    if not click_points:
        return np.zeros((image.height, image.width), dtype=np.uint8)

    canvas_w, canvas_h = canvas_wh
    scale_x = image.width / canvas_w
    scale_y = image.height / canvas_h

    def _to_orig(pts, label):
        out = []
        for cx, cy in (pts or []):
            ix = max(0, min(image.width - 1, int(round(cx * scale_x))))
            iy = max(0, min(image.height - 1, int(round(cy * scale_y))))
            out.append([ix, iy, label])
        return out

    clicks = _to_orig(click_points, 1) + _to_orig(negative_points, 0)

    rgb = np.array(image.convert("RGB"), dtype=np.uint8)
    sam = _get_sam(model_name)
    # モデルを切り替えると埋め込みキャッシュが無効になるため、キーにモデル名を含める
    mask = sam.forward(rgb, clicks, f"{sam.model_name}:{image_key}")

    if mask.shape[:2] != rgb.shape[:2]:
        mask = cv2.resize(mask, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_NEAREST)
    mask = np.where(mask >= 127, 255, 0).astype(np.uint8)

    return dilate_mask(mask, iterations=dilate_iters)


# ── パイプライン（エントリーポイント） ─────────────────────────────────────────

def run_pipeline(
    original_image: ImageRGB,
    canvas_rgba: CanvasArr,
    canvas_wh: Size2D,
    method: str = "telea",
    radius: int = 7,
    dilate_iters: int = 2,
    use_lama: bool = False,
) -> Tuple[ImageRGB, MaskArr]:
    """
    アップロード画像 + キャンバス描画 → 加工済み画像（フルパイプライン）

    UI 非依存のメインエントリーポイント。
    Flutter / Swift 移植時はこのシグネチャを参考に実装する。

    Args:
        original_image : 元の PIL 画像（フル解像度）
        canvas_rgba    : キャンバス描画データ (H, W, 4)
        canvas_wh      : キャンバスの表示サイズ (width, height)
        method         : "telea" or "ns"
        radius         : インペイント参照半径
        dilate_iters   : マスク膨張の反復回数（0=膨張なし）

    Returns:
        (加工済み PIL 画像, マスク配列)
    """
    orig_wh = (original_image.width, original_image.height)

    # 1. キャンバスから描画マスクを抽出（キャンバス→元画像サイズにスケール）
    mask = extract_mask_from_canvas(canvas_rgba, orig_wh, canvas_wh)

    # 2. マスクを少し膨張させて塗り残しをカバー
    mask = dilate_mask(mask, iterations=dilate_iters)

    # 3. インペインティング実行
    if use_lama:
        result = inpaint_lama(original_image, mask)
    else:
        result = inpaint_opencv(original_image, mask, method=method, radius=radius)

    return result, mask


def has_drawing(canvas_rgba: CanvasArr, stroke_rgb=(255, 16, 16), tolerance: int = 60) -> bool:
    """キャンバスにブラシ描画があるか判定する"""
    if canvas_rgba is None:
        return False
    sr, sg, sb = stroke_rgb
    r = canvas_rgba[:, :, 0].astype(np.int16)
    g = canvas_rgba[:, :, 1].astype(np.int16)
    b = canvas_rgba[:, :, 2].astype(np.int16)
    dist = np.maximum(np.maximum(np.abs(r - sr), np.abs(g - sg)), np.abs(b - sb))
    return bool((dist < tolerance).any())
