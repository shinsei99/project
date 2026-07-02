import SwiftUI

/// テキストを自分のバウンディングボックス内だけに収めて描く。
/// ドラッグ移動、右下ハンドルで拡大・回転、×で削除。
struct TextLayer: View {
    @Binding var annotation: Annotation
    let fitted: CGRect
    let selected: Bool
    let onSelect: () -> Void
    let onDelete: () -> Void

    @State private var moveStart: CGPoint?
    @State private var handleStart: HandleStart?
    struct HandleStart { var frac: CGFloat; var rot: Angle; var dist: CGFloat; var angle: Double }

    var body: some View {
        let fontPt = max(6, annotation.fontHeightFraction * fitted.height)
        let center = CGPoint(x: fitted.minX + annotation.position.x * fitted.width,
                             y: fitted.minY + annotation.position.y * fitted.height)
        let sz = TextRendering.attributedString(annotation, fontPt: fontPt).size()
        let pad = max(1, fontPt * annotation.outlineWidthRatio)
        let halfW = sz.width / 2 + pad
        let halfH = sz.height / 2 + pad
        let th = CGFloat(annotation.rotation.radians)
        let cs = cos(th), sn = sin(th)
        let rot: (CGFloat, CGFloat) -> CGPoint = { ox, oy in
            CGPoint(x: ox * cs - oy * sn, y: ox * sn + oy * cs)
        }
        let corners = [rot(halfW, halfH), rot(-halfW, halfH), rot(halfW, -halfH), rot(-halfW, -halfH)]
        let margin: CGFloat = 22
        let minx = (corners.map { $0.x }.min() ?? 0) - margin
        let maxx = (corners.map { $0.x }.max() ?? 0) + margin
        let miny = (corners.map { $0.y }.min() ?? 0) - margin
        let maxy = (corners.map { $0.y }.max() ?? 0) + margin
        let bbox = CGRect(x: center.x + minx, y: center.y + miny, width: maxx - minx, height: maxy - miny)
        let lc = CGPoint(x: -minx, y: -miny)
        let br = rot(halfW, halfH)

        ZStack(alignment: .topLeading) {
            StrokeTextLabel(annotation: annotation, fontPt: fontPt)
                .padding(pad)
                .contentShape(Rectangle())   // UILabel はタップを通さないのでヒット領域を明示
                .overlay {
                    if selected {
                        RoundedRectangle(cornerRadius: 4)
                            .strokeBorder(Color.accentColor,
                                          style: StrokeStyle(lineWidth: 1.5, dash: [5, 4]))
                    }
                }
                .rotationEffect(annotation.rotation)
                .position(lc)
                .onTapGesture { onSelect() }
                .gesture(moveGesture)

            if selected {
                ScaleRotateBadge()
                    .position(x: lc.x + br.x, y: lc.y + br.y)
                    .gesture(scaleRotateGesture(center: center))
            }
        }
        .frame(width: bbox.width, height: bbox.height)
        .position(x: bbox.midX, y: bbox.midY)
    }

    private var moveGesture: some Gesture {
        DragGesture(minimumDistance: 2, coordinateSpace: .named("canvas"))
            .onChanged { v in
                onSelect()
                if moveStart == nil { moveStart = annotation.position }
                let start = moveStart ?? annotation.position
                var p = CGPoint(x: start.x + v.translation.width / fitted.width,
                                y: start.y + v.translation.height / fitted.height)
                p.x = min(max(p.x, 0), 1); p.y = min(max(p.y, 0), 1)
                annotation.position = p
            }
            .onEnded { _ in moveStart = nil }
    }

    private func scaleRotateGesture(center: CGPoint) -> some Gesture {
        DragGesture(minimumDistance: 1, coordinateSpace: .named("canvas"))
            .onChanged { v in
                onSelect()
                let vec = CGPoint(x: v.location.x - center.x, y: v.location.y - center.y)
                let dist = max(1, hypot(vec.x, vec.y))
                let ang = atan2(vec.y, vec.x)
                if handleStart == nil {
                    handleStart = HandleStart(frac: annotation.fontHeightFraction,
                                              rot: annotation.rotation, dist: dist, angle: Double(ang))
                }
                guard let hs = handleStart else { return }
                annotation.fontHeightFraction = min(max(hs.frac * (dist / hs.dist), 0.02), 0.6)
                annotation.rotation = hs.rot + .radians(Double(ang) - hs.angle)
            }
            .onEnded { _ in handleStart = nil }
    }
}
