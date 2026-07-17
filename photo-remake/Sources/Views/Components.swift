import SwiftUI

/// 色プリセットの2段（横スクロール）。1段目＝濃い色、2段目＝淡い色。
/// 2段目の一番左にカスタムカラー（フリー）ピッカーを置く。
struct ColorPaletteRow: View {
    @Binding var hex: String

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 8) {
                    ForEach(PalettePresets.row1, id: \.self) { swatch($0) }
                }
                HStack(spacing: 8) {
                    freePicker
                    ForEach(PalettePresets.row2, id: \.self) { swatch($0) }
                }
            }
            .padding(.horizontal, 4)
            .padding(.vertical, 2)
        }
    }

    private func swatch(_ c: String) -> some View {
        Circle()
            .fill(Color(hex: c))
            .frame(width: 24, height: 24)
            .overlay(
                Circle().strokeBorder(
                    hex.uppercased() == c ? Color.accentColor : Color.white.opacity(0.35),
                    lineWidth: hex.uppercased() == c ? 3 : 1)
            )
            .onTapGesture { hex = c }
    }

    /// カスタムカラー（フリー）ピッカー。
    private var freePicker: some View {
        ColorPicker("", selection: Binding(
            get: { Color(hex: hex) },
            set: { hex = UIColor($0).hexString }), supportsOpacity: false)
            .labelsHidden()
            .frame(width: 24, height: 24)
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
