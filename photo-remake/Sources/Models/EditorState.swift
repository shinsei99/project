import SwiftUI
import Combine

/// 編集セッションの状態。元画像は非破壊で保持し、補正・注釈を別管理する。
@MainActor
final class EditorState: ObservableObject {
    /// 取り込んだ元画像（向き正規化済み・フル解像度）。
    @Published private(set) var originalImage: UIImage
    /// ライブプレビュー用に縮小した基底画像。
    private var previewBase: UIImage
    /// 補正を適用したプレビュー画像（表示用）。
    @Published private(set) var previewImage: UIImage

    @Published var adjustments = Adjustments() { didSet { schedulePreview() } }
    @Published var annotations: [Annotation] = []
    @Published var selectedID: UUID?
    /// キャンバス上でテキスト内容を直接編集中の注釈 ID（nil で編集終了）。
    @Published var editingTextID: UUID?

    /// モザイク用にピクセル化したプレビュー（モザイク領域はこれを切り出して表示）。
    @Published private(set) var mosaicPreview: UIImage?
    /// モザイクの粗さ（画像幅に対するブロック割合）。
    @Published var mosaicBlockFraction: CGFloat = 0.045 { didSet { refreshMosaicPreview() } }

    // MARK: 取り消し（Undo）
    private struct Snapshot {
        var annotations: [Annotation]
        var adjustments: Adjustments
        var originalImage: UIImage
        var previewBase: UIImage
        var mosaicBlockFraction: CGFloat
        var selectedID: UUID?
    }
    private var undoStack: [Snapshot] = []
    @Published private(set) var canUndo = false

    private var previewTask: Task<Void, Never>?

    init(image: UIImage, seedDemo: Bool = false) {
        let up = image.normalizedUp()
        self.originalImage = up
        let base = up.downscaled(maxPixels: 1600)
        self.previewBase = base
        self.previewImage = base
        if seedDemo {
            var t = Annotation.text(at: CGPoint(x: 0.52, y: 0.44))
            t.text = "テスト"
            t.colorHex = "#FFFFFF"
            t.fontHeightFraction = 0.09
            annotations.append(t)
            var arrow = Annotation.arrow(at: CGPoint(x: 0.36, y: 0.52))
            arrow.arrowStart = CGPoint(x: 0.52, y: 0.42)   // 尾（右上）
            arrow.arrowEnd = CGPoint(x: 0.30, y: 0.60)     // 先端（左下）
            annotations.append(arrow)
            var m = Annotation.mosaic(at: CGPoint(x: 0.72, y: 0.5))
            m.mosaicHalfW = 0.18; m.mosaicHalfH = 0.08
            annotations.append(m)
            var box = Annotation.shape(.roundedRect, at: CGPoint(x: 0.34, y: 0.72))
            box.shapeHalfW = 0.22; box.shapeHalfH = 0.10
            annotations.append(box)
            var star = Annotation.shape(.star, at: CGPoint(x: 0.74, y: 0.22))
            star.shapeDrawStyle = .both
            star.colorHex = "#FFCC00"; star.strokeColorHex = "#FF3B30"
            star.rotation = .degrees(12)
            annotations.append(star)
            var bubble = Annotation.shape(.bubble, at: CGPoint(x: 0.30, y: 0.16))
            bubble.shapeDrawStyle = .fill
            bubble.colorHex = "#007AFF"; bubble.shapeOpacity = 0.55
            annotations.append(bubble)
            selectedID = star.id
            refreshMosaicPreview()
        }
    }

    var selectedIndex: Int? {
        guard let id = selectedID else { return nil }
        return annotations.firstIndex { $0.id == id }
    }
    var selected: Annotation? {
        guard let i = selectedIndex else { return nil }
        return annotations[i]
    }

    func binding(for id: UUID) -> Binding<Annotation>? {
        guard let initial = annotations.first(where: { $0.id == id }) else { return nil }
        // フォールバックに Annotation(kind:.text) を使うと新UUID が生成され
        // selectedID と不一致になるバグがあるため、初期値（同じ UUID）をキャプチャして使う。
        return Binding(
            get: { self.annotations.first(where: { $0.id == id }) ?? initial },
            set: { newValue in
                if let i = self.annotations.firstIndex(where: { $0.id == id }) {
                    self.annotations[i] = newValue
                }
            }
        )
    }

