import UIKit
import SwiftUI

/// テキスト注釈の描画属性。プレビューと書き出しで共用。
enum TextRendering {

    // MARK: - 属性生成

    static func attributes(_ a: Annotation, fontPt: CGFloat) -> [NSAttributedString.Key: Any] {
        let font = AnnotationFont.uiFont(name: a.fontName, size: max(4, fontPt), weightIndex: a.fontWeightIndex)
        var attrs: [NSAttributedString.Key: Any] = [
            .font: font,
            .foregroundColor: UIColor(hex: a.colorHex),
            .paragraphStyle: paragraph(for: a.align),
        ]
        if a.hasOutline {
            attrs[.strokeColor] = UIColor(hex: a.outlineColorHex).withAlphaComponent(a.outlineOpacity)
            attrs[.strokeWidth] = -Double(a.outlineWidthRatio * 100) // 負値＝塗り＋縁取り
        }
        // 影は2パス描画で縁だけに付けるため、ここでは付与しない
        return attrs
    }

    /// 通常の塗り／縁取り属性に、はっきり見えるドロップシャドウを付与する。
    static func dropShadowAttributes(_ a: Annotation, fontPt: CGFloat) -> [NSAttributedString.Key: Any] {
        var attrs = attributes(a, fontPt: fontPt)
        let sh = NSShadow()
        sh.shadowColor = UIColor(hex: a.shadowColorHex).withAlphaComponent(0.6)
        sh.shadowBlurRadius = fontPt * 0.10
        sh.shadowOffset = CGSize(width: fontPt * 0.10, height: fontPt * 0.12) // 右下にはっきり落とす
        attrs[.shadow] = sh
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

    // MARK: - 影付き描画ヘルパー

    /// 影あり時のドロップシャドウ描画。2パスにすることで文字の色は変えずに影だけを後ろに残す。
    /// 1パス目: 影付きで描く（塗り＋影）／2パス目: 影なしの通常塗りを同位置に重ねて文字を元の色に戻す。
    static func drawWithShadow(_ a: Annotation, fontPt: CGFloat, string: String, in rect: CGRect) {
        NSAttributedString(string: string, attributes: dropShadowAttributes(a, fontPt: fontPt)).draw(in: rect)
        NSAttributedString(string: string, attributes: attributes(a, fontPt: fontPt)).draw(in: rect)
    }

    // MARK: - Private

    private static func paragraph(for align: Annotation.Align) -> NSParagraphStyle {
        let p = NSMutableParagraphStyle()
        switch align {
        case .left: p.alignment = .left
        case .center: p.alignment = .center
        case .right: p.alignment = .right
        }
        return p
    }
}

// MARK: - プレビュー用ビュー

/// 影あり時はドロップシャドウ付きで描く。
final class TwoPassTextView: UIView {
    var annotation: Annotation = Annotation(kind: .text) {
        didSet { invalidateIntrinsicContentSize(); setNeedsDisplay() }
    }
    var fontPt: CGFloat = 12 {
        didSet { invalidateIntrinsicContentSize(); setNeedsDisplay() }
    }

    override var intrinsicContentSize: CGSize {
        TextRendering.attributedString(annotation, fontPt: fontPt).size()
    }

    override func draw(_ rect: CGRect) {
        let s = TextRendering.displayString(annotation)
        let sz = TextRendering.attributedString(annotation, fontPt: fontPt).size()
        let r = CGRect(x: (rect.width - sz.width) / 2,
                       y: (rect.height - sz.height) / 2,
                       width: sz.width, height: sz.height)

        if annotation.hasShadow {
            TextRendering.drawWithShadow(annotation, fontPt: fontPt, string: s, in: r)
        } else {
            NSAttributedString(string: s, attributes: TextRendering.attributes(annotation, fontPt: fontPt)).draw(in: r)
        }
    }
}

struct StrokeTextLabel: UIViewRepresentable {
    let annotation: Annotation
    let fontPt: CGFloat

    func makeUIView(context: Context) -> TwoPassTextView {
        let v = TwoPassTextView()
        v.backgroundColor = .clear
        v.clipsToBounds = false
        return v
    }

    func updateUIView(_ v: TwoPassTextView, context: Context) {
        v.annotation = annotation
        v.fontPt = fontPt
    }

    func sizeThatFits(_ proposal: ProposedViewSize, uiView: TwoPassTextView, context: Context) -> CGSize? {
        uiView.intrinsicContentSize
    }
}
