import SwiftUI

/// 選択中テキストの装飾パネル（文字/書体/色/縁取り/影 ＋ 削除）。
struct TextStylePanel: View {
    @Binding var annotation: Annotation
    var onDelete: () -> Void

    enum Tab { case text, font, color, outline, shadow }
    @State private var tab: Tab = .text

    var body: some View {
        VStack(spacing: 10) {
            content
                .frame(minHeight: 92, alignment: .top)
                .padding(.horizontal)

            Divider().overlay(Color.white.opacity(0.1))

            HStack(spacing: 0) {
                ToolTabButton(title: "文字", systemImage: "textformat", isActive: tab == .text) { tab = .text }
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
        .padding(.vertical, 10)
        .background(.ultraThinMaterial)
    }

    @ViewBuilder private var content: some View {
        switch tab {
        case .text:
            VStack(spacing: 10) {
                ZStack(alignment: .topLeading) {
                    if annotation.text.isEmpty {
                        Text("テキストを入力")
                            .foregroundStyle(.secondary)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 10)
                    }
                    // TextEditor: Return は改行を挿入し、キーボードを閉じない（TextField と異なる）
                    TextEditor(text: $annotation.text)
                        .frame(minHeight: 44, maxHeight: 88)
                        .scrollContentBackground(.hidden)
                        .opacity(annotation.text.isEmpty ? 0.25 : 1)
                        .toolbar {
                            ToolbarItemGroup(placement: .keyboard) {
                                Spacer()
                                Button("完了") {
                                    UIApplication.shared.sendAction(
                                        #selector(UIResponder.resignFirstResponder),
                                        to: nil, from: nil, for: nil)
                                }
                            }
                        }
                }
                .background(Color(.systemGray6))
                .clipShape(RoundedRectangle(cornerRadius: 8))
                .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color(.systemGray4), lineWidth: 0.5))
                LabeledSlider(label: "大きさ",
                              value: fraction(\.fontHeightFraction, mul: 1000), range: 20...220)
                HStack(spacing: 10) {
                    Text("太さ").font(.caption).foregroundStyle(.secondary)
                        .frame(width: 56, alignment: .leading)
                    Slider(value: Binding(
                        get: { Double(annotation.fontWeightIndex) },
                        set: { annotation.fontWeightIndex = Int($0.rounded()) }
                    ), in: 0...8, step: 1)
                    Text(AnnotationFont.weightLabels[max(0, min(annotation.fontWeightIndex, 8))])
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(.secondary).frame(width: 34, alignment: .trailing)
                }
            }
        case .font:
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    ForEach(AnnotationFont.choices, id: \.name) { c in
                        Button(c.label) { annotation.fontName = c.name }
                            .buttonStyle(.bordered)
                            .tint(annotation.fontName == c.name ? .accentColor : .secondary)
                    }
                }
                HStack(spacing: 16) {
                    Toggle("縦書き", isOn: $annotation.isVertical)
                }
                .font(.subheadline)
                .toggleStyle(.button)
            }
        case .color:
            VStack(alignment: .leading, spacing: 6) {
                Text("文字の色").font(.caption).foregroundStyle(.secondary)
                ColorPaletteRow(hex: $annotation.colorHex)
            }
        case .outline:
            VStack(spacing: 8) {
                Toggle("縁取りをつける", isOn: $annotation.hasOutline).font(.subheadline)
                if annotation.hasOutline {
                    ColorPaletteRow(hex: $annotation.outlineColorHex)
                    LabeledSlider(label: "太さ",
                                  value: fraction(\.outlineWidthRatio, mul: 100), range: 0...25)
                    LabeledSlider(label: "透過度",
                                  value: fraction(\.outlineOpacity, mul: 100), range: 0...100)
                }
            }
        case .shadow:
            Toggle("影をつける", isOn: $annotation.hasShadow)
                .font(.subheadline)
                .padding(.top, 4)
        }
    }

    /// CGFloat の割合プロパティを Double スライダー値へ橋渡しする Binding を作る。
    private func fraction(_ keyPath: WritableKeyPath<Annotation, CGFloat>, mul: Double) -> Binding<Double> {
        Binding(
            get: { Double(annotation[keyPath: keyPath]) * mul },
            set: { annotation[keyPath: keyPath] = CGFloat($0 / mul) }
        )
    }
}
