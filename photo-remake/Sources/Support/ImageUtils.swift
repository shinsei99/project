import UIKit

extension UIImage {
    /// EXIF 回転を実ピクセルに焼き込み、向きを .up に正規化する。
    /// Core Image / 手動描画は orientation を無視するため、取り込み時に必ず通す。
    func normalizedUp() -> UIImage {
        if imageOrientation == .up { return self }
        let format = UIGraphicsImageRendererFormat.default()
        format.scale = scale
        let renderer = UIGraphicsImageRenderer(size: size, format: format)
        return renderer.image { _ in draw(in: CGRect(origin: .zero, size: size)) }
    }

    /// 長辺が maxPixels を超える場合だけ縮小したコピーを返す（ライブプレビュー高速化用）。
    func downscaled(maxPixels: CGFloat) -> UIImage {
        let longSide = max(size.width, size.height) * scale
        guard longSide > maxPixels else { return self }
        let ratio = maxPixels / longSide
        let newSize = CGSize(width: size.width * scale * ratio,
                             height: size.height * scale * ratio)
        let format = UIGraphicsImageRendererFormat.default()
        format.scale = 1
        let renderer = UIGraphicsImageRenderer(size: newSize, format: format)
        return renderer.image { _ in draw(in: CGRect(origin: .zero, size: newSize)) }
    }
}

extension UIImage {
    /// 正規化矩形（0..1, 左上原点）で切り抜いたコピーを返す。
    func cropped(to r: CGRect) -> UIImage {
        guard let cg = cgImage else { return self }
        let W = CGFloat(cg.width), H = CGFloat(cg.height)
        let rect = CGRect(x: r.minX * W, y: r.minY * H,
                          width: r.width * W, height: r.height * H).integral
        let safe = rect.intersection(CGRect(x: 0, y: 0, width: W, height: H))
        guard !safe.isNull, safe.width >= 1, safe.height >= 1,
              let out = cg.cropping(to: safe) else { return self }
        return UIImage(cgImage: out, scale: scale, orientation: .up)
    }
}

/// コンテナ内に aspect-fit で画像を収めたときの実表示矩形を計算する。
/// 注釈の正規化座標(0..1)を画面座標へ変換する基準に使う。
func aspectFitRect(imageSize: CGSize, in container: CGSize) -> CGRect {
    guard imageSize.width > 0, imageSize.height > 0 else { return .zero }
    let scale = min(container.width / imageSize.width,
                    container.height / imageSize.height)
    let w = imageSize.width * scale
    let h = imageSize.height * scale
    return CGRect(x: (container.width - w) / 2,
                  y: (container.height - h) / 2,
                  width: w, height: h)
}
