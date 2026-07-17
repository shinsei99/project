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

    /// サブパレット共通の高さ（全種類で統一＝切替時に写真が動かない）。
    private let subPaletteHeight: CGFloat = 205

    // テキスト入力画面（文字追加・編集）
    @State private var showTextInput = false
    @State private var draftText = ""
    @State private var draftAlign: Annotation.Align = .left
    @State private var editTargetID: UUID?

    init(image: UIImage, seedDemo: Bool = false, onNewPhoto: @escaping () -> Void) {
        _state = StateObject(wrappedValue: EditorState(image: image, seedDemo: seedDemo))
        self.onNewPhoto = onNewPhoto
    }

    var body: some View {
        VStack(spacing: 0) {
            topBar
            Divider().overlay(Color.white.opacity(0.1))
            // 写真フィールド：残り全部（下のフィールドが固定なので高さが変わらない＝写真が動かない）
            AnnotatedImageView(state: state)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color.black)
            // テキスト入力中はパレットを隠し、キーボードの上に写真を広く見せる。
            if state.editingTextID == nil {
                // サブパレットフィールド：常に固定高で確保。選択時のみ中身を表示（未選択でも領域は保持）。
                subPaletteField
                    .frame(height: subPaletteHeight, alignment: .top)
                    .frame(maxWidth: .infinity)
                    .background(.ultraThinMaterial)
                    .contentShape(Rectangle())   // 領域のタップを吸収（下の写真の選択解除を防ぐ）
                // メインパレット：常に一番下で固定
                globalBar
            }
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
        .fullScreenCover(isPresented: $showTextInput) {
            TextInputView(text: $draftText, align: $draftAlign,
                          onCancel: { closeTextInput() },
                          onDone: { commitText() })
        }
        // 既存テキストをタップ（選択済みを再タップ）したら入力画面を開く
        .onChange(of: state.editingTextID) { id in
            guard let id, let a = state.annotations.first(where: { $0.id == id }) else { return }
            editTargetID = id
            draftText = a.text
            draftAlign = a.align
            showTextInput = true
        }
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
                Button { startNewText() } label: { Label("文字を追加", systemImage: "textformat") }
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

    /// 固定高のサブパレットフィールド。選択中は該当パネル、未選択時は使い方ヒント。
    @ViewBuilder private var subPaletteField: some View {
        if let sel = state.selected {
            selectedPanel(for: sel)
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        } else {
            Text("要素をタップで選択・操作。文字・矢印・モザイクは下のパレットから追加。↩︎で元に戻す。")
                .font(.caption).foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 28)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }

    @ViewBuilder private func selectedPanel(for sel: Annotation) -> some View {
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
    }

    private var globalBar: some View {
        HStack(spacing: 0) {
            ToolTabButton(title: "文字", systemImage: "textformat", isActive: false) { startNewText() }
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

    /// 新規テキスト：まず入力画面を開き、完了で配置する（この時点では追加しない）。
    private func startNewText() {
        editTargetID = nil
        draftText = ""
        draftAlign = .left
        showTextInput = true
    }

    private func commitText() {
        let trimmed = draftText.trimmingCharacters(in: .whitespacesAndNewlines)
        if let id = editTargetID {
            if trimmed.isEmpty { state.delete(id) }
            else { state.updateText(id, text: draftText, align: draftAlign) }
        } else if !trimmed.isEmpty {
            state.insertText(draftText, align: draftAlign)
        }
        closeTextInput()
    }

    private func closeTextInput() {
        showTextInput = false
        editTargetID = nil
        state.editingTextID = nil
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

/// 文字の追加・編集を行う専用入力画面。上部にキャンセル／行揃え／完了、下に大きな入力欄。
struct TextInputView: View {
    @Binding var text: String
    @Binding var align: Annotation.Align
    var onCancel: () -> Void
    var onDone: () -> Void

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Button("キャンセル", action: onCancel)
                Spacer()
                Picker("行揃え", selection: $align) {
                    Image(systemName: "text.alignleft").tag(Annotation.Align.left)
                    Image(systemName: "text.aligncenter").tag(Annotation.Align.center)
                    Image(systemName: "text.alignright").tag(Annotation.Align.right)
                }
                .pickerStyle(.segmented)
                .frame(width: 170)
                Spacer()
                Button("完了", action: onDone).fontWeight(.semibold)
            }
            .padding(.horizontal)
            .padding(.vertical, 12)

            Divider()

            // UITextView 版：makeUIView で becomeFirstResponder するのでキーボードが確実に出る
            FocusedTextView(text: $text, alignment: nsAlign)
                .padding(.horizontal, 12)
                .padding(.top, 10)
        }
        .background(Color(.systemBackground).ignoresSafeArea())
    }

    private var nsAlign: NSTextAlignment {
        switch align {
        case .left: return .left
        case .center: return .center
        case .right: return .right
        }
    }
}

/// 起動時に自動でキーボードを出す UITextView ラッパー。
struct FocusedTextView: UIViewRepresentable {
    @Binding var text: String
    var alignment: NSTextAlignment

    func makeUIView(context: Context) -> UITextView {
        let tv = UITextView()
        tv.font = .systemFont(ofSize: 26)
        tv.backgroundColor = .clear
        tv.textAlignment = alignment
        tv.text = text
        tv.delegate = context.coordinator
        tv.keyboardDismissMode = .none
        DispatchQueue.main.async { tv.becomeFirstResponder() }
        return tv
    }

    func updateUIView(_ tv: UITextView, context: Context) {
        if tv.text != text { tv.text = text }
        if tv.textAlignment != alignment { tv.textAlignment = alignment }
    }

    func makeCoordinator() -> Coordinator { Coordinator(text: $text) }

    final class Coordinator: NSObject, UITextViewDelegate {
        let text: Binding<String>
        init(text: Binding<String>) { self.text = text }
        func textViewDidChange(_ tv: UITextView) { text.wrappedValue = tv.text }
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
