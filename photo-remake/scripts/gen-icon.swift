import Foundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

// 1024pt アプリアイコンを生成（写真カード＋ピンクの矢印＝注釈）。
let size = 1024
let cs = CGColorSpaceCreateDeviceRGB()
guard let ctx = CGContext(data: nil, width: size, height: size, bitsPerComponent: 8,
                          bytesPerRow: 0, space: cs,
                          bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else {
    fatalError("ctx")
}
let S = CGFloat(size)

// 背景グラデーション（青→インディゴ）
let colors = [CGColor(red: 0.04, green: 0.52, blue: 1, alpha: 1),
              CGColor(red: 0.37, green: 0.36, blue: 0.9, alpha: 1)] as CFArray
let grad = CGGradient(colorsSpace: cs, colors: colors, locations: [0, 1])!
ctx.drawLinearGradient(grad, start: CGPoint(x: 0, y: S), end: CGPoint(x: S, y: 0), options: [])

// 白い写真カード
let card = CGRect(x: 205, y: 250, width: 614, height: 524)
let cardPath = CGPath(roundedRect: card, cornerWidth: 74, cornerHeight: 74, transform: nil)
ctx.addPath(cardPath)
ctx.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 0.96))
ctx.fillPath()

// カード内に簡単な風景（空・太陽・山）
ctx.saveGState()
ctx.addPath(cardPath); ctx.clip()
ctx.setFillColor(CGColor(red: 0.82, green: 0.91, blue: 1, alpha: 1)); ctx.fill(card)
ctx.setFillColor(CGColor(red: 1, green: 0.81, blue: 0.24, alpha: 1))
ctx.fillEllipse(in: CGRect(x: card.minX + 78, y: card.maxY - 190, width: 118, height: 118))
ctx.setFillColor(CGColor(red: 0.30, green: 0.72, blue: 0.42, alpha: 1))
ctx.beginPath()
ctx.move(to: CGPoint(x: card.minX, y: card.minY + 20))
ctx.addLine(to: CGPoint(x: card.midX - 30, y: card.midY + 10))
ctx.addLine(to: CGPoint(x: card.midX + 150, y: card.minY + 20))
ctx.closePath(); ctx.fillPath()
ctx.setFillColor(CGColor(red: 0.24, green: 0.62, blue: 0.36, alpha: 1))
ctx.beginPath()
ctx.move(to: CGPoint(x: card.midX - 40, y: card.minY + 20))
ctx.addLine(to: CGPoint(x: card.midX + 190, y: card.midY + 60))
ctx.addLine(to: CGPoint(x: card.maxX, y: card.minY + 20))
ctx.closePath(); ctx.fillPath()
ctx.restoreGState()

// ピンクの矢印（原点中心・+x 向き→回転）
func arrowPath(length: CGFloat, thickness: CGFloat) -> CGPath {
    let p = CGMutablePath()
    let half = length / 2, shaftH = thickness
    let headLen = min(length * 0.42, thickness * 2.6), headH = thickness * 2.6
    let sx = half - headLen
    p.move(to: CGPoint(x: -half, y: -shaftH / 2))
    p.addLine(to: CGPoint(x: sx, y: -shaftH / 2))
    p.addLine(to: CGPoint(x: sx, y: -headH / 2))
    p.addLine(to: CGPoint(x: half, y: 0))
    p.addLine(to: CGPoint(x: sx, y: headH / 2))
    p.addLine(to: CGPoint(x: sx, y: shaftH / 2))
    p.addLine(to: CGPoint(x: -half, y: shaftH / 2))
    p.closeSubpath()
    return p
}
ctx.saveGState()
ctx.translateBy(x: 560, y: 470)
ctx.rotate(by: .pi * 0.80)
ctx.setShadow(offset: CGSize(width: 0, height: -14), blur: 26,
              color: CGColor(red: 0, green: 0, blue: 0, alpha: 0.28))
ctx.addPath(arrowPath(length: 540, thickness: 84))
ctx.setFillColor(CGColor(red: 1, green: 0.18, blue: 0.33, alpha: 1))
ctx.fillPath()
ctx.restoreGState()

guard let img = ctx.makeImage() else { fatalError("img") }
let out = URL(fileURLWithPath: CommandLine.arguments[1])
let dest = CGImageDestinationCreateWithURL(out as CFURL, UTType.png.identifier as CFString, 1, nil)!
CGImageDestinationAddImage(dest, img, nil)
if CGImageDestinationFinalize(dest) { print("wrote \(out.path)") } else { fatalError("write") }
