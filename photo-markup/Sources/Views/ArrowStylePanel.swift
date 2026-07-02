import SwiftUI

/// 選択中の矢印の装飾パネル（色/長さ/太さ ＋ 削除）。
struct ArrowStylePanel: View {
    @Binding var annotation: Annotation
    var onDelete: () -> Void

    var body: some View {
        VStack(spacing: 10) {
            VStack(alignment: .leading, spacing: 6) {
                Text("矢印の色").font(.caption).foregroundStyle(.secondary)
                ColorPaletteRow(hex: $annotation.colorHex)
            }
            LabeledSlider(label: "長さ", value: fraction(\.arrowLengthFraction, mul: 100), range: 5...120)
            LabeledSlider(label: "太さ", value: fraction(\.arrowThicknessRatio, mul: 100), range: 6...30)

            Divider().overlay(Color.white.opacity(0.1))
            HStack {
                Text("2本指でピンチ＝拡大 / 回転").font(.caption2).foregroundStyle(.secondary)
                Spacer()
                Button(role: .destructive, action: onDelete) {
                    Label("削除", systemImage: "trash")
                }
                .font(.subheadline)
            }
        }
        .padding()
        .background(.ultraThinMaterial)
    }

    private func fraction(_ keyPath: WritableKeyPath<Annotation, CGFloat>, mul: Double) -> Binding<Double> {
        Binding(
            get: { Double(annotation[keyPath: keyPath]) * mul },
            set: { annotation[keyPath: keyPath] = CGFloat($0 / mul) }
        )
    }
}
