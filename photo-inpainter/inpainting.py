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

# LaMa モデルの利用可能チェック（optional）
try:
    from simple_lama_inpainting import SimpleLama as _SimpleLama
    LAMA_AVAILABLE = True
except ImportError:
    LAMA_AVAILABLE = False

_lama_instance = None  # シングルトン（モデルのロードは重いため1回だけ）

def _get_lama() -> "_SimpleLama":
    global _lama_instance
    if _lama_instance is None:
        import torch
        # macOS は CUDA 非対応。MPS（Apple Silicon）があれば使い、なければ CPU
        if torch.backends.mps.is_available():
            device = torch.device("mps")
        else:
            device = torch.device("cpu")
        _lama_instance = _SimpleLama(device=device)
    return _lama_instance


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


def _point_to_segment_dist(px: float, py: float,
                            x1: float, y1: float,
                            x2: float, y2: float) -> float:
    """点 (px, py) から線分 (x1,y1)-(x2,y2) への最短距離。"""
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return float(((px - x1) ** 2 + (py - y1) ** 2) ** 0.5)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return float(((px - x1 - t * dx) ** 2 + (py - y1 - t * dy) ** 2) ** 0.5)


def _hough_wire_mask(gray: np.ndarray, ix: int, iy: int,
                     search_radius: int, wire_thickness: int = 4) -> np.ndarray:
    """
    HoughLinesP で直線セグメントを検出し、クリック点に最も近い「電線」のみ返す。

    クリック点に最も近いセグメントを基準線とし、
    ① 同じ角度（±25°以内）かつ
    ② 基準線の延長上（垂直距離 20px 以内）
    にあるセグメントのみ選択する。

    これにより建物の辺（異なる角度・位置）は除外され、
    電線（同じ方向・同一直線上に連続するセグメント群）のみ抽出される。
    """
    H, W = gray.shape
    empty = np.zeros((H, W), dtype=np.uint8)

    edges = cv2.Canny(gray, 30, 100)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180,
                             threshold=30, minLineLength=15, maxLineGap=15)
    if lines is None:
        return empty

    # クリック点に最も近いセグメントを基準線に採用
    best_dist, ref = float('inf'), None
    for seg in lines:
        x1, y1, x2, y2 = seg[0]
        d = _point_to_segment_dist(float(ix), float(iy), x1, y1, x2, y2)
        if d < best_dist:
            best_dist, ref = d, seg[0]

    if ref is None or best_dist > search_radius:
        return empty

    rx1, ry1, rx2, ry2 = ref
    rdx, rdy = rx2 - rx1, ry2 - ry1
    rlen = (rdx ** 2 + rdy ** 2) ** 0.5
    if rlen < 1:
        return empty

    rux, ruy = rdx / rlen, rdy / rlen   # 単位方向ベクトル
    rnx, rny = -ruy, rux                 # 単位法線ベクトル
    ref_angle = np.arctan2(rdy, rdx)

    mask = empty.copy()
    for seg in lines:
        x1, y1, x2, y2 = seg[0]
        dx, dy = x2 - x1, y2 - y1

        # ① 角度チェック（180° 対称を考慮）
        a_diff = abs(ref_angle - np.arctan2(dy, dx))
        if a_diff > np.pi / 2:
            a_diff = np.pi - a_diff
        if a_diff > np.radians(25):
            continue

        # ② 基準線の延長線からの垂直距離チェック
        mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        perp = abs((mx - rx1) * rny - (my - ry1) * rnx)
        if perp > 20:
            continue

        cv2.line(mask, (x1, y1), (x2, y2), 255, wire_thickness)

    return mask


def _nearest_component(
    labels: np.ndarray,
    ix: int,
    iy: int,
    orig_w: int,
    orig_h: int,
    search_radius: int,
) -> np.ndarray:
    """labels 配列の中から (ix, iy) に最も近い連結成分を返す。"""
    y1 = max(0, iy - search_radius)
    y2 = min(orig_h, iy + search_radius + 1)
    x1 = max(0, ix - search_radius)
    x2 = min(orig_w, ix + search_radius + 1)

    win = labels[y1:y2, x1:x2]
    yy, xx = np.ogrid[y1:y2, x1:x2]
    win_dists = (yy - iy) ** 2 + (xx - ix) ** 2

    nearby = np.unique(win[win > 0])
    if len(nearby) == 0:
        return np.zeros((orig_h, orig_w), dtype=np.uint8)

    best_label, best_dist = None, float('inf')
    for lbl in nearby:
        px = win == lbl
        if px.sum() < 3:
            continue
        d = float(win_dists[px].min() ** 0.5)
        if d < best_dist:
            best_dist, best_label = d, lbl

    if best_label is None:
        return np.zeros((orig_h, orig_w), dtype=np.uint8)

    return (labels == best_label).astype(np.uint8) * 255


