import SwiftUI

/// 色プリセットの横スクロール＋カスタムカラーピッカー。
struct ColorPaletteRow: View {
    @Binding var hex: String

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 12) {
                ForEach(PalettePresets.colors, id: \.self) { c in
                    Circle()
                        .fill(Color(hex: c))
                        .frame(width: 30, height: 30)
                        .overlay(
                            Circle().strokeBorder(
                                hex.uppercased() == c ? Color.accentColor : Color.white.opacity(0.35),
                                lineWidth: hex.uppercased() == c ? 3 : 1)
                        )
                        .onTapGesture { hex = c }
                }
                ColorPicker("", selection: Binding(
                    get: { Color(hex: hex) },
                    set: { hex = UIColor($0).hexString }), supportsOpacity: false)
                    .labelsHidden()
                    .frame(width: 32, height: 32)
            }
            .padding(.horizontal, 4)
            .padding(.vertical, 2)
        }
    }
}

/// ラベル付きスライダー。
struct LabeledSlider: View {
    let label: String
    @Binding var value: Double
    var range: ClosedRange<Double>
    var step: Double = 1

    var body: some View {
        HStack(spacing: 10) {
            Text(label).font(.caption).foregroundStyle(.secondary)
                .frame(width: 56, alignment: .leading)
            Slider(value: $value, in: range, step: step)
            Text("\(Int(value))").font(.caption.monospacedDigit())
                .foregroundStyle(.secondary).frame(width: 34, alignment: .trailing)
        }
    }
}

/// 下部ツールのタブボタン。
struct ToolTabButton: View {
    let title: String
    let systemImage: String
    let isActive: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 3) {
                Image(systemName: systemImage).font(.system(size: 18))
                Text(title).font(.caption2)
            }
            .foregroundStyle(isActive ? Color.accentColor : Color.primary)
            .frame(maxWidth: .infinity)
        }
    }
}
