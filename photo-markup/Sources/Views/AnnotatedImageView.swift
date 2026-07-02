import SwiftUI

/// 補正プレビュー画像＋注釈レイヤーを重ね、ドラッグ移動・ピンチ拡大・回転を扱うキャンバス。
struct AnnotatedImageView: View {
    @ObservedObject var state: EditorState

    @State private var moveStart: CGPoint?
    @State private var scaleStart: CGFloat?
    @State private var rotStart: Angle?

    var body: some View {
        GeometryReader { geo in
            let fitted = aspectFitRect(imageSize: state.previewImage.size, in: geo.size)
            ZStack {
                Image(uiImage: state.previewImage)
                    .resizable()
                    .frame(width: fitted.width, height: fitted.height)
                    .position(x: fitted.midX, y: fitted.midY)

                ForEach(state.annotations) { a in
                    annotationView(a, fitted: fitted)
                }
            }
            .frame(width: geo.size.width, height: geo.size.height)
            .contentShape(Rectangle())
            .onTapGesture { state.selectedID = nil }
        }
    }

    @ViewBuilder
    private func annotationView(_ a: Annotation, fitted: CGRect) -> some View {
        let center = CGPoint(x: fitted.minX + a.position.x * fitted.width,
                             y: fitted.minY + a.position.y * fitted.height)
        let selected = a.id == state.selectedID

        contentView(a, fitted: fitted)
            .padding(6)
            .overlay {
                if selected {
                    RoundedRectangle(cornerRadius: 4)
                        .strokeBorder(Color.accentColor,
                                      style: StrokeStyle(lineWidth: 1.5, dash: [5, 4]))
                }
            }
            .rotationEffect(a.rotation)
            .position(center)
            .gesture(combinedGesture(for: a, fitted: fitted))
            .onTapGesture { state.selectedID = a.id }
    }

    @ViewBuilder
    private func contentView(_ a: Annotation, fitted: CGRect) -> some View {
        switch a.kind {
        case .text:
            TextAnnotationLabel(annotation: a,
                                fontPt: max(6, a.fontHeightFraction * fitted.height))
        case .arrow:
            ArrowAnnotationView(annotation: a,
                                displayLength: a.arrowLengthFraction * min(fitted.width, fitted.height))
        }
    }

    private func combinedGesture(for a: Annotation, fitted: CGRect) -> some Gesture {
        let drag = DragGesture(minimumDistance: 2)
            .onChanged { v in
                if state.selectedID != a.id { state.selectedID = a.id }
                guard let b = state.binding(for: a.id) else { return }
                if moveStart == nil { moveStart = b.wrappedValue.position }
                let start = moveStart ?? b.wrappedValue.position
                var p = CGPoint(x: start.x + v.translation.width / fitted.width,
                                y: start.y + v.translation.height / fitted.height)
                p.x = min(max(p.x, 0), 1)
                p.y = min(max(p.y, 0), 1)
                b.wrappedValue.position = p
            }
            .onEnded { _ in moveStart = nil }

        let magnify = MagnificationGesture()
            .onChanged { scale in
                guard let b = state.binding(for: a.id) else { return }
                switch b.wrappedValue.kind {
                case .text:
                    if scaleStart == nil { scaleStart = b.wrappedValue.fontHeightFraction }
                    let base = scaleStart ?? b.wrappedValue.fontHeightFraction
                    b.wrappedValue.fontHeightFraction = min(max(base * scale, 0.02), 0.5)
                case .arrow:
                    if scaleStart == nil { scaleStart = b.wrappedValue.arrowLengthFraction }
                    let base = scaleStart ?? b.wrappedValue.arrowLengthFraction
                    b.wrappedValue.arrowLengthFraction = min(max(base * scale, 0.05), 1.2)
                }
            }
            .onEnded { _ in scaleStart = nil }

        let rotate = RotationGesture()
            .onChanged { ang in
                guard let b = state.binding(for: a.id) else { return }
                if rotStart == nil { rotStart = b.wrappedValue.rotation }
                b.wrappedValue.rotation = (rotStart ?? .zero) + ang
            }
            .onEnded { _ in rotStart = nil }

        return drag.simultaneously(with: magnify).simultaneously(with: rotate)
    }
}