    /// 入力画面で確定した内容から新規テキストを追加する。
    func insertText(_ text: String, align: Annotation.Align) {
        pushUndo()
        var a = Annotation.text()
        a.colorHex = "#FFFFFF"
        a.text = text
        a.align = align
        annotations.append(a)
        selectedID = a.id
    }

    /// 既存テキストの内容・行揃えを更新する。
    func updateText(_ id: UUID, text: String, align: Annotation.Align) {
        guard let i = annotations.firstIndex(where: { $0.id == id }) else { return }
        pushUndo()
        annotations[i].text = text
        annotations[i].align = align
    }
    func addArrow() {
        pushUndo()
        let a = Annotation.arrow()
        annotations.append(a)
        selectedID = a.id
    }
    /// 「図形」パレットから追加する（矢印もここに含まれる）。
    func addTool(_ tool: AnnotationTool) {
        switch tool {
        case .arrow: addArrow()
        case .shape(let k): addShape(k)
        }
    }

    /// 選択中の注釈の種類を変える。矢印⇄図形も、位置・大きさ・向きを引き継いで入れ替える。
    func convertSelected(to tool: AnnotationTool) {
        guard let i = selectedIndex else { return }
        var a = annotations[i]
        let W = max(1, originalImage.size.width), H = max(1, originalImage.size.height)

        switch (a.kind, tool) {
        case (.shape, .shape(let k)):
            guard a.shapeKind != k else { return }
            pushUndo()
            a.shapeKind = k

        case (.arrow, .shape(let k)):
            pushUndo()
            // 2点（尾・先端）から 中心・長さ・向き を作って図形へ移す
            let dx = (a.arrowEnd.x - a.arrowStart.x) * W
            let dy = (a.arrowEnd.y - a.arrowStart.y) * H
            let len = max(1, (dx * dx + dy * dy).squareRoot())
            a.kind = .shape
            a.shapeKind = k
            a.position = CGPoint(x: (a.arrowStart.x + a.arrowEnd.x) / 2,
                                 y: (a.arrowStart.y + a.arrowEnd.y) / 2)
            a.rotation = .radians(atan2(Double(dy), Double(dx)))
            a.shapeHalfW = min(max(len / 2 / W, 0.02), 0.6)
            a.shapeHalfH = min(max(len * a.arrowThicknessRatio * 1.3 / H, 0.02), 0.6)
            a.shapeDrawStyle = .fill          // 矢印は塗りなので塗りで引き継ぐ
            a.strokeColorHex = a.colorHex

        case (.shape, .arrow):
            pushUndo()
            let halfLen = a.shapeHalfW * W
            let th = a.rotation.radians
            let cx = a.position.x * W, cy = a.position.y * H
            let ex = cos(th) * halfLen, ey = sin(th) * halfLen
            a.kind = .arrow
            a.arrowStart = clamp01(CGPoint(x: (cx - ex) / W, y: (cy - ey) / H))
            a.arrowEnd = clamp01(CGPoint(x: (cx + ex) / W, y: (cy + ey) / H))
            let thickness = a.shapeHalfH * H * 2 / 1.3
            a.arrowThicknessRatio = min(max(thickness / max(1, halfLen * 2), 0.06), 0.30)
            // 塗りだけの図形だった場合は塗り色、枠線だけなら枠線色を矢印の色にする
            if a.shapeDrawStyle == .stroke { a.colorHex = a.strokeColorHex }
            a.rotation = .zero

        default:
            return                              // 矢印→矢印など、変化なし
        }
        annotations[i] = a
        refreshMosaicPreview()
    }

    private func clamp01(_ p: CGPoint) -> CGPoint {
        CGPoint(x: min(max(p.x, 0), 1), y: min(max(p.y, 0), 1))
    }

    func addShape(_ kind: ShapeKind) {
        pushUndo()
        let a = Annotation.shape(kind)
        annotations.append(a)
        selectedID = a.id
    }
    func addMosaic() {
        pushUndo()
        let a = Annotation.mosaic()
        annotations.append(a)
        selectedID = a.id
        refreshMosaicPreview()
    }
    func deleteSelected() {
        guard let id = selectedID else { return }
        delete(id)
    }
    func delete(_ id: UUID) {
        pushUndo()
        annotations.removeAll { $0.id == id }
        if selectedID == id { selectedID = nil }
        if editingTextID == id { editingTextID = nil }
        refreshMosaicPreview()
    }

