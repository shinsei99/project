// スキャン画像PDF／画像ファイルを macOS の Vision で文字起こしする。
//
//   ./ocr_pdf <ファイル> [--max-pages N] [--min-conf 0.0]
//   → 標準出力に「\f」区切りでページごとの本文を書く。文字が取れなければ空。
//
// **なぜ claude vision ではなく macOS Vision か**（2026-08-31）
//   添付のスキャンPDFは約11,100件ある。claude vision（AI業務マネージャーの夜間OCR）は
//   実測 186件/2時間 ＝ 60晩かかるうえ、**同じ定額枠を夜間ジョブ同士で取り合う**。
//   macOS Vision は OS 同梱で、無料・ネットワーク不要・並列に強い。
//   このMacでは写真5,781枚を同じ方式で処理した実績がある。
//
// 注意
//   - 日本語は `ja-JP` を先頭に置く（`en-US` だけだと漢字が化ける）
//   - PDFKit でページを画像化してから Vision にかける。**PDFのテキスト層は見ない**
//     （テキスト層があるものは Python 側で先に処理し、ここへは来ない）
//   - 解像度は 2倍（約144dpi）。1倍だと小さい文字を落とし、3倍以上は遅くなるだけだった

import Foundation
import Vision
import PDFKit
import CoreGraphics
import AppKit

struct Args {
    var path: String = ""
    var maxPages: Int = 30
    var scale: CGFloat = 2.0
}

func parseArgs() -> Args {
    var a = Args()
    var it = CommandLine.arguments.dropFirst().makeIterator()
    while let x = it.next() {
        switch x {
        case "--max-pages": a.maxPages = Int(it.next() ?? "30") ?? 30
        case "--scale":     a.scale = CGFloat(Double(it.next() ?? "2") ?? 2)
        default:            if a.path.isEmpty { a.path = x }
        }
    }
    return a
}

/// 1枚の画像から文字を取り出す。取れなければ空文字。
func recognize(_ cgImage: CGImage) -> String {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true
    // ★日本語を先頭に。順序が結果に効く
    request.recognitionLanguages = ["ja-JP", "en-US"]
    let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
    do {
        try handler.perform([request])
    } catch {
        FileHandle.standardError.write("Vision失敗: \(error)\n".data(using: .utf8)!)
        return ""
    }
    guard let obs = request.results else { return "" }
    return obs.compactMap { $0.topCandidates(1).first?.string }.joined(separator: "\n")
}

/// PDF の1ページを CGImage にする。
func render(_ page: PDFPage, scale: CGFloat) -> CGImage? {
    let bounds = page.bounds(for: .mediaBox)
    let w = Int(bounds.width * scale), h = Int(bounds.height * scale)
    guard w > 0, h > 0, w < 20000, h < 20000 else { return nil }
    guard let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8,
                              bytesPerRow: 0, space: CGColorSpaceCreateDeviceRGB(),
                              bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue) else { return nil }
    ctx.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1))
    ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
    ctx.scaleBy(x: scale, y: scale)
    ctx.translateBy(x: -bounds.origin.x, y: -bounds.origin.y)
    page.draw(with: .mediaBox, to: ctx)
    return ctx.makeImage()
}

let args = parseArgs()
guard !args.path.isEmpty else {
    FileHandle.standardError.write("使い方: ocr_pdf <ファイル> [--max-pages N] [--scale N]\n".data(using: .utf8)!)
    exit(2)
}
let url = URL(fileURLWithPath: args.path)
let ext = url.pathExtension.lowercased()

var pages: [String] = []

if ext == "pdf" {
    guard let doc = PDFDocument(url: url) else {
        FileHandle.standardError.write("PDFを開けない\n".data(using: .utf8)!)
        exit(3)
    }
    let n = min(doc.pageCount, args.maxPages)
    for i in 0..<n {
        guard let page = doc.page(at: i), let img = render(page, scale: args.scale) else {
            pages.append("")
            continue
        }
        pages.append(recognize(img))
    }
} else {
    // 画像ファイル（jpg / png / heic …）
    guard let image = NSImage(contentsOf: url),
          let cg = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        FileHandle.standardError.write("画像を開けない\n".data(using: .utf8)!)
        exit(3)
    }
    pages.append(recognize(cg))
}

print(pages.joined(separator: "\u{0C}"))
