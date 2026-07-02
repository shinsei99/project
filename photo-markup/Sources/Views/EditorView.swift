import SwiftUI

/// 編集画面本体。上部バー・キャンバス・下部ツールを束ねる。
struct EditorView: View {
    @StateObject private var state: EditorState
    let onNewPhoto: () -> Void

    @State private var showAdjust = false
    @State private var adjustSnapshot = Adjustments()
    @State private var showHelp = false
    @State private var saving = false
    @State private var saveMessage: String?

    init(image: UIImage, seedDemo: Bool = false, onNewPhoto: @escaping () -> Void) {
        _state = StateObject(wrappedValue: EditorState(image: image, seedDemo: seedDemo))
        self.onNewPhoto = onNewPhoto
    }

    var body: some View {
        VStack(spacing: 0) {
            topBar
            Divider().overlay(Color.white.opacity(0.1))
            AnnotatedImageView(state: state)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color.black)
            bottomArea
        }
        .background(Color(hex: "#0E0E14").ignoresSafeArea())
        .overlay { if saving { savingOverlay } }
        .fullScreenCover(isPresented: $showAdjust) {
            AdjustPanel(state: state, snapshot: adjustSnapshot)
        }
        .sheet(isPresented: $showHelp) { HelpView() }
        .alert("保存", isPresented: Binding(
            get: { saveMessage != nil },
            set: { if !$0 { saveMessage = nil } })) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(saveMessage ?? "")
        }
    }

    private var topBar: some View {
        HStack {
            Button { onNewPhoto() } label: {
                Label("写真", systemImage: "photo").labelStyle(.titleAndIcon)
            }
            Spacer()
            Menu {
                Button { state.addText() } label: { Label("文字を追加", systemImage: "textformat") }
                Button { state.addArrow() } label: { Label("矢印を追加", systemImage: "arrow.up.left") }
            } label: {
                Label("追加", systemImage: "plus.circle")
            }
            Spacer()
            Button { showHelp = true } label: { Image(systemName: "questionmark.circle") }
            Spacer()
            Button { save() } label: { Text("保存").fontWeight(.semibold) }
        }
        .font(.callout)
        .padding(.horizontal)
        .padding(.vertical, 10)
    }

    @ViewBuilder private var bottomArea: some View {
        if let sel = state.selected, let b = state.binding(for: sel.id) {
            switch sel.kind {
            case .text: TextStylePanel(annotation: b, onDelete: { state.deleteSelected() })
            case .arrow: ArrowStylePanel(annotation: b, onDelete: { state.deleteSelected() })
            }
        } else {
            globalBar
        }
    }

    private var globalBar: some View {
        HStack(spacing: 0) {
            ToolTabButton(title: "文字", systemImage: "textformat", isActive: false) { state.addText() }
            ToolTabButton(title: "矢印", systemImage: "arrow.up.left", isActive: false) { state.addArrow() }
            ToolTabButton(title: "調整", systemImage: "slider.horizontal.3",
                          isActive: !state.adjustments.isIdentity) {
                adjustSnapshot = state.adjustments
                showAdjust = true
            }
        }
        .padding(.vertical, 14)
        .background(.ultraThinMaterial)
    }

    private var savingOverlay: some View {
        ZStack {
            Color.black.opacity(0.5).ignoresSafeArea()
            VStack(spacing: 12) {
                ProgressView().controlSize(.large).tint(.white)
                Text("保存中…").foregroundStyle(.white)
            }
        }
    }

    private func save() {
        state.selectedID = nil
        saving = true
        Task {
            let image = await state.renderFinalImage()
            do {
                try await PhotoSaver.save(image)
                saveMessage = "カメラロールに保存しました。"
            } catch {
                saveMessage = error.localizedDescription
            }
            saving = false
        }
    }
}

/// 使い方ヘルプ。
struct HelpView: View {
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            List {
                Section("基本") {
                    Label("上部「追加」から文字・矢印を置けます", systemImage: "plus.circle")
                    Label("指1本でドラッグ＝移動", systemImage: "hand.draw")
                    Label("2本指でピンチ＝拡大・回転", systemImage: "arrow.up.left.and.arrow.down.right")
                    Label("要素をタップ＝選択、下のパネルで装飾", systemImage: "hand.tap")
                }
                Section("補正") {
                    Label("「調整」で明るさ・コントラスト・鮮やかさ・シャープ・ノイズ除去", systemImage: "slider.horizontal.3")
                }
                Section("保存") {
                    Label("右上「保存」でフル画質のままカメラロールへ", systemImage: "square.and.arrow.down")
                }
            }
            .navigationTitle("使い方")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("閉じる") { dismiss() } } }
        }
    }
}
