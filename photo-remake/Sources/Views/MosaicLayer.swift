import SwiftUI

/// モザイク領域（軸並行の矩形）。ピクセル化済み画像の該当部分を切り出して表示する。
/// 本体ドラッグで移動、右下ハンドルでサイズ変更。
struct MosaicLayer: View {
    @Binding var annotation: Annotation
    let mosaicImage: UIImage?
    let fitted: CGRect
    let selected: Bool
    let onSelect: () -> Void
    let onBeginEdit: () -> Void

    @State private var moveStart: CGPoint?
    @State private var sizeActive = false

    var body: some View {
        let region = regionNorm()
        let d = CGRect(x: fitted.minX + region.minX * fitted.width,
                       y: fitted.minY + region.minY * fitted.height,
                       width: region.width * fitted.width,
                       height: region.height * fitted.height)
        let cropped = mosaicImage?.cropped(to: region)
        let margin: CGFloat = 24
        let bbox = d.insetBy(dx: -margin, dy: -margin)
        let lc = CGRect(x: d.minX - bbox.minX, y: d.minY - bbox.minY, width: d.width, height: d.height)

        ZStack(alignment: .topLeading) {
            Group {
                if let cropped {
                    Image(uiImage: cropped).resizable().interpolation(.none)
                } else {
                    Rectangle().fill(Color.black.opacity(0.4))
                }
            }
            .frame(width: lc.width, height: lc.height)
            .overlay {
                if selected {
                    Rectangle().strokeBorder(Color.accentColor,
                                             style: StrokeStyle(lineWidth: 1.5, dash: [5, 4]))
                }
            }
            .position(x: lc.midX, y: lc.midY)
            .contentShape(Rectangle())
            .onTapGesture { onSelect() }
            .gesture(moveGesture)

            if selected {
                ResizeBadge()
                    .position(x: lc.maxX, y: lc.maxY)
                    .gesture(resizeGesture)
            }
        }
        .frame(width: bbox.width, height: bbox.height)
        .position(x: bbox.midX, y: bbox.midY)
    }

    private func regionNorm() -> CGRect {
        let x = min(max(annotation.position.x - annotation.mosaicHalfW, 0), 1)
        let y = min(max(annotation.position.y - annotation.mosaicHalfH, 0), 1)
        let x2 = min(max(annotation.position.x + annotation.mosaicHalfW, 0), 1)
        let y2 = min(max(annotation.position.y + annotation.mosaicHalfH, 0), 1)
        return CGRect(x: x, y: y, width: max(x2 - x, 0.001), height: max(y2 - y, 0.001))
    }

    private var moveGesture: some Gesture {
        DragGesture(minimumDistance: 2, coordinateSpace: .named("canvas"))
            .onChanged { v in
                onSelect()
                if moveStart == nil { moveStart = annotation.position; onBeginEdit() }
                let start = moveStart ?? annotation.position
                var p = CGPoint(x: start.x + v.translation.width / fitted.width,
                                y: start.y + v.translation.height / fitted.height)
                p.x = min(max(p.x, 0), 1); p.y = min(max(p.y, 0), 1)
                annotation.position = p
            }
            .onEnded { _ in moveStart = nil }
    }

    private var resizeGesture: some Gesture {
        DragGesture(minimumDistance: 1, coordinateSpace: .named("canvas"))
            .onChanged { v in
                onSelect()
                if !sizeActive { sizeActive = true; onBeginEdit() }
                let cx = fitted.minX + annotation.position.x * fitted.width
                let cy = fitted.minY + annotation.position.y * fitted.height
                annotation.mosaicHalfW = min(max(abs(v.location.x - cx) / fitted.width, 0.02), 0.5)
                annotation.mosaicHalfH = min(max(abs(v.location.y - cy) / fitted.height, 0.02), 0.5)
            }
            .onEnded { _ in sizeActive = false }
    }
}
