import SwiftUI

/// 編集画面本体。上部バー・キャンバス・下部ツールを束ねる。
struct EditorView: View {
    @StateObject private var state: EditorState
    let onNewPhoto: () -> Void

    @State private var showAdjust = false
    @State private var adjustSnapshot = Adjustments()
    @State private var showCrop = false
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
                .padding(.bottom, 10)   // 縦写真で操作パネルと密着しないよう少し離す
            bottomArea
                .frame(height: 214, alignment: .top)   // 固定高：選択で写真が上下に動かない
                .frame(maxWidth: .infinity)
        }
        .background(Color(hex: "#0E0E14").ignoresSafeArea())
        .overlay { if saving { savingOverlay } }
        .fullScreenCover(isPresented: $showAdjust) {
            AdjustPanel(state: state, snapshot: adjustSnapshot)
        }
        .fullScreenCover(isPresented: $showCrop) {
            CropView(state: state)
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
                Button { state.addMosaic() } label: { Label("モザイクを追加", systemImage: "square.grid.3x3.fill") }
            } label: {
                Label("追加", systemImage: "plus.circle")
            }
            Spacer()
            Button { state.undo() } label: { Image(systemName: "arrow.uturn.backward") }
                .disabled(!state.canUndo)
            Button { showHelp = true } label: { Image(systemName: "questionmark.circle") }
            Spacer()
            Button { save() } label: { Text("保存").fontWeight(.semibold) }
        }
        .font(.callout)
        .padding(.horizontal)
        .padding(.vertical, 10)
    }

    @ViewBuilder private var bottomArea: some View {
        if let sel = state.selected {
            switch sel.kind {
            case .text:
                if let b = state.binding(for: sel.id) {
                    TextStylePanel(annotation: b, onDelete: { state.deleteSelected() })
                }
            case .arrow:
                if let b = state.binding(for: sel.id) {
                    ArrowStylePanel(annotation: b, onDelete: { state.deleteSelected() })
                }
            case .mosaic:
                MosaicStylePanel(state: state, onDelete: { state.deleteSelected() })
            }
        } else {
            globalBar
        }
    }

    private var globalBar: some View {
        VStack(spacing: 4) {
            HStack(spacing: 0) {
                ToolTabButton(title: "文字", systemImage: "textformat", isActive: false) { state.addText() }
                ToolTabButton(title: "矢印", systemImage: "arrow.up.left", isActive: false) { state.addArrow() }
                ToolTabButton(title: "モザイク", systemImage: "square.grid.3x3.fill", isActive: false) { state.addMosaic() }
                ToolTabButton(title: "調整", systemImage: "slider.horizontal.3",
                              isActive: !state.adjustments.isIdentity) {
                    adjustSnapshot = state.adjustments
                    showAdjust = true
                }
                ToolTabButton(title: "切り抜き", systemImage: "crop", isActive: false) {
                    showCrop = true
                }
            }
            Text("文字・矢印・モザイクを追加。要素をタップで選択・操作。↩︎で元に戻す。")
                .font(.caption2).foregroundStyle(.secondary)
        }
        .padding(.vertical, 14)
        .frame(maxWidth: .infinity)
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
