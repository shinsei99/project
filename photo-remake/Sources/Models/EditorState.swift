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
            selectedID = m.id
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

    func addText() {
        pushUndo()
        var a = Annotation.text()
        a.colorHex = "#FFFFFF"
        annotations.append(a)
        selectedID = a.id
    }
    func addArrow() {
        pushUndo()
        let a = Annotation.arrow()
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
        refreshMosaicPreview()
    }

    var hasMosaic: Bool { annotations.contains { $0.kind == .mosaic } }

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