    var hasMosaic: Bool { annotations.contains { $0.kind == .mosaic } }

    /// 何か編集したか（写真の入れ替え前に確認を出すかの判定に使う）。
    var hasEdits: Bool { !annotations.isEmpty || !adjustments.isIdentity || canUndo }

    // MARK: - モザイク・プレビュー

    func refreshMosaicPreview() {
        guard hasMosaic else { mosaicPreview = nil; return }
        let img = previewImage
        let bf = mosaicBlockFraction
        Task { [weak self] in
            let m = await ImageProcessor.shared.pixellate(img, blockFraction: bf)
            self?.mosaicPreview = m
        }
    }

    // MARK: - 取り消し（Undo）

    /// 変更の直前に現在状態を退避（各操作・ジェスチャー開始時に呼ぶ）。
    func pushUndo() {
        undoStack.append(Snapshot(
            annotations: annotations, adjustments: adjustments,
            originalImage: originalImage, previewBase: previewBase,
            mosaicBlockFraction: mosaicBlockFraction, selectedID: selectedID))
        if undoStack.count > 40 { undoStack.removeFirst() }
        canUndo = true
    }

    func undo() {
        guard let s = undoStack.popLast() else { return }
        annotations = s.annotations
        originalImage = s.originalImage
        previewBase = s.previewBase
        selectedID = s.selectedID
        mosaicBlockFraction = s.mosaicBlockFraction
        adjustments = s.adjustments      // didSet で schedulePreview
        canUndo = !undoStack.isEmpty
        previewImage = previewBase
        schedulePreview()
        refreshMosaicPreview()
    }
    func bringSelectedToFront() {
        guard let i = selectedIndex else { return }
        let a = annotations.remove(at: i)
        annotations.append(a)
    }

    // MARK: - プレビュー再計算（デバウンス）

    private func schedulePreview() {
        previewTask?.cancel()
        let adj = adjustments
        let base = previewBase
        previewTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 40_000_000) // 40ms デバウンス
            if Task.isCancelled { return }
            let output = await ImageProcessor.shared.render(adj, on: base)
            if Task.isCancelled { return }
            self?.previewImage = output
            self?.refreshMosaicPreview()
        }
    }

    /// 正規化矩形で画像を切り抜き、既存の注釈座標を新しい画像基準へ変換する。
    func applyCrop(_ norm: CGRect) {
        let r = CGRect(x: max(0, norm.minX), y: max(0, norm.minY),
                       width: norm.width, height: norm.height)
            .intersection(CGRect(x: 0, y: 0, width: 1, height: 1))
        guard r.width > 0.02, r.height > 0.02,
              r.width < 0.999 || r.height < 0.999 else { return }
        pushUndo()

        originalImage = originalImage.cropped(to: r)
        previewBase = originalImage.downscaled(maxPixels: 1600)

        for i in annotations.indices {
            annotations[i].position = remap(annotations[i].position, in: r)
            annotations[i].arrowStart = remap(annotations[i].arrowStart, in: r)
            annotations[i].arrowEnd = remap(annotations[i].arrowEnd, in: r)
            annotations[i].fontHeightFraction /= r.height   // 画像が小さくなる分、文字割合は拡大
            annotations[i].mosaicHalfW /= r.width
            annotations[i].mosaicHalfH /= r.height
            annotations[i].shapeHalfW /= r.width
            annotations[i].shapeHalfH /= r.height
            // 枠線は画像の短辺基準なので、短辺の縮み分だけ割合を戻す
            annotations[i].shapeLineWidthRatio /= min(r.width, r.height)
        }
        previewImage = previewBase
        schedulePreview()
        refreshMosaicPreview()
    }

    private func remap(_ p: CGPoint, in r: CGRect) -> CGPoint {
        CGPoint(x: (p.x - r.minX) / r.width, y: (p.y - r.minY) / r.height)
    }

    /// 保存用にフル解像度で補正＋注釈を焼き込んだ最終画像を生成。
    func renderFinalImage() async -> UIImage {
        let adjusted = await ImageProcessor.shared.render(adjustments, on: originalImage)
        var mosaicFull: UIImage?
        if hasMosaic {
            mosaicFull = await ImageProcessor.shared.pixellate(adjusted, blockFraction: mosaicBlockFraction)
        }
        return ImageExporter.compose(base: adjusted, mosaic: mosaicFull, annotations: annotations)
    }
}
