import SwiftUI

/// 全画面の補正調整パネル（参考UIの「調整」画面に相当）。
/// キャンセルで開いた時点のパラメータへ戻す。
struct AdjustPanel: View {
    @ObservedObject var state: EditorState
    let snapshot: Adjustments
    @Environment(\.dismiss) private var dismiss
    @State private var field: Adjustments.Field = .brightness

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            VStack(spacing: 0) {
                Image(uiImage: state.previewImage)
                    .resizable()
                    .scaledToFit()
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .padding()

                VStack(spacing: 8) {
                    HStack {
                        Text(field.label)
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(Color.accentColor)
                        Spacer()
                        Text("\(Int(state.adjustments[field]))")
                            .font(.subheadline.monospacedDigit())
                            .foregroundStyle(.secondary)
                    }
                    Slider(
                        value: Binding(get: { state.adjustments[field] },
                                       set: { state.adjustments[field] = $0 }),
                        in: field.range, step: 1)
                }
                .padding(.horizontal)

                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 26) {
                        ForEach(Adjustments.Field.allCases) { f in
                            Button { field = f } label: {
                                VStack(spacing: 5) {
                                    Image(systemName: f.systemImage).font(.system(size: 20))
                                    Text(f.label).font(.caption2)
                                }
                                .foregroundStyle(field == f ? Color.accentColor : Color.secondary)
                                .overlay(alignment: .topTrailing) {
                                    if state.adjustments[f] != 0 {
                                        Circle().fill(Color.accentColor).frame(width: 5, height: 5)
                                            .offset(x: 6, y: -2)
                                    }
                                }
                            }
                        }
                    }
                    .padding(.horizontal, 22)
                    .padding(.vertical, 14)
                }

                Divider().overlay(Color.white.opacity(0.1))

                HStack {
                    Button { state.adjustments = snapshot; dismiss() } label: {
                        Image(systemName: "xmark").font(.title3)
                    }
                    Spacer()
                    Button("リセット") { state.adjustments = .identity }
                        .font(.subheadline)
                        .disabled(state.adjustments.isIdentity)
                    Spacer()
                    Button { dismiss() } label: {
                        Image(systemName: "checkmark").font(.title3)
                    }
                }
                .tint(.white)
                .padding(.horizontal, 24)
                .padding(.vertical, 12)
            }
        }
    }
}
