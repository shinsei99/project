import SwiftUI

/// 選択中の図形のパネル。タブは 種類 / 色 / 線 ＋ 削除。
struct ShapeStylePanel: View {
    @Binding var annotation: Annotation
    var onDelete: () -> Void

    enum Tab { case kind, color, line }
    @State private var tab: Tab = .kind
    /// 色タブでいま塗り・枠線のどちらを触っているか。
    enum ColorTarget { case fill, stroke }
    @State private var colorTarget: ColorTarget = .stroke

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
                Text("図形の種類（タップで差し替え）")
                    .font(.caption).foregroundStyle(.secondary)
                ShapeKindRow(selection: $annotation.shapeKind)
                Text("本体ドラッグ＝移動／右下＝大きさ／右上＝回転")
                    .font(.caption2).foregroundStyle(.secondary)
            }
        case .color:
            VStack(alignment: .leading, spacing: 8) {
                // どちらの色を触るかを選ぶ。塗り／枠線それぞれに「なし」がある。
                Picker("色を変える対象", selection: $colorTarget) {
                    Text(annotation.shapeDrawStyle == .fill ? "枠線（なし）" : "枠線")
                        .tag(ColorTarget.stroke)
                    Text(annotation.shapeDrawStyle == .stroke ? "塗り（なし）" : "塗り")
                        .tag(ColorTarget.fill)
                }
                .pickerStyle(.segmented)

                HStack(spacing: 8) {
                    noneChip(isOn: isNone) { setNone() }
                    ColorPaletteRow(hex: colorTarget == .fill ? fillBinding : strokeBinding)
                }
                Text(isNone
                     ? "「なし」を選択中。色をタップすると付きます。"
                     : "「なし」をタップすると\(colorTarget == .fill ? "塗り" : "枠線")を消せます。")
                    .font(.caption2).foregroundStyle(.secondary)
            }
        case .line:
            VStack(alignment: .leading, spacing: 10) {
                if annotation.shapeDrawStyle != .fill {
                    LabeledSlider(label: "線の太さ",
                                  value: fraction(\.shapeLineWidthRatio, mul: 1000), range: 2...60)
                }
                if annotation.shapeDrawStyle != .stroke {
                    LabeledSlider(label: "透け具合",
                                  value: fraction(\.shapeOpacity, mul: 100), range: 10...100)
                }
                Button {
                    annotation.rotation = .zero
                } label: {
                    Label("向きを戻す", systemImage: "arrow.counterclockwise")
                        .font(.subheadline)
                }
                .disabled(annotation.rotation == .zero)
            }
        }
    }

    /// いま選んでいる対象（塗り／枠線）が「なし」か。
    private var isNone: Bool {
        colorTarget == .fill ? annotation.shapeDrawStyle == .stroke
                             : annotation.shapeDrawStyle == .fill
    }

    /// 「なし」にする。塗りを消せば枠線だけ、枠線を消せば塗りだけになる（両方なしにはしない）。
    private func setNone() {
        annotation.shapeDrawStyle = (colorTarget == .fill) ? .stroke : .fill
    }

    /// 塗りの色。色を選んだ時点で「塗りなし」なら塗りを復活させる。
    private var fillBinding: Binding<String> {
        Binding(
            get: { annotation.shapeDrawStyle == .stroke ? "" : annotation.colorHex },
            set: {
                annotation.colorHex = $0
                if annotation.shapeDrawStyle == .stroke { annotation.shapeDrawStyle = .both }
            })
    }

    /// 枠線の色。色を選んだ時点で「枠線なし」なら枠線を復活させる。
    private var strokeBinding: Binding<String> {
        Binding(
            get: { annotation.shapeDrawStyle == .fill ? "" : annotation.strokeColorHex },
            set: {
                annotation.strokeColorHex = $0
                if annotation.shapeDrawStyle == .fill { annotation.shapeDrawStyle = .both }
            })
    }

    /// 「なし」（＝この色を使わない）チップ。塗りを消す／枠線を消すのに使う。
    private func noneChip(isOn: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 3) {
                ZStack {
                    Circle().fill(Color.black.opacity(0.25))
                    Circle().strokeBorder(isOn ? Color.accentColor : Color.white.opacity(0.35),
                                          lineWidth: isOn ? 3 : 1)
                    Rectangle().fill(Color.red)
                        .frame(width: 26, height: 2)
                        .rotationEffect(.degrees(-45))
                }
                .frame(width: 24, height: 24)
                Text("なし").font(.system(size: 9))
                    .foregroundStyle(isOn ? Color.accentColor : .secondary)
            }
        }
        .buttonStyle(.plain)
    }

    private func fraction(_ keyPath: WritableKeyPath<Annotation, CGFloat>, mul: Double) -> Binding<Double> {
        Binding(
            get: { Double(annotation[keyPath: keyPath]) * mul },
            set: { annotation[keyPath: keyPath] = CGFloat($0 / mul) }
        )
    }
}

/// 図形の種類を横スクロールで並べる（実際のパスをそのまま縮小表示）。
struct ShapeKindRow: View {
    @Binding var selection: ShapeKind

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 10) {
                ForEach(ShapeKind.allCases) { kind in
                    Button {
                        selection = kind
                    } label: {
                        ShapeChip(kind: kind, isSelected: kind == selection)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, 4)
            .padding(.vertical, 2)
        }
    }
}

/// 図形1つぶんの見本。
struct ShapeChip: View {
    let kind: ShapeKind
    var isSelected: Bool = false
    var side: CGFloat = 44

    var body: some View {
        VStack(spacing: 4) {
            AnnotationShape(kind: kind)
                .stroke(isSelected ? Color.accentColor : Color.primary,
                        style: StrokeStyle(lineWidth: 2, lineJoin: .round))
                .padding(6)
                .frame(width: side, height: side)
                .background(
                    RoundedRectangle(cornerRadius: 10)
                        .fill(Color.primary.opacity(isSelected ? 0.16 : 0.06))
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 10)
                        .strokeBorder(Color.accentColor, lineWidth: isSelected ? 2 : 0)
                )
            Text(kind.label).font(.caption2).foregroundStyle(.secondary)
        }
    }
}

/// 追加する図形を選ぶシート。
struct ShapePickerView: View {
    var onPick: (ShapeKind) -> Void
    @Environment(\.dismiss) private var dismiss

    private let columns = [GridItem(.adaptive(minimum: 84), spacing: 12)]

    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVGrid(columns: columns, spacing: 14) {
                    ForEach(ShapeKind.allCases) { kind in
                        Button {
                            onPick(kind)
                            dismiss()
                        } label: {
                            ShapeChip(kind: kind, side: 64)
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding()
            }
            .navigationTitle("図形を選ぶ")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("閉じる") { dismiss() } }
            }
        }
    }
}
