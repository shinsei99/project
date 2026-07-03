import SwiftUI

/// テキスト注釈の見た目。CoreText の実ストロークで縁取りを滑らかに描く（書き出しと一致）。
struct TextAnnotationLabel: View {
    let annotation: Annotation
    let fontPt: CGFloat

    var body: some View {
        StrokeTextLabel(annotation: annotation, fontPt: fontPt)
            .fixedSize()
            // ストロークがフレーム外へ少しはみ出すぶんの余白
            .padding(max(1, fontPt * annotation.outlineWidthRatio))
    }
}
