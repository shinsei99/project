import Foundation
import Capacitor
import Vision
import UIKit

/// 端末の中だけで動く文書OCR。
///
/// **Apple Vision の `RecognizeDocumentsRequest`（iOS 26〜）を使う。**
/// 従来の `VNRecognizeTextRequest` は縦書きの日本語を読めない（2026-08-28 に実測。
/// 縦書きページから15文字しか取れなかった）。縦書きの自炊本を救えるのはこちらだけ。
///
/// 通信は一切しない。画像も文字も端末の外へ出さない。
@objc(DocumentOCRPlugin)
public class DocumentOCRPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "DocumentOCRPlugin"
    public let jsName = "DocumentOCR"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "isAvailable", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "recognize", returnType: CAPPluginReturnPromise)
    ]

    /// この端末で使えるか。**iOS 26 未満では false を返す**（画面にボタンを出さないため）。
    @objc func isAvailable(_ call: CAPPluginCall) {
        if #available(iOS 26.0, *) {
            call.resolve(["available": true, "reason": ""])
        } else {
            call.resolve(["available": false,
                          "reason": "縦書きを読める文書OCRは iOS 26 以降でだけ使えます"])
        }
    }

    /// base64 の画像1枚を読む。行は**読み順のまま**、位置は左下原点の正規化座標で返す。
    @objc func recognize(_ call: CAPPluginCall) {
        guard let b64 = call.getString("image") else {
            call.reject("image（base64）がありません")
            return
        }
        // data URL（"data:image/jpeg;base64,…"）で渡ってきても受け取れるようにする
        let payload = b64.contains(",") ? String(b64.split(separator: ",", maxSplits: 1).last ?? "") : b64
        guard let data = Data(base64Encoded: payload, options: .ignoreUnknownCharacters),
              let image = UIImage(data: data),
              let cg = image.cgImage else {
            call.reject("画像を読み込めませんでした")
            return
        }
        // **可用性の判定はここで閉じる。** guard #available の効果を閉包の中まで当てにすると、
        // Swift のバージョンによって通らないことがあるので、専用の関数に分ける
        if #available(iOS 26.0, *) {
            Task { await Self.run(call: call, image: cg) }
        } else {
            call.reject("この端末の iOS では使えません（iOS 26 以降が必要）")
        }
    }

    @available(iOS 26.0, *)
    private static func run(call: CAPPluginCall, image cg: CGImage) async {
        do {
            let observations = try await RecognizeDocumentsRequest().perform(on: cg)
            var lines: [[String: Any]] = []
            for observation in observations {
                for line in observation.document.text.lines {
                    let points = line.boundingRegion.normalizedPoints
                    guard !points.isEmpty else { continue }
                    let text = String(line.transcript)
                    if text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { continue }
                    let xs = points.map { Double($0.x) }
                    let ys = points.map { Double($0.y) }
                    let minX = xs.min() ?? 0, maxX = xs.max() ?? 0
                    let minY = ys.min() ?? 0, maxY = ys.max() ?? 0
                    lines.append([
                        "text": text,
                        "x": minX, "y": minY,
                        "w": maxX - minX, "h": maxY - minY
                    ])
                }
            }
            call.resolve(["lines": lines, "width": cg.width, "height": cg.height])
        } catch {
            call.reject("読み取りに失敗しました: \(error.localizedDescription)")
        }
    }
}
