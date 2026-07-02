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
        let center = CGPoint(x: a.position.x * imageSize.width,
                             y: a.position.y * imageSize.height)
        c.saveGState()
        c.translateBy(x: center.x, y: center.y)
        c.rotate(by: CGFloat(a.rotation.radians))
        switch a.kind {
        case .text: drawText(a, in: c, imageSize: imageSize)
        case .arrow: drawArrow(a, in: c, imageSize: imageSize)
        }
        c.restoreGState()
    }

    private static func drawText(_ a: Annotation, in c: CGContext, imageSize: CGSize) {
        let pt = max(4, a.fontHeightFraction * imageSize.height)
        let font = AnnotationFont.uiFont(name: a.fontName, size: pt, bold: a.isBold)
        var attrs: [NSAttributedString.Key: Any] = [
            .font: font,
            .foregroundColor: UIColor(hex: a.colorHex),
        ]
        if a.hasOutline {
            attrs[.strokeColor] = UIColor(hex: a.outlineColorHex)
                .withAlphaComponent(a.outlineOpacity)
            attrs[.strokeWidth] = -Double(a.outlineWidthRatio * 100) // 負値=塗り＋縁取り
        }
        if a.hasShadow {
            let sh = NSShadow()
            sh.shadowColor = UIColor.black.withAlphaComponent(0.55)
            sh.shadowBlurRadius = pt * 0.12
            sh.shadowOffset = CGSize(width: 0, height: pt * 0.06)
            attrs[.shadow] = sh
        }
        let text = a.text.isEmpty ? " " : a.text
        let str = NSAttributedString(string: text, attributes: attrs)
        let size = str.size()
        str.draw(at: CGPoint(x: -size.width / 2, y: -size.height / 2))
    }

    private static func drawArrow(_ a: Annotation, in c: CGContext, imageSize: CGSize) {
        let length = a.arrowLengthFraction * min(imageSize.width, imageSize.height)
        let thickness = length * a.arrowThicknessRatio
        c.addPath(ArrowGeometry.path(length: length, thickness: thickness))
        c.setFillColor(UIColor(hex: a.colorHex).cgColor)
        c.fillPath()
    }
}
