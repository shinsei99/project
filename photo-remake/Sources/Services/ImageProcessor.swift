import CoreImage
import CoreImage.CIFilterBuiltins
import UIKit

/// Core Image を使った補正パイプライン。actor で GPU コンテキストを共有し逐次実行。
actor ImageProcessor {
    static let shared = ImageProcessor()

    private let context = CIContext(options: [.cacheIntermediates: false])

    /// 補正を適用した UIImage を返す。無補正なら入力をそのまま返す。
    func render(_ adj: Adjustments, on image: UIImage) -> UIImage {
        if adj.isIdentity { return image }
        guard let cg = image.cgImage else { return image }
        var ci = CIImage(cgImage: cg)

        // 明るさ・コントラスト・彩度（飽和）
        if adj.brightness != 0 || adj.contrast != 0 || adj.saturation != 0 {
            let f = CIFilter.colorControls()
            f.inputImage = ci
            f.brightness = Float(adj.brightness / 100 * 0.4)
            f.contrast = Float(1 + adj.contrast / 100 * 0.5)
            f.saturation = Float(1 + adj.saturation / 100)
            if let out = f.outputImage { ci = out }
        }
        // 鮮やかさ（自然な彩度）
        if adj.vibrance != 0 {
            let f = CIFilter.vibrance()
            f.inputImage = ci
            f.amount = Float(adj.vibrance / 100)
            if let out = f.outputImage { ci = out }
        }
        // 鮮明度（局所コントラスト）
        if adj.clarity != 0 {
            let f = CIFilter.unsharpMask()
            f.inputImage = ci
            f.radius = 3.0
            f.intensity = Float(adj.clarity / 100 * 0.8)
            if let out = f.outputImage { ci = out }
        }
        // ノイズ除去（シャープより先に）
        if adj.noiseReduction != 0 {
            let f = CIFilter.noiseReduction()
            f.inputImage = ci
            f.noiseLevel = Float(adj.noiseReduction / 100 * 0.08)
            f.sharpness = 0.4
            if let out = f.outputImage { ci = out }
        }
        // シャープ
        if adj.sharpness != 0 {
            let f = CIFilter.sharpenLuminance()
            f.inputImage = ci
            f.sharpness = Float(adj.sharpness / 100 * 1.2)
            if let out = f.outputImage { ci = out }
        }

        let rect = ci.extent.isInfinite ? CIImage(cgImage: cg).extent : ci.extent
        guard let outCG = context.createCGImage(ci, from: rect) else { return image }
        return UIImage(cgImage: outCG, scale: image.scale, orientation: .up)
    }

    /// 画像全体をモザイク（ピクセル化）した版を返す。blockFraction は画像幅に対するブロック割合。
    func pixellate(_ image: UIImage, blockFraction: CGFloat) -> UIImage {
        guard let cg = image.cgImage else { return image }
        let ci = CIImage(cgImage: cg)
        let f = CIFilter.pixellate()
        f.inputImage = ci
        f.scale = Float(max(4, blockFraction * CGFloat(cg.width)))
        f.center = CGPoint(x: cg.width / 2, y: cg.height / 2)
        guard let out = f.outputImage else { return image }
        let rect = CGRect(x: 0, y: 0, width: cg.width, height: cg.height)
        guard let outCG = context.createCGImage(out, from: rect) else { return image }
        return UIImage(cgImage: outCG, scale: image.scale, orientation: .up)
    }
}
