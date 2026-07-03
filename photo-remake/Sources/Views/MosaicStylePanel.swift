import SwiftUI

/// 選択中モザイクの設定パネル（粗さ＋削除）。粗さは全モザイク共通。
struct MosaicStylePanel: View {
    @ObservedObject var state: EditorState
    var onDelete: () -> Void

    var body: some View {
        VStack(spacing: 12) {
            Text("隠したい所を枠で囲む／本体ドラッグで移動・右下でサイズ調整")
                .font(.caption).foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
            LabeledSlider(
                label: "粗さ",
                value: Binding(get: { Double(state.mosaicBlockFraction * 1000) },
                               set: { state.mosaicBlockFraction = CGFloat($0 / 1000) }),
                range: 15...100)
            Divider().overlay(Color.white.opacity(0.1))
            HStack {
                Text("モザイク").font(.caption2).foregroundStyle(.secondary)
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
}
