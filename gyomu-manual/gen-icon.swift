import Foundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

let size = 1024
let cs = CGColorSpaceCreateDeviceRGB()
guard let ctx = CGContext(data: nil, width: size, height: size, bitsPerComponent: 8,
                          bytesPerRow: 0, space: cs,
                          bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { fatalError() }
let S = CGFloat(size)

// ── 背景: 青 #4472C4 + 角丸 ──
let bgBlue = CGColor(red: 68/255, green: 114/255, blue: 196/255, alpha: 1)
let bgPath = CGPath(roundedRect: CGRect(x: 0, y: 0, width: S, height: S),
                    cornerWidth: 200, cornerHeight: 200, transform: nil)
ctx.setFillColor(bgBlue)
ctx.addPath(bgPath); ctx.fillPath()

let W = CGColor(red: 1, green: 1, blue: 1, alpha: 1)
let lineBlue = CGColor(red: 68/255, green: 114/255, blue: 196/255, alpha: 1)

// ── 開いた本（フラット・上から見た形）──
// 左ページ
let lx1: CGFloat = 140, lx2: CGFloat = 488
let py1: CGFloat = 210, py2: CGFloat = 810
let leftPage = CGMutablePath()
leftPage.move(to:    CGPoint(x: lx1,    y: py1 + 40))
leftPage.addLine(to: CGPoint(x: lx2,    y: py1))
leftPage.addLine(to: CGPoint(x: lx2,    y: py2))
leftPage.addLine(to: CGPoint(x: lx1,    y: py2 - 40))
leftPage.closeSubpath()
ctx.setFillColor(W); ctx.addPath(leftPage); ctx.fillPath()

// 右ページ
let rx1: CGFloat = 536, rx2: CGFloat = 884
let rightPage = CGMutablePath()
rightPage.move(to:    CGPoint(x: rx1,    y: py1))
rightPage.addLine(to: CGPoint(x: rx2,    y: py1 + 40))
rightPage.addLine(to: CGPoint(x: rx2,    y: py2 - 40))
rightPage.addLine(to: CGPoint(x: rx1,    y: py2))
rightPage.closeSubpath()
ctx.setFillColor(W); ctx.addPath(rightPage); ctx.fillPath()

// ── 本文ライン（青・丸端）──
ctx.setStrokeColor(lineBlue)
ctx.setLineCap(.round)

// 左ページ：6行（最終行だけ短め）
let lLineX1: CGFloat = 200, lLineX2: CGFloat = 450
let rLineX1: CGFloat = 574, rLineX2: CGFloat = 824
let lineWidths: [CGFloat] = [1.0, 0.92, 0.92, 0.92, 0.92, 0.55]
let lineYStart: CGFloat = 320
let lineStep:   CGFloat = 90

for (i, ratio) in lineWidths.enumerated() {
    let y = lineYStart + CGFloat(i) * lineStep
    let lw: CGFloat = i < 2 ? 30 : 24
    ctx.setLineWidth(lw)
    // 左ページ
    ctx.move(to:    CGPoint(x: lLineX1, y: y))
    ctx.addLine(to: CGPoint(x: lLineX1 + (lLineX2 - lLineX1) * ratio, y: y))
    ctx.strokePath()
    // 右ページ
    ctx.move(to:    CGPoint(x: rLineX1, y: y))
    ctx.addLine(to: CGPoint(x: rLineX1 + (rLineX2 - rLineX1) * ratio, y: y))
    ctx.strokePath()
}

// ── 中央の綴じ目（細い青）──
ctx.setStrokeColor(CGColor(red: 68/255, green: 114/255, blue: 196/255, alpha: 0.35))
ctx.setLineWidth(10)
ctx.setLineCap(.butt)
ctx.move(to:    CGPoint(x: S/2, y: py1 + 10))
ctx.addLine(to: CGPoint(x: S/2, y: py2 - 10))
ctx.strokePath()

// ── 出力 ──
guard let img = ctx.makeImage() else { fatalError() }
let outURL = URL(fileURLWithPath: CommandLine.arguments.count > 1
    ? CommandLine.arguments[1]
    : "/tmp/gyomu-manual-icon.png")
let dest = CGImageDestinationCreateWithURL(outURL as CFURL, UTType.png.identifier as CFString, 1, nil)!
CGImageDestinationAddImage(dest, img, nil)
CGImageDestinationFinalize(dest)
print("Saved: \(outURL.path)")
