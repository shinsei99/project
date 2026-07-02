import UIKit
import SwiftUI

/// テキスト注釈の描画属性。プレビュー(UILabel)と書き出し(Core Graphics)で共用し、
/// 縁取り・影を「本物のストローク」で滑らかに、かつ WYSIWYG で一致させる。
enum TextRendering {
    static func attributes(_ a: Annotation, fontPt: CGFloat) -> [NSAttributedString.Key: Any] {
        let font = AnnotationFont.uiFont(name: a.fontName, size: max(4, fontPt), bold: a.isBold)
        var attrs: [NSAttributedString.Key: Any] = [
            .font: font,
            .foregroundColor: UIColor(hex: a.colorHex),
        ]
        if a.hasOutline {
            attrs[.strokeColor] = UIColor(hex: a.outlineColorHex).withAlphaComponent(a.outlineOpacity)
            attrs[.strokeWidth] = -Double(a.outlineWidthRatio * 100) // 負値＝塗り＋縁取り
        }
        if a.hasShadow {
            let sh = NSShadow()
            sh.shadowColor = UIColor.black.withAlphaComponent(0.55)
            sh.shadowBlurRadius = fontPt * 0.12
            sh.shadowOffset = CGSize(width: 0, height: fontPt * 0.06)
            attrs[.shadow] = sh
        }
        let para = NSMutableParagraphStyle()
        para.alignment = .center
        attrs[.paragraphStyle] = para
        return attrs
    }

    static func attributedString(_ a: Annotation, fontPt: CGFloat) -> NSAttributedString {
        NSAttributedString(string: displayString(a), attributes: attributes(a, fontPt: fontPt))
    }

    /// 実際に描く文字列。縦書きは1文字ずつ改行して縦に積む。
    static func displayString(_ a: Annotation) -> String {
        let base = a.text.isEmpty ? " " : a.text
        guard a.isVertical else { return base }
        return base.replacingOccurrences(of: "\n", with: "")
            .map(String.init).joined(separator: "\n")
    }
}

/// CoreText の実ストロークで縁取りテキストを描くプレビュー用ラベル（滑らか・書き出しと一致）。
struct StrokeTextLabel: UIViewRepresentable {
    let annotation: Annotation
    let fontPt: CGFloat

    func makeUIView(context: Context) -> UILabel {
        let label = UILabel()
        label.numberOfLines = 0
        label.textAlignment = .center
        label.backgroundColor = .clear
        label.clipsToBounds = false
        return label
    }

    func updateUIView(_ label: UILabel, context: Context) {
        label.attributedText = TextRendering.attributedString(annotation, fontPt: fontPt)
        label.invalidateIntrinsicContentSize()
    }

    func sizeThatFits(_ proposal: ProposedViewSize, uiView: UILabel, context: Context) -> CGSize? {
        uiView.intrinsicContentSize
    }
}
