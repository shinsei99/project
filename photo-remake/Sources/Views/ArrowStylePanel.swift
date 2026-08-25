import SwiftUI

/// 選択中の矢印のパネル。タブは 種類 / 色 / 線 ＋ 削除（図形パネルと同じ並び）。
/// 「種類」から図形へ入れ替えられる（矢印も図形パレットの一員）。
struct ArrowStylePanel: View {
    @Binding var annotation: Annotation
    var onChangeTool: (AnnotationTool) -> Void
    var onDelete: () -> Void

    enum Tab { case kind, color, line }
    @State private var tab: Tab = .kind

    var body: some View {
        VStack(spacing: 8) {
            ScrollView {
                content
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal)
                    .padding(.top, 4)
            }
            .frame(maxHeight: .infinity)

            Divider().overlay(Color.white.opacity(0.1))

            HStack(spacing: 0) {
                ToolTabButton(title: "種類", systemImage: "square.on.circle", isActive: tab == .kind) { tab = .kind }
                ToolTabButton(title: "色", systemImage: "paintpalette", isActive: tab == .color) { tab = .color }
                ToolTabButton(title: "線", systemImage: "scribble", isActive: tab == .line) { tab = .line }
                Button(action: onDelete) {
                    VStack(spacing: 3) {
                        Image(systemName: "trash").font(.system(size: 18))
                        Text("削除").font(.caption2)
                    }
                    .foregroundStyle(.red)
                    .frame(maxWidth: .infinity)
                }
            }
        }
        .padding(.vertical, 8)
        .frame(maxHeight: .infinity)
    }

    @ViewBuilder private var content: some View {
        switch tab {
        case .kind:
            VStack(alignment: .leading, spacing: 8) {
                Text("種類（タップで差し替え。図形にもできます）")
                    .font(.caption).foregroundStyle(.secondary)
                ToolRow(current: .arrow, onPick: onChangeTool)
                Text("○の両端をドラッグ＝向き・長さ／本体ドラッグ＝移動")
                    .font(.caption2).foregroundStyle(.secondary)
            }
        case .color:
            VStack(alignment: .leading, spacing: 6) {
                Text("矢印の色").font(.caption).foregroundStyle(.secondary)
                ColorPaletteRow(hex: $annotation.colorHex)
            }
        case .line:
            LabeledSlider(label: "太さ", value: fraction(\.arrowThicknessRatio, mul: 100), range: 6...30)
        }
    }

    private func fraction(_ keyPath: WritableKeyPath<Annotation, CGFloat>, mul: Double) -> Binding<Double> {
        Binding(
            get: { Double(annotation[keyPath: keyPath]) * mul },
            set: { annotation[keyPath: keyPath] = CGFloat($0 / mul) }
        )
    }
}
