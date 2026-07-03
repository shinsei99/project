import SwiftUI

/// 2点（尾・先端）を結ぶ矢印シェイプ。座標は絶対値（親の座標空間）で受け取る。
struct ArrowBetweenShape: Shape {
    var from: CGPoint
    var to: CGPoint
    var thickness: CGFloat

    func path(in rect: CGRect) -> Path {
        Path(ArrowGeometry.pathBetween(from: from, to: to, thickness: thickness))
    }
}

/// 矢印を自分のバウンディングボックス内だけに収めて描く（他要素のタップを奪わない）。
/// 選択中は両端ハンドルで向き・長さを直感操作、本体ドラッグで移動、×で削除。
struct ArrowLayer: View {
    @Binding var annotation: Annotation
    let fitted: CGRect
    let selected: Bool
    let onSelect: () -> Void
    let onDelete: () -> Void
    let onBeginEdit: () -> Void

    @State private var moveBase: (CGPoint, CGPoint)?
    @State private var handleActive = false

    var body: some View {
        let a = toPoint(annotation.arrowStart)
        let b = toPoint(annotation.arrowEnd)
        let length = max(1, hypot(b.x - a.x, b.y - a.y))
        let thickness = length * annotation.arrowThicknessRatio
        let margin: CGFloat = 26
        let minX = min(a.x, b.x) - margin, minY = min(a.y, b.y) - margin
        let maxX = max(a.x, b.x) + margin, maxY = max(a.y, b.y) + margin
        let bbox = CGRect(x: minX, y: minY, width: maxX - minX, height: maxY - minY)
        let aL = CGPoint(x: a.x - minX, y: a.y - minY)
        let bL = CGPoint(x: b.x - minX, y: b.y - minY)

        ZStack(alignment: .topLeading) {
            ArrowBetweenShape(from: aL, to: bL, thickness: thickness)
                .fill(Color(hex: annotation.colorHex))
                .overlay {
                    if selected {
                        ArrowBetweenShape(from: aL, to: bL, thickness: thickness)
                            .stroke(Color.white.opacity(0.9), lineWidth: 1)
                    }
                }
                .contentShape(ArrowBetweenShape(from: aL, to: bL, thickness: max(thickness, 34)))
                .onTapGesture { onSelect() }
                .gesture(bodyDrag)

            if selected {
                handle(at: aL) { annotation.arrowStart = toNorm($0) }
                handle(at: bL) { annotation.arrowEnd = toNorm($0) }
            }
        }
        .frame(width: bbox.width, height: bbox.height)
        .position(x: bbox.midX, y: bbox.midY)
    }

    private var bodyDrag: some Gesture {
        DragGesture(minimumDistance: 2, coordinateSpace: .named("canvas"))
            .onChanged { v in
                onSelect()
                if moveBase == nil { moveBase = (annotation.arrowStart, annotation.arrowEnd); onBeginEdit() }
                guard let base = moveBase else { return }
                let dx = v.translation.width / fitted.width
                let dy = v.translation.height / fitted.height
                annotation.arrowStart = clamp(CGPoint(x: base.0.x + dx, y: base.0.y + dy))
                annotation.arrowEnd = clamp(CGPoint(x: base.1.x + dx, y: base.1.y + dy))
            }
            .onEnded { _ in moveBase = nil }
    }

    private func handle(at p: CGPoint, update: @escaping (CGPoint) -> Void) -> some View {
        EndpointBadge()
            .position(p)
            .gesture(
                DragGesture(coordinateSpace: .named("canvas"))
                    .onChanged { v in
                        onSelect()
                        if !handleActive { handleActive = true; onBeginEdit() }
                        update(v.location)
                    }
                    .onEnded { _ in handleActive = false }
            )
    }

    private func toPoint(_ n: CGPoint) -> CGPoint {
        CGPoint(x: fitted.minX + n.x * fitted.width, y: fitted.minY + n.y * fitted.height)
    }
    private func toNorm(_ p: CGPoint) -> CGPoint {
        clamp(CGPoint(x: (p.x - fitted.minX) / fitted.width,
                      y: (p.y - fitted.minY) / fitted.height))
    }
    private func clamp(_ p: CGPoint) -> CGPoint {
        CGPoint(x: min(max(p.x, 0), 1), y: min(max(p.y, 0), 1))
    }
}
