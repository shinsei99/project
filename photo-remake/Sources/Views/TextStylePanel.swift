import SwiftUI

/// 選択中テキストのパネル。文字内容はキャンバス上で直接編集するため、ここには入力欄を置かない。
/// タブは 書体（大きさ・太さ・縦書き含む）/ 色 / 縁取り / 影 ＋ 削除。
struct TextStylePanel: View {
    @Binding var annotation: Annotation
    var onDelete: () -> Void

    enum Tab { case font, color, outline, shadow }
    @State private var tab: Tab = .font

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
                ToolTabButton(title: "書体", systemImage: "a.square", isActive: tab == .font) { tab = .font }
                ToolTabButton(title: "色", systemImage: "paintpalette", isActive: tab == .color) { tab = .color }
                ToolTabButton(title: "縁取り", systemImage: "square.on.square", isActive: tab == .outline) { tab = .outline }
                ToolTabButton(title: "影", systemImage: "shadow", isActive: tab == .shadow) { tab = .shadow }
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
        case .font:
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 8) {
                    ForEach(AnnotationFont.choices, id: \.name) { c in
                        Button(c.label) { annotation.fontName = c.name }
                            .buttonStyle(.bordered)
                            .tint(annotation.fontName == c.name ? .accentColor : .secondary)
                    }
                }
                HStack(spacing: 10) {
                    Text("太さ").font(.caption).foregroundStyle(.secondary)
                        .frame(width: 44, alignment: .leading)
                    Slider(value: Binding(
                        get: { Double(annotation.fontWeightIndex) },
                        set: { annotation.fontWeightIndex = Int($0.rounded()) }
                    ), in: 0...8, step: 1)
                    Text(AnnotationFont.weightLabels[max(0, min(annotation.fontWeightIndex, 8))])
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(.secondary).frame(width: 30, alignment: .trailing)
                }
                Toggle(isOn: $annotation.isVertical) {
                    Label("縦書き", systemImage: "arrow.up.and.down.text.horizontal")
                }
                .toggleStyle(.button)
                .tint(.accentColor)
                .font(.subheadline)
            }
        case .color:
            VStack(alignment: .leading, spacing: 8) {
                paletteHeader {
                    Text("文字の色").font(.caption).foregroundStyle(.secondary)
                }
                ColorPaletteRow(hex: $annotation.colorHex)
            }
        case .outline:
            VStack(alignment: .leading, spacing: 8) {
                paletteHeader {
                    Toggle("縁取りをつける", isOn: $annotation.hasOutline)
                        .font(.caption).fixedSize()
                    if annotation.hasOutline {
                        Text("太さ").font(.caption2).foregroundStyle(.secondary)
                        Slider(value: fraction(\.outlineWidthRatio, mul: 100), in: 0...25)
                    }
                }
                if annotation.hasOutline {
                    ColorPaletteRow(hex: $annotation.outlineColorHex)
                }
            }
        case .shadow:
            VStack(alignment: .leading, spacing: 8) {
                paletteHeader {
                    Toggle("影をつける", isOn: $annotation.hasShadow)
                        .font(.caption).fixedSize()
                }
                if annotation.hasShadow {
                    ColorPaletteRow(hex: $annotation.shadowColorHex)
                }
            }
        }
    }

    /// 色/縁取り/影 タブ共通の見出し行（同じ高さ）。下のカラーパレットの位置が揃う。
    private func paletteHeader<Content: View>(@ViewBuilder _ content: () -> Content) -> some View {
        HStack(spacing: 10) { content() }
            .frame(height: 30)
            .frame(maxWidth: .infinity, alignment: .leading)
    }

    /// CGFloat の割合プロパティを Double スライダー値へ橋渡しする Binding を作る。
    private func fraction(_ keyPath: WritableKeyPath<Annotation, CGFloat>, mul: Double) -> Binding<Double> {
        Binding(
            get: { Double(annotation[keyPath: keyPath]) * mul },
            set: { annotation[keyPath: keyPath] = CGFloat($0 / mul) }
        )
    }
}
