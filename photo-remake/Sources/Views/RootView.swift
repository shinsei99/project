import SwiftUI
import PhotosUI

/// 起点。写真を選ぶ／撮影する → 編集画面へ。
struct RootView: View {
    @State private var image: UIImage?
    @State private var demo = false

    init() {
        #if DEBUG
        if DebugSample.isEnabled {
            _image = State(initialValue: DebugSample.image())
            _demo = State(initialValue: true)
        }
        #endif
    }

    var body: some View {
        Group {
            if let image {
                EditorView(image: image, seedDemo: demo) { self.image = nil; demo = false }
            } else {
                StartView { self.image = $0 }
            }
        }
        .animation(.default, value: image != nil)
    }
}

private struct StartView: View {
    var onPicked: (UIImage) -> Void

    @State private var photoItem: PhotosPickerItem?
    @State private var showCamera = false
    @State private var loading = false

    var body: some View {
        ZStack {
            LinearGradient(colors: [Color(hex: "#1C1C2E"), Color(hex: "#0E0E14")],
                           startPoint: .top, endPoint: .bottom)
                .ignoresSafeArea()

            VStack(spacing: 28) {
                Spacer()
                Image(systemName: "photo.on.rectangle.angled")
                    .font(.system(size: 66, weight: .light))
                    .foregroundStyle(.tint)
                Text("フォトリメイク")
                    .font(.title.bold())
                Text("写真に文字・矢印を入れて、明るさやシャープも整えます")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 40)

                Spacer()

                VStack(spacing: 14) {
                    PhotosPicker(selection: $photoItem, matching: .images) {
                        Label("写真を選ぶ", systemImage: "photo")
                            .font(.headline)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 16)
                            .background(.tint, in: RoundedRectangle(cornerRadius: 16))
                            .foregroundStyle(.white)
                    }

                    if UIImagePickerController.isSourceTypeAvailable(.camera) {
                        Button {
                            showCamera = true
                        } label: {
                            Label("撮影する", systemImage: "camera")
                                .font(.headline)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 16)
                                .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
                        }
                    }
                }
                .padding(.horizontal, 28)
                .padding(.bottom, 40)
            }

            if loading { ProgressView().controlSize(.large) }
        }
        .fullScreenCover(isPresented: $showCamera) {
            CameraPicker { onPicked($0) }
                .ignoresSafeArea()
        }
        .onChange(of: photoItem) { newItem in
            guard let newItem else { return }
            loading = true
            Task {
                if let data = try? await newItem.loadTransferable(type: Data.self),
                   let img = UIImage(data: data) {
                    onPicked(img)
                }
                loading = false
            }
        }
    }
}
