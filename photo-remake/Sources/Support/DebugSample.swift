#if DEBUG
import UIKit

/// DEBUG時、環境変数 PM_SAMPLE=1 で起動するとサンプル画像＋注釈でエディタを開く（動作確認用）。
enum DebugSample {
    static var isEnabled: Bool { ProcessInfo.processInfo.environment["PM_SAMPLE"] == "1" }
    /// PM_EXPORT=1 なら起動直後に書き出し結果を Documents/export.png へ保存する（プレビューとの一致確認用）。
    static var exportsOnLaunch: Bool { ProcessInfo.processInfo.environment["PM_EXPORT"] == "1" }

    static func writeExport(_ image: UIImage) {
        guard let data = image.pngData(),
              let dir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first
        else { return }
        try? data.write(to: dir.appendingPathComponent("export.png"))
        print("[PM_EXPORT] wrote export.png")
    }

    static func image() -> UIImage {
        let size = CGSize(width: 1200, height: 1600)
        let renderer = UIGraphicsImageRenderer(size: size)
        return renderer.image { ctx in
            let c = ctx.cgContext
            let cs = CGColorSpaceCreateDeviceRGB()
            let g = CGGradient(colorsSpace: cs, colors: [
                UIColor(red: 0.55, green: 0.78, blue: 0.98, alpha: 1).cgColor,
                UIColor(red: 0.86, green: 0.93, blue: 1.0, alpha: 1).cgColor] as CFArray,
                locations: [0, 1])!
            c.drawLinearGradient(g, start: .zero, end: CGPoint(x: 0, y: size.height * 0.62), options: [])
            UIColor(red: 0.36, green: 0.55, blue: 0.32, alpha: 1).setFill()
            c.fill(CGRect(x: 0, y: size.height * 0.62, width: size.width, height: size.height * 0.38))
            UIColor(red: 0.20, green: 0.42, blue: 0.24, alpha: 1).setFill()
            for i in 0..<6 {
                c.fillEllipse(in: CGRect(x: CGFloat(i) * 220 + 30, y: size.height * 0.36,
                                         width: 210, height: 380))
            }
        }
    }
}
#endif
