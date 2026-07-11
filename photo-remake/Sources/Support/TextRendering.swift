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
            .paragraphStyle: centerPara,
        ]
        if a.hasOutline {
            attrs[.strokeColor] = UIColor(hex: a.outlineColorHex).withAlphaComponent(a.outlineOpacity)
            attrs[.strokeWidth] = -Double(a.outlineWidthRatio * 100) // 負値＝塗り＋縁取り
        }
        // 影は2パス描画で縁だけに付けるため、ここでは付与しない
        return attrs
    }

    /// 2パス描画 1パス目: 通常描画＋影。影はグリフ外側にも内側にも広がる。
    static func outlineWithShadowAttributes(_ a: Annotation, fontPt: CGFloat) -> [NSAttributedString.Key: Any] {
        let font = AnnotationFont.uiFont(name: a.fontName, size: max(4, fontPt), weightIndex: a.fontWeightIndex)
        var attrs: [NSAttributedString.Key: Any] = [
            .font: font,
            .foregroundColor: UIColor(hex: a.colorHex),
            .paragraphStyle: centerPara,
        ]
        if a.hasOutline {
            attrs[.strokeColor] = UIColor(hex: a.outlineColorHex).withAlphaComponent(a.outlineOpacity)
            attrs[.strokeWidth] = -Double(a.outlineWidthRatio * 100) // 負値＝塗り＋縁取り（通常と同じ）
        }
        let sh = NSShadow()
        sh.shadowColor = UIColor.black.withAlphaComponent(0.55)
        sh.shadowBlurRadius = fontPt * 0.14
        sh.shadowOffset = CGSize(width: fontPt * 0.05, height: fontPt * 0.07)
        attrs[.shadow] = sh
        return attrs
    }

    /// 2パス描画 2パス目: 塗りのみ・影なし。1パス目で内側に漏れた影を上書きして消す。
    static func fillOnlyAttributes(_ a: Annotation, fontPt: CGFloat) -> [NSAttributedString.Key: Any] {
        let font = AnnotationFont.uiFont(name: a.fontName, size: max(4, fontPt), weightIndex: a.fontWeightIndex)
        return [
            .font: font,
            .foregroundColor: UIColor(hex: a.colorHex),
            .paragraphStyle: centerPara,
        ]
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

    // MARK: - 2パス描画ヘルパー

    /// 影あり時に2パスで文字列を描く（rect はそのまま使う）。
    static func drawTwoPass(_ a: Annotation, fontPt: CGFloat, string: String, in rect: CGRect) {
        let outline = NSAttributedString(string: string, attributes: outlineWithShadowAttributes(a, fontPt: fontPt))
        let fill    = NSAttributedString(string: string, attributes: fillOnlyAttributes(a, fontPt: fontPt))
        outline.draw(in: rect)
        fill.draw(in: rect)
    }

    // MARK: - Private

    private static var centerPara: NSParagraphStyle {
        let p = NSMutableParagraphStyle()
        p.alignment = .center
        return p
    }
}

// MARK: - プレビュー用ビュー

/// 影あり時に2パスで描く（1パス目: 縁+影, 2パス目: 塗り）ことで縁のみに影を付与する。
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
            TextRendering.drawTwoPass(annotation, fontPt: fontPt, string: s, in: r)
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
