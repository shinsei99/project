import SwiftUI

/// テキスト注釈の見た目（縁取りは8方向オフセットで近似。書き出しは実ストロークで描く）。
struct TextAnnotationLabel: View {
    let annotation: Annotation
    let fontPt: CGFloat

    var body: some View {
        let a = annotation
        let font: Font = a.fontName.isEmpty
            ? .system(size: fontPt, weight: a.isBold ? .bold : .regular)
            : .custom(a.fontName, size: fontPt)
        let text = a.text.isEmpty ? " " : a.text

        ZStack {
            if a.hasOutline {
                let w = max(0.5, fontPt * a.outlineWidthRatio)
                ForEach(Array(offsets(w).enumerated()), id: \.offset) { _, off in
                    Text(text).font(font)
                        .foregroundColor(Color(hex: a.outlineColorHex).opacity(a.outlineOpacity))
                        .offset(x: off.width, y: off.height)
                }
            }
            Text(text).font(font).foregroundColor(Color(hex: a.colorHex))
        }
        .shadow(color: a.hasShadow ? Color.black.opacity(0.5) : .clear,
                radius: a.hasShadow ? fontPt * 0.10 : 0,
                x: 0, y: a.hasShadow ? fontPt * 0.05 : 0)
        .fixedSize()
    }

    private func offsets(_ d: CGFloat) -> [CGSize] {
        [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]
            .map { CGSize(width: CGFloat($0.0) * d, height: CGFloat($0.1) * d) }
    }
}

/// 矢印注釈の見た目（ArrowGeometry を共用）。
struct ArrowAnnotationView: View {
    let annotation: Annotation
    let displayLength: CGFloat

    var body: some View {
        let thickness = displayLength * annotation.arrowThicknessRatio
        let size = ArrowGeometry.boundingSize(length: displayLength, thickness: thickness)
        Canvas { ctx, sz in
            let path = Path(ArrowGeometry.path(length: displayLength, thickness: thickness))
                .applying(CGAffineTransform(translationX: sz.width / 2, y: sz.height / 2))
            ctx.fill(path, with: .color(Color(hex: annotation.colorHex)))
        }
        .frame(width: max(size.width, 1), height: max(size.height, 1))
    }
}
