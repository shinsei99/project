import SwiftUI

/// トリミング画面。四隅ハンドルでサイズ変更、内側ドラッグで移動、比率プリセット、✓で確定。
struct CropView: View {
    @ObservedObject var state: EditorState
    @Environment(\.dismiss) private var dismiss

    @State private var rect = CGRect(x: 0, y: 0, width: 1, height: 1)
    @State private var moveStart: CGRect?
    /// 比率プリセット選択時にロックされる縦横比（正規化rectの width/height）。nil＝自由変形。
    @State private var lockedAspect: CGFloat?

    private enum Corner { case tl, tr, bl, br }
    private let presets: [(String, CGFloat?)] = [
        ("全体", nil), ("1:1", 1), ("4:3", 4.0 / 3.0), ("3:4", 3.0 / 4.0),
        ("16:9", 16.0 / 9.0), ("9:16", 9.0 / 16.0),
    ]

    var body: some View {
        GeometryReader { geo in
            let area = CGSize(width: geo.size.width, height: max(120, geo.size.height - 160))
            let fitted = aspectFitRect(imageSize: state.previewImage.size, in: area)
            VStack(spacing: 0) {
                ZStack {
                    Image(uiImage: state.previewImage)
                        .resizable()
                        .frame(width: fitted.width, height: fitted.height)
                        .position(x: fitted.midX, y: fitted.midY)
                    overlay(fitted: fitted, canvas: area)
                }
                .frame(width: geo.size.width, height: area.height)
                .coordinateSpace(name: "crop")

                controls.frame(height: 160)
            }
        }
        .background(Color.black.ignoresSafeArea())
    }

    private func overlay(fitted: CGRect, canvas: CGSize) -> some View {
        let d = disp(rect, fitted)
        return ZStack(alignment: .topLeading) {
            Canvas { ctx, size in
                var p = Path(CGRect(origin: .zero, size: size))
                p.addRect(d)
                ctx.fill(p, with: .color(.black.opacity(0.55)), style: FillStyle(eoFill: true))
            }
            .frame(width: canvas.width, height: canvas.height)
            .allowsHitTesting(false)

            Rectangle().stroke(Color.white, lineWidth: 1)
                .frame(width: d.width, height: d.height)
                .position(x: d.midX, y: d.midY)
                .allowsHitTesting(false)

            gridLines(d).allowsHitTesting(false)

            Rectangle().fill(Color.clear).contentShape(Rectangle())
                .frame(width: d.width, height: d.height)
                .position(x: d.midX, y: d.midY)
                .gesture(moveGesture(fitted))

            handle(.tl, at: CGPoint(x: d.minX, y: d.minY), fitted: fitted)
            handle(.tr, at: CGPoint(x: d.maxX, y: d.minY), fitted: fitted)
            handle(.bl, at: CGPoint(x: d.minX, y: d.maxY), fitted: fitted)
            handle(.br, at: CGPoint(x: d.maxX, y: d.maxY), fitted: fitted)
        }
    }

    private func gridLines(_ d: CGRect) -> some View {
        Path { p in
            for i in 1...2 {
                let x = d.minX + d.width * CGFloat(i) / 3
                p.move(to: CGPoint(x: x, y: d.minY)); p.addLine(to: CGPoint(x: x, y: d.maxY))
                let y = d.minY + d.height * CGFloat(i) / 3
                p.move(to: CGPoint(x: d.minX, y: y)); p.addLine(to: CGPoint(x: d.maxX, y: y))
            }
        }
        .stroke(Color.white.opacity(0.4), lineWidth: 0.5)
    }

    private func handle(_ corner: Corner, at p: CGPoint, fitted: CGRect) -> some View {
        Circle().fill(Color.white)
            .overlay(Circle().stroke(Color.accentColor, lineWidth: 2))
            .frame(width: 24, height: 24)
            .shadow(color: .black.opacity(0.4), radius: 2)
            .position(p)
            .gesture(
                DragGesture(coordinateSpace: .named("crop"))
                    .onChanged { v in resize(corner, to: normPoint(v.location, fitted)) }
            )
    }