def click_auto_mask(
    image: ImageRGB,
    click_points: List[Tuple[float, float]],
    canvas_wh: Size2D,
    tolerance: int = 25,
    dilate_iters: int = 3,
) -> MaskArr:
    """
    クリック座標リストから自動マスクを生成する。

    処理フロー:
    1. bilateralFilter で JPEG ノイズを除去（エッジは保持）
    2. Black-hat 変換で「細い暗い構造物だけ」を抽出（空・建物壁は除外）
    3. クリック点に最も近い Black-hat 連結成分を返す（= 電線）
    4. Black-hat で見つからない場合: 色類似度でフォールバック（人物向け）

    Args:
        image        : 元 PIL 画像 (RGB)
        click_points : キャンバス座標の点リスト [(cx, cy), ...]
        canvas_wh    : キャンバスの表示サイズ (width, height)
        tolerance    : フォールバック時の色許容差（人物は 30〜50）
        dilate_iters : マスク膨張の反復回数

    Returns:
        (H_orig, W_orig) uint8 マスク配列
    """
    orig_w, orig_h = image.width, image.height
    canvas_w, canvas_h = canvas_wh
    scale_x = orig_w / canvas_w
    scale_y = orig_h / canvas_h
    search_radius = max(30, int(max(scale_x, scale_y) * 10))
    snap_r = max(5, int(max(scale_x, scale_y) * 2))

    img_bgr = pil_to_cv2(image)
    smooth = cv2.bilateralFilter(img_bgr, 5, 50, 50)
    gray = cv2.cvtColor(smooth, cv2.COLOR_BGR2GRAY)

    combined = np.zeros((orig_h, orig_w), dtype=np.uint8)

    for cx, cy in click_points:
        ix = max(0, min(orig_w - 1, int(round(cx * scale_x))))
        iy = max(0, min(orig_h - 1, int(round(cy * scale_y))))

        # 近傍の最暗ピクセルにスナップ（クリックずれ・JPEG 端ピクセル対策）
        sy1 = max(0, iy - snap_r)
        sy2 = min(orig_h, iy + snap_r + 1)
        sx1 = max(0, ix - snap_r)
        sx2 = min(orig_w, ix + snap_r + 1)
        min_pos = np.unravel_index(gray[sy1:sy2, sx1:sx2].argmin(), (sy2 - sy1, sx2 - sx1))
        seed_iy = sy1 + int(min_pos[0])
        seed_ix = sx1 + int(min_pos[1])

        # ① Hough 直線検出（主手法）
        # 「クリック点に最も近い直線と同じ角度・同一延長線上のセグメント」だけを選ぶ
        # → 電線（一直線状のセグメント群）のみ抽出、建物の辺（異なる位置・角度）は除外
        point_mask = _hough_wire_mask(gray, seed_ix, seed_iy, search_radius)

        # ② フラッドフィル フォールバック（Hough で検出できない場合）
        # グローバル色選択ではなくフラッドフィルを使うことで
        # 「クリック点から連結していない同色エリア」が選択されるのを防ぐ
        if point_mask.sum() // 255 < 30:
            flood_buf = np.zeros((orig_h + 2, orig_w + 2), dtype=np.uint8)
            cv2.floodFill(
                smooth.copy(), flood_buf,
                seedPoint=(seed_ix, seed_iy), newVal=(0, 0, 0),
                loDiff=(tolerance,) * 3, upDiff=(tolerance,) * 3,
                flags=cv2.FLOODFILL_MASK_ONLY | (255 << 8),
            )
            point_mask = flood_buf[1:-1, 1:-1]

        combined = cv2.bitwise_or(combined, point_mask)

    if dilate_iters > 0:
        combined = dilate_mask(combined, iterations=dilate_iters)

    return combined


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

    OpenCV より大幅に高品質。初回実行時にモデル（約200MB）を自動ダウンロード。
    CPU のみでも動作するが、OpenCV より処理は遅い（数秒〜数十秒）。

    Args:
        image : 入力 PIL 画像 (RGB)
        mask  : uint8 マスク — 255=消去対象, 0=保持

    Returns:
        処理済み PIL 画像 (RGB)
    """
    if not LAMA_AVAILABLE:
        raise RuntimeError("simple-lama-inpainting がインストールされていません。`pip install simple-lama-inpainting` を実行してください。")

    lama = _get_lama()
    mask_pil = Image.fromarray(mask).convert("L")
    result = lama(image, mask_pil)
    return result.convert("RGB")


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
