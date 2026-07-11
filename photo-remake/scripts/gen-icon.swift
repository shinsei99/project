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

// ── 背景：ダークプレミアムグラデーション ──
let bg = [CGColor(red: 0.05, green: 0.08, blue: 0.18, alpha: 1),
          CGColor(red: 0.13, green: 0.06, blue: 0.26, alpha: 1)] as CFArray
ctx.drawLinearGradient(
    CGGradient(colorsSpace: cs, colors: bg, locations: [0, 1])!,
    start: CGPoint(x: 0, y: S), end: CGPoint(x: S, y: 0), options: [])

// ── 写真カード（白・角丸・わずかに傾ける）──
ctx.saveGState()
ctx.translateBy(x: S / 2, y: S / 2 - 10)
ctx.rotate(by: -.pi * 0.04)

let cardW: CGFloat = 660, cardH: CGFloat = 530
let cardRect = CGRect(x: -cardW / 2, y: -cardH / 2, width: cardW, height: cardH)
let cardPath = CGPath(roundedRect: cardRect, cornerWidth: 56, cornerHeight: 56, transform: nil)

// カードの影
ctx.setShadow(offset: CGSize(width: 0, height: -28), blur: 72,
              color: CGColor(red: 0, green: 0, blue: 0, alpha: 0.60))
ctx.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1))
ctx.addPath(cardPath); ctx.fillPath()

// カード内：ミニマルな写真感（淡い空→白のグラデ）
ctx.addPath(cardPath); ctx.clip()
let inner = [CGColor(red: 0.85, green: 0.91, blue: 0.99, alpha: 1),
             CGColor(red: 0.96, green: 0.97, blue: 1.00, alpha: 1)] as CFArray
ctx.drawLinearGradient(
    CGGradient(colorsSpace: cs, colors: inner, locations: [0, 1])!,
    start: CGPoint(x: 0, y: cardH / 2), end: CGPoint(x: 0, y: -cardH / 2), options: [])

// 地平線（細くて上品）
ctx.setStrokeColor(CGColor(red: 0.75, green: 0.85, blue: 0.96, alpha: 0.8))
ctx.setLineWidth(2.5)
ctx.move(to: CGPoint(x: -cardW / 2 + 60, y: -20))
ctx.addLine(to: CGPoint(x: cardW / 2 - 60, y: -20))
ctx.strokePath()

// 太陽（控えめなゴールド円）
ctx.setFillColor(CGColor(red: 0.95, green: 0.85, blue: 0.58, alpha: 0.55))
ctx.fillEllipse(in: CGRect(x: -cardW / 2 + 80, y: 20, width: 96, height: 96))

ctx.restoreGState()

// ── 鉛筆（ゴールド・スリム・エレガント）──
ctx.saveGState()
ctx.translateBy(x: S * 0.63, y: S * 0.41)
ctx.rotate(by: -.pi * 0.25)  // 右上から左下に向かう
ctx.setShadow(offset: CGSize(width: 6, height: -10), blur: 22,
              color: CGColor(red: 0, green: 0, blue: 0, alpha: 0.45))

let pLen: CGFloat = 390, pW: CGFloat = 52

// 消しゴム（ピンク・丸角）
let eraserRect = CGRect(x: -pW / 2, y: pLen * 0.30, width: pW, height: pLen * 0.14)
ctx.setFillColor(CGColor(red: 0.98, green: 0.48, blue: 0.60, alpha: 1))
ctx.addPath(CGPath(roundedRect: eraserRect, cornerWidth: 10, cornerHeight: 10, transform: nil))
ctx.fillPath()

// 金属バンド（シルバー）
ctx.setFillColor(CGColor(red: 0.80, green: 0.84, blue: 0.90, alpha: 1))
ctx.fill(CGRect(x: -pW / 2, y: pLen * 0.22, width: pW, height: pLen * 0.10))

// 本体グラデーション（ゴールド〜アンバー）
let bodyRect = CGRect(x: -pW / 2, y: -pLen * 0.22, width: pW, height: pLen * 0.46)
ctx.saveGState()
ctx.clip(to: bodyRect)
let gold = [CGColor(red: 1.00, green: 0.82, blue: 0.12, alpha: 1),
            CGColor(red: 0.88, green: 0.56, blue: 0.00, alpha: 1)] as CFArray
ctx.drawLinearGradient(
    CGGradient(colorsSpace: cs, colors: gold, locations: [0, 1])!,
    start: CGPoint(x: -pW / 2, y: 0), end: CGPoint(x: pW / 2, y: 0), options: [])
ctx.restoreGState()

// 削り部分（木の色）
let wood = CGMutablePath()
wood.move(to: CGPoint(x: -pW / 2, y: -pLen * 0.22))
wood.addLine(to: CGPoint(x: 0, y: -pLen * 0.40))
wood.addLine(to: CGPoint(x: pW / 2, y: -pLen * 0.22))
wood.closeSubpath()
ctx.setFillColor(CGColor(red: 0.87, green: 0.66, blue: 0.46, alpha: 1))
ctx.addPath(wood); ctx.fillPath()

// 芯（グラファイト）
let lead = CGMutablePath()
lead.move(to: CGPoint(x: -9, y: -pLen * 0.36))
lead.addLine(to: CGPoint(x: 0, y: -pLen * 0.40))
lead.addLine(to: CGPoint(x: 9, y: -pLen * 0.36))
lead.closeSubpath()
ctx.setFillColor(CGColor(red: 0.15, green: 0.15, blue: 0.18, alpha: 1))
ctx.addPath(lead); ctx.fillPath()

ctx.restoreGState()

// 書き出し
guard let img = ctx.makeImage() else { fatalError() }
let out = URL(fileURLWithPath: CommandLine.arguments[1])
let dest = CGImageDestinationCreateWithURL(out as CFURL, UTType.png.identifier as CFString, 1, nil)!
CGImageDestinationAddImage(dest, img, nil)
if CGImageDestinationFinalize(dest) { print("wrote \(out.path)") } else { fatalError("write") }
