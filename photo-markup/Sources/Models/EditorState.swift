import SwiftUI
import Combine

/// 編集セッションの状態。元画像は非破壊で保持し、補正・注釈を別管理する。
@MainActor
final class EditorState: ObservableObject {
    /// 取り込んだ元画像（向き正規化済み・フル解像度）。
    @Published private(set) var originalImage: UIImage
    /// ライブプレビュー用に縮小した基底画像。
    private let previewBase: UIImage
    /// 補正を適用したプレビュー画像（表示用）。
    @Published private(set) var previewImage: UIImage

    @Published var adjustments = Adjustments() { didSet { schedulePreview() } }
    @Published var annotations: [Annotation] = []
    @Published var selectedID: UUID?

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
            var arrow = Annotation.arrow(at: CGPoint(x: 0.34, y: 0.52))
            arrow.rotation = .degrees(150)
            annotations.append(arrow)
            selectedID = t.id
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
        guard let i = annotations.firstIndex(where: { $0.id == id }) else { return nil }
        return Binding(
            get: { self.annotations[i] },
            set: { self.annotations[i] = $0 }
        )
    }

    func addText() {
        var a = Annotation.text()
        a.colorHex = "#FFFFFF"
        annotations.append(a)
        selectedID = a.id
    }
    func addArrow() {
        let a = Annotation.arrow()
        annotations.append(a)
        selectedID = a.id
    }
    func deleteSelected() {
        guard let id = selectedID else { return }
        annotations.removeAll { $0.id == id }
        selectedID = nil
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
        }
    }

    /// 保存用にフル解像度で補正＋注釈を焼き込んだ最終画像を生成。
    func renderFinalImage() async -> UIImage {
        let adjusted = await ImageProcessor.shared.render(adjustments, on: originalImage)
        return ImageExporter.compose(base: adjusted, annotations: annotations)
    }
}
