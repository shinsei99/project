import SwiftUI

/// 補正プレビュー画像＋注釈レイヤーを重ねるキャンバス。
/// テキスト・矢印はそれぞれ自分の領域だけに収まり（TextLayer / ArrowLayer）、選択・操作が干渉しない。
struct AnnotatedImageView: View {
    @ObservedObject var state: EditorState

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
            .coordinateSpace(name: "canvas")
            .onTapGesture { state.selectedID = nil }
        }
    }

    @ViewBuilder
    private func annotationView(_ a: Annotation, fitted: CGRect) -> some View {
        if let b = state.binding(for: a.id) {
            switch a.kind {
            case .text:
                TextLayer(annotation: b, fitted: fitted, selected: a.id == state.selectedID,
                          onSelect: { state.selectedID = a.id },
                          onDelete: { state.delete(a.id) },
                          onBeginEdit: { state.pushUndo() })
            case .arrow:
                ArrowLayer(annotation: b, fitted: fitted, selected: a.id == state.selectedID,
                           onSelect: { state.selectedID = a.id },
                           onDelete: { state.delete(a.id) },
                           onBeginEdit: { state.pushUndo() })
            case .mosaic:
                MosaicLayer(annotation: b, mosaicImage: state.mosaicPreview, fitted: fitted,
                            selected: a.id == state.selectedID,
                            onSelect: { state.selectedID = a.id },
                            onBeginEdit: { state.pushUndo() })
            }
        }
    }
}
