import Foundation
import Vision
import AppKit

// 使い方: visocr <画像パス> ...   → 1行1JSON（text/bbox/conf）
let args = Array(CommandLine.arguments.dropFirst())
for path in args {
    guard let img = NSImage(contentsOfFile: path),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        FileHandle.standardError.write("load failed: \(path)\n".data(using: .utf8)!); continue
    }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.recognitionLanguages = ["ja-JP", "en-US"]
    req.usesLanguageCorrection = true
    req.revision = VNRecognizeTextRequestRevision3
    let handler = VNImageRequestHandler(cgImage: cg, options: [:])
    do { try handler.perform([req]) } catch {
        FileHandle.standardError.write("ocr failed: \(path): \(error)\n".data(using: .utf8)!); continue
    }
    var lines: [[String: Any]] = []
    for obs in (req.results ?? []) {
        guard let c = obs.topCandidates(1).first else { continue }
        let b = obs.boundingBox
        lines.append(["t": c.string, "c": c.confidence,
                      "x": b.origin.x, "y": b.origin.y, "w": b.size.width, "h": b.size.height])
    }
    let out: [String: Any] = ["file": path, "w": cg.width, "h": cg.height, "lines": lines]
    let d = try! JSONSerialization.data(withJSONObject: out, options: [])
    FileHandle.standardOutput.write(d); FileHandle.standardOutput.write("\n".data(using: .utf8)!)
}