    private var controls: some View {
        VStack(spacing: 14) {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 12) {
                    ForEach(presets, id: \.0) { name, aspect in
                        Button(name) { applyPreset(aspect) }
                            .buttonStyle(.bordered)
                            .tint(.white)
                    }
                }
                .padding(.horizontal)
            }
            HStack {
                Button { dismiss() } label: { Image(systemName: "xmark").font(.title3) }
                Spacer()
                Text("トリミング").font(.subheadline).foregroundStyle(.secondary)
                Spacer()
                Button {
                    state.applyCrop(rect)
                    dismiss()
                } label: { Image(systemName: "checkmark").font(.title3) }
            }
            .tint(.white)
            .padding(.horizontal, 24)
        }
        .padding(.top, 8)
    }

    // MARK: - 計算

    private func disp(_ r: CGRect, _ f: CGRect) -> CGRect {
        CGRect(x: f.minX + r.minX * f.width, y: f.minY + r.minY * f.height,
               width: r.width * f.width, height: r.height * f.height)
    }
    private func normPoint(_ p: CGPoint, _ f: CGRect) -> CGPoint {
        CGPoint(x: min(max((p.x - f.minX) / f.width, 0), 1),
                y: min(max((p.y - f.minY) / f.height, 0), 1))
    }

    private func moveGesture(_ fitted: CGRect) -> some Gesture {
        DragGesture(minimumDistance: 2, coordinateSpace: .named("crop"))
            .onChanged { v in
                if moveStart == nil { moveStart = rect }
                let base = moveStart ?? rect
                let dx = v.translation.width / fitted.width
                let dy = v.translation.height / fitted.height
                let nx = min(max(base.minX + dx, 0), 1 - base.width)
                let ny = min(max(base.minY + dy, 0), 1 - base.height)
                rect = CGRect(x: nx, y: ny, width: base.width, height: base.height)
            }
            .onEnded { _ in moveStart = nil }
    }

    private func resize(_ corner: Corner, to n: CGPoint) {
        // 比率ロック中は対角を固定して縦横比を保ったまま拡縮する。
        if let ratio = lockedAspect {
            resizeLocked(corner, to: n, ratio: ratio)
            return
        }
        var minX = rect.minX, minY = rect.minY, maxX = rect.maxX, maxY = rect.maxY
        switch corner {
        case .tl: minX = n.x; minY = n.y
        case .tr: maxX = n.x; minY = n.y
        case .bl: minX = n.x; maxY = n.y
        case .br: maxX = n.x; maxY = n.y
        }
        let minSize: CGFloat = 0.08
        minX = min(minX, maxX - minSize); minY = min(minY, maxY - minSize)
        maxX = max(maxX, minX + minSize); maxY = max(maxY, minY + minSize)
        minX = max(0, minX); minY = max(0, minY); maxX = min(1, maxX); maxY = min(1, maxY)
        rect = CGRect(x: minX, y: minY, width: maxX - minX, height: maxY - minY)
    }

    /// 縦横比 `ratio`（=width/height）を維持したまま四隅で拡縮。対角の隅を固定点にする。
    private func resizeLocked(_ corner: Corner, to n: CGPoint, ratio: CGFloat) {
        // ドラッグ隅の対角（固定点）と、固定点から見た伸びる向き。
        let anchor: CGPoint
        switch corner {
        case .tl: anchor = CGPoint(x: rect.maxX, y: rect.maxY)
        case .tr: anchor = CGPoint(x: rect.minX, y: rect.maxY)
        case .bl: anchor = CGPoint(x: rect.maxX, y: rect.minY)
        case .br: anchor = CGPoint(x: rect.minX, y: rect.minY)
        }
        let dirX: CGFloat = (corner == .tr || corner == .br) ? 1 : -1
        let dirY: CGFloat = (corner == .bl || corner == .br) ? 1 : -1

        // ドラッグ量から幅を決め、比率で高さを確定（大きい方の動きを優先＝操作が素直）。
        var w = max(abs(n.x - anchor.x), abs(n.y - anchor.y) * ratio)
        // 画面端（0〜1）に収まる最大幅と、最小サイズで両端をクランプ。
        let availX = dirX > 0 ? (1 - anchor.x) : anchor.x
        let availY = dirY > 0 ? (1 - anchor.y) : anchor.y
        let maxW = min(availX, availY * ratio)
        let minSize: CGFloat = 0.08
        let minW = max(minSize, minSize * ratio)
        w = min(max(w, minW), max(maxW, minW))
        let h = w / ratio

        let x0 = dirX > 0 ? anchor.x : anchor.x - w
        let y0 = dirY > 0 ? anchor.y : anchor.y - h
        rect = CGRect(x: x0, y: y0, width: w, height: h)
    }

    private func applyPreset(_ aspect: CGFloat?) {
        guard let a = aspect else {
            lockedAspect = nil          // 「全体」は自由変形に戻す
            rect = CGRect(x: 0, y: 0, width: 1, height: 1)
            return
        }
        let img = state.previewImage.size
        guard img.width > 0, img.height > 0 else { return }
        let rr = a * img.height / img.width
        var nw: CGFloat = 1, nh: CGFloat = 1
        if rr >= 1 { nw = 1; nh = 1 / rr } else { nh = 1; nw = rr }
        lockedAspect = rr               // 以降の四隅ドラッグはこの比率を維持
        rect = CGRect(x: (1 - nw) / 2, y: (1 - nh) / 2, width: nw, height: nh)
    }
}
