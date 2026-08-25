import SwiftUI

/// 図形注釈の見た目（SwiftUI 側）。書き出しと同じ `ShapeGeometry` のパスを使う。
struct AnnotationShape: Shape {
    var kind: ShapeKind
    func path(in rect: CGRect) -> Path { Path(ShapeGeometry.path(kind, in: rect)) }
}

/// 図形を自分のバウンディングボックス内だけに描く（他要素のタップを奪わない）。
/// 本体ドラッグ＝移動、右下ハンドル＝サイズ変更、右上ハンドル＝回転。
struct ShapeLayer: View {
    @Binding var annotation: Annotation
    let fitted: CGRect
    let selected: Bool
    let onSelect: () -> Void
    let onBeginEdit: () -> Void

    @State private var moveStart: CGPoint?
    @State private var sizeActive = false
    @State private var rotStart: (rot: Angle, angle: Double)?

    var body: some View {
        let center = CGPoint(x: fitted.minX + annotation.position.x * fitted.width,
                             y: fitted.minY + annotation.position.y * fitted.height)
        let halfW = max(4, annotation.shapeHalfW * fitted.width)
        let halfH = max(4, annotation.shapeHalfH * fitted.height)
        let lw = lineWidth
        let th = CGFloat(annotation.rotation.radians)
        let cs = cos(th), sn = sin(th)
        let rot: (CGFloat, CGFloat) -> CGPoint = { ox, oy in
            CGPoint(x: ox * cs - oy * sn, y: ox * sn + oy * cs)
        }
        let corners = [rot(halfW, halfH), rot(-halfW, halfH), rot(halfW, -halfH), rot(-halfW, -halfH)]
        let margin: CGFloat = 24 + lw
        let minx = (corners.map(\.x).min() ?? 0) - margin
        let maxx = (corners.map(\.x).max() ?? 0) + margin
        let miny = (corners.map(\.y).min() ?? 0) - margin
        let maxy = (corners.map(\.y).max() ?? 0) + margin
        let bbox = CGRect(x: center.x + minx, y: center.y + miny, width: maxx - minx, height: maxy - miny)
        let lc = CGPoint(x: -minx, y: -miny)
        let brOff = rot(halfW, halfH)     // 右下＝サイズ変更
        let trOff = rot(halfW, -halfH)    // 右上＝回転

        ZStack(alignment: .topLeading) {
            drawing(lineWidth: lw)
                .frame(width: halfW * 2, height: halfH * 2)
                .overlay {
                    if selected {
                        Rectangle().strokeBorder(Color.accentColor,
                                                 style: StrokeStyle(lineWidth: 1.5, dash: [5, 4]))
                    }
                }
                .contentShape(AnnotationShape(kind: annotation.shapeKind))
                .rotationEffect(annotation.rotation)
                .position(lc)
                .onTapGesture { onSelect() }
                .gesture(moveGesture)

            if selected {
                ResizeBadge()
                    .position(x: lc.x + brOff.x, y: lc.y + brOff.y)
                    .gesture(resizeGesture(center: center, angle: th))
                RotateBadge()
                    .position(x: lc.x + trOff.x, y: lc.y + trOff.y)
                    .gesture(rotateGesture(center: center))
            }
        }
        .frame(width: bbox.width, height: bbox.height)
        .position(x: bbox.midX, y: bbox.midY)
    }

    /// 枠線の太さ（画像の短辺基準＝書き出しと同じ計算）。
    private var lineWidth: CGFloat {
        max(1, annotation.shapeLineWidthRatio * min(fitted.width, fitted.height))
    }

    @ViewBuilder private func drawing(lineWidth lw: CGFloat) -> some View {
        let s = AnnotationShape(kind: annotation.shapeKind)
        ZStack {
            if annotation.shapeDrawStyle != .stroke {
                s.fill(Color(hex: annotation.colorHex).opacity(annotation.shapeOpacity))
            }
            if annotation.shapeDrawStyle != .fill {
                s.stroke(Color(hex: annotation.strokeColorHex),
                         style: StrokeStyle(lineWidth: lw, lineJoin: .round))
            }
        }
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

    /// 右下ハンドル：回転を打ち消した図形の座標系で、中心からの距離＝半サイズにする。
    private func resizeGesture(center: CGPoint, angle: CGFloat) -> some Gesture {
        DragGesture(minimumDistance: 1, coordinateSpace: .named("canvas"))
            .onChanged { v in
                onSelect()
                if !sizeActive { sizeActive = true; onBeginEdit() }
                let dx = v.location.x - center.x, dy = v.location.y - center.y
                let lx = dx * cos(-angle) - dy * sin(-angle)
                let ly = dx * sin(-angle) + dy * cos(-angle)
                annotation.shapeHalfW = min(max(abs(lx) / fitted.width, 0.02), 0.6)
                annotation.shapeHalfH = min(max(abs(ly) / fitted.height, 0.02), 0.6)
            }
            .onEnded { _ in sizeActive = false }
    }

    /// 右上ハンドル：中心まわりの角度で回転。
    private func rotateGesture(center: CGPoint) -> some Gesture {
        DragGesture(minimumDistance: 1, coordinateSpace: .named("canvas"))
            .onChanged { v in
                onSelect()
                let ang = atan2(v.location.y - center.y, v.location.x - center.x)
                if rotStart == nil { rotStart = (annotation.rotation, Double(ang)); onBeginEdit() }
                guard let s = rotStart else { return }
                annotation.rotation = s.rot + .radians(Double(ang) - s.angle)
            }
            .onEnded { _ in rotStart = nil }
    }
}
