import SwiftUI

/// テキストを自分のバウンディングボックス内だけに収めて描く。
/// 1本指ドラッグ＝移動、右下ハンドル＝拡大縮小、右上ハンドル＝回転、2本指ピンチ＝拡大（回転はしない）。
struct TextLayer: View {
    @Binding var annotation: Annotation
    let fitted: CGRect
    let selected: Bool
    let onSelect: () -> Void
    let onDelete: () -> Void
    let onBeginEdit: () -> Void

    @State private var moveStart: CGPoint?
    @State private var scalePinchStart: CGFloat?
    @State private var scaleHandleStart: (frac: CGFloat, dist: CGFloat)?
    @State private var rotHandleStart: (rot: Angle, angle: Double)?

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
        let brOff = rot(halfW, halfH)     // 右下＝拡大縮小
        let trOff = rot(halfW, -halfH)    // 右上＝回転

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
                .gesture(bodyGesture)

            if selected {
                ResizeBadge()
                    .position(x: lc.x + brOff.x, y: lc.y + brOff.y)
                    .gesture(scaleGesture(center: center))
                RotateBadge()
                    .position(x: lc.x + trOff.x, y: lc.y + trOff.y)
                    .gesture(rotateGesture(center: center))
            }
        }
        .frame(width: bbox.width, height: bbox.height)
        .position(x: bbox.midX, y: bbox.midY)
    }

    /// 1本指=移動、2本指ピンチ=拡大のみ（回転はしない）。
    private var bodyGesture: some Gesture {
        let drag = DragGesture(minimumDistance: 2, coordinateSpace: .named("canvas"))
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

        let magnify = MagnificationGesture()
            .onChanged { scale in
                onSelect()
                if scalePinchStart == nil { scalePinchStart = annotation.fontHeightFraction; onBeginEdit() }
                let base = scalePinchStart ?? annotation.fontHeightFraction
                annotation.fontHeightFraction = min(max(base * scale, 0.02), 0.6)
            }
            .onEnded { _ in scalePinchStart = nil }

        return drag.simultaneously(with: magnify)
    }

    /// 右下ハンドル：中心からの距離で拡大縮小のみ。
    private func scaleGesture(center: CGPoint) -> some Gesture {
        DragGesture(minimumDistance: 1, coordinateSpace: .named("canvas"))
            .onChanged { v in
                onSelect()
                let dist = max(1, hypot(v.location.x - center.x, v.location.y - center.y))
                if scaleHandleStart == nil {
                    scaleHandleStart = (annotation.fontHeightFraction, dist); onBeginEdit()
                }
                guard let s = scaleHandleStart else { return }
                annotation.fontHeightFraction = min(max(s.frac * (dist / s.dist), 0.02), 0.6)
            }
            .onEnded { _ in scaleHandleStart = nil }
    }

    /// 右上ハンドル：中心まわりの角度で回転のみ。
    private func rotateGesture(center: CGPoint) -> some Gesture {
        DragGesture(minimumDistance: 1, coordinateSpace: .named("canvas"))
            .onChanged { v in
                onSelect()
                let ang = atan2(v.location.y - center.y, v.location.x - center.x)
                if rotHandleStart == nil { rotHandleStart = (annotation.rotation, Double(ang)); onBeginEdit() }
                guard let s = rotHandleStart else { return }
                annotation.rotation = s.rot + .radians(Double(ang) - s.angle)
            }
            .onEnded { _ in rotHandleStart = nil }
    }
}
