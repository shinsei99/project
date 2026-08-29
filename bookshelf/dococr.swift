import Foundation
import Vision
import AppKit

// macOS 26 の文書OCR。1画像1行のJSON（読み順の行＋外接矩形）を吐く。
@main
struct M {
    static func main() async {
        for path in CommandLine.arguments.dropFirst() {
            guard let img = NSImage(contentsOfFile: path),
                  let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
                FileHandle.standardError.write("load failed: \(path)\n".data(using: .utf8)!); continue
            }
            do {
                let obs = try await RecognizeDocumentsRequest().perform(on: cg)
                var lines: [[String: Any]] = []
                for o in obs {
                    for ln in o.document.text.lines {
                        let pts = ln.boundingRegion.normalizedPoints
                        guard !pts.isEmpty else { continue }
                        let xs = pts.map { Double($0.x) }, ys = pts.map { Double($0.y) }
                        lines.append(["t": String(ln.transcript),
                                      "x": xs.min()!, "y": ys.min()!,
                                      "w": xs.max()! - xs.min()!, "h": ys.max()! - ys.min()!])
                    }
                }
                let out: [String: Any] = ["file": path, "w": cg.width, "h": cg.height, "lines": lines]
                FileHandle.standardOutput.write(try! JSONSerialization.data(withJSONObject: out))
                FileHandle.standardOutput.write("\n".data(using: .utf8)!)
            } catch {
                FileHandle.standardError.write("ocr failed: \(path): \(error)\n".data(using: .utf8)!)
            }
        }
    }
}
