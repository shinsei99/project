import Photos
import UIKit

/// 加工画像をカメラロールへ保存する。
enum PhotoSaver {
    enum SaveError: LocalizedError {
        case denied, failed
        var errorDescription: String? {
            switch self {
            case .denied: return "写真の保存が許可されていません。設定アプリで許可してください。"
            case .failed: return "保存に失敗しました。"
            }
        }
    }

    static func save(_ image: UIImage) async throws {
        let status = await requestAddAuthorization()
        guard status == .authorized || status == .limited else { throw SaveError.denied }
        try await withCheckedThrowingContinuation { (cont: CheckedContinuation<Void, Error>) in
            PHPhotoLibrary.shared().performChanges {
                PHAssetChangeRequest.creationRequestForAsset(from: image)
            } completionHandler: { ok, err in
                if ok { cont.resume() }
                else { cont.resume(throwing: err ?? SaveError.failed) }
            }
        }
    }

    private static func requestAddAuthorization() async -> PHAuthorizationStatus {
        await withCheckedContinuation { cont in
            PHPhotoLibrary.requestAuthorization(for: .addOnly) { cont.resume(returning: $0) }
        }
    }
}
