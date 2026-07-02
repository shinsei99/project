import UIKit

/// 補正済みの基底画像に注釈を焼き込み、フル解像度の最終画像を生成する。
enum ImageExporter {
    static func compose(base: UIImage, annotations: [Annotation]) -> UIImage {
        let px: CGSize
        if let cg = base.cgImage {
            px = CGSize(width: cg.width, height: cg.height)
        } else {
            px = CGSize(width: base.size.width * base.scale,
                        height: base.size.height * base.scale)
        }
        let format = UIGraphicsImageRendererFormat.default()
        format.scale = 1
        format.opaque = true
        let renderer = UIGraphicsImageRenderer(size: px, format: format)
        return renderer.image { ctx in
            base.draw(in: CGRect(origin: .zero, size: px))
            for a in annotations {
                draw(a, in: ctx.cgContext, imageSize: px)
            }
        }
    }

    private static func draw(_ a: Annotation, in c: CGContext, imageSize: CGSize) {
        switch a.kind {
        case .text:
            let center = CGPoint(x: a.position.x * imageSize.width,
                                 y: a.position.y * imageSize.height)
            c.saveGState()
            c.translateBy(x: center.x, y: center.y)
            c.rotate(by: CGFloat(a.rotation.radians))
            drawText(a, in: c, imageSize: imageSize)
            c.restoreGState()
        case .arrow:
            drawArrow(a, in: c, imageSize: imageSize)
        }
    }

    private static func drawText(_ a: Annotation, in c: CGContext, imageSize: CGSize) {
        let pt = max(4, a.fontHeightFraction * imageSize.height)
        let str = TextRendering.attributedString(a, fontPt: pt)
        let bigSize = CGSize(width: CGFloat.greatestFiniteMagnitude,
                             height: CGFloat.greatestFiniteMagnitude)
        let bounds = str.boundingRect(
            with: bigSize,
            options: [.usesLineFragmentOrigin, .usesFontLeading], context: nil)
        str.draw(in: CGRect(x: -bounds.width / 2, y: -bounds.height / 2,
                            width: bounds.width, height: bounds.height))
    }

    private static func drawArrow(_ a: Annotation, in c: CGContext, imageSize: CGSize) {
        let from = CGPoint(x: a.arrowStart.x * imageSize.width, y: a.arrowStart.y * imageSize.height)
        let to = CGPoint(x: a.arrowEnd.x * imageSize.width, y: a.arrowEnd.y * imageSize.height)
        let length = max(1, hypot(to.x - from.x, to.y - from.y))
        let thickness = length * a.arrowThicknessRatio
        c.addPath(ArrowGeometry.pathBetween(from: from, to: to, thickness: thickness))
        c.setFillColor(UIColor(hex: a.colorHex).cgColor)
        c.fillPath()
    }
}
