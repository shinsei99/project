import Foundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

// 買取DMメーカー アイコン（社内ツール既存ファミリー準拠：角丸ソリッド背景＋白フラット線画）
// モチーフ：家（🏠 不動産＝買取対象）＋ 封筒（DM）
let size = 1024
let cs = CGColorSpaceCreateDeviceRGB()
guard let ctx = CGContext(data: nil, width: size, height: size, bitsPerComponent: 8,
                          bytesPerRow: 0, space: cs,
                          bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { fatalError() }
let S = CGFloat(size)

// ── 背景: 紫 #6C5CE7 + 角丸（既存と同じ角丸200）──
let bg = CGColor(red: 108/255, green: 92/255, blue: 231/255, alpha: 1)
let bgPath = CGPath(roundedRect: CGRect(x: 0, y: 0, width: S, height: S),
                    cornerWidth: 200, cornerHeight: 200, transform: nil)
ctx.setFillColor(bg); ctx.addPath(bgPath); ctx.fillPath()

let W = CGColor(red: 1, green: 1, blue: 1, alpha: 1)
let purple = CGColor(red: 108/255, green: 92/255, blue: 231/255, alpha: 1)

// ── 家（白・上部）──
// 屋根（三角）
let roof = CGMutablePath()
roof.move(to:    CGPoint(x: 250, y: 604))
roof.addLine(to: CGPoint(x: 512, y: 866))
roof.addLine(to: CGPoint(x: 774, y: 604))
roof.closeSubpath()
ctx.setFillColor(W); ctx.addPath(roof); ctx.fillPath()
// 本体（角丸rect、屋根の下）
let body = CGPath(roundedRect: CGRect(x: 322, y: 372, width: 380, height: 252),
                  cornerWidth: 20, cornerHeight: 20, transform: nil)
ctx.setFillColor(W); ctx.addPath(body); ctx.fillPath()

// ── 封筒（DM）＝家の下半分にかぶせる白い封筒 ──
let ex0: CGFloat = 214, ex1: CGFloat = 810      // 幅596
let ey0: CGFloat = 180, ey1: CGFloat = 486      // 高さ306
let env = CGPath(roundedRect: CGRect(x: ex0, y: ey0, width: ex1 - ex0, height: ey1 - ey0),
                 cornerWidth: 40, cornerHeight: 40, transform: nil)
ctx.setFillColor(W); ctx.addPath(env); ctx.fillPath()

// 封筒のフラップ（紫のV）
ctx.setStrokeColor(purple); ctx.setLineCap(.round); ctx.setLineJoin(.round)
ctx.setLineWidth(30)
ctx.move(to:    CGPoint(x: ex0 + 26, y: ey1 - 24))
ctx.addLine(to: CGPoint(x: (ex0 + ex1)/2, y: ey0 + (ey1 - ey0) * 0.40))
ctx.addLine(to: CGPoint(x: ex1 - 26, y: ey1 - 24))
ctx.strokePath()

// ── 家の窓（紫の小さな四角、屋根の直下）──
ctx.setFillColor(purple)
let win = CGPath(roundedRect: CGRect(x: 462, y: 520, width: 100, height: 76),
                 cornerWidth: 12, cornerHeight: 12, transform: nil)
ctx.addPath(win); ctx.fillPath()

// ── 出力 ──
guard let img = ctx.makeImage() else { fatalError() }
let outURL = URL(fileURLWithPath: CommandLine.arguments.count > 1
    ? CommandLine.arguments[1] : "/tmp/kaitori-dm-icon.png")
let dest = CGImageDestinationCreateWithURL(outURL as CFURL, UTType.png.identifier as CFString, 1, nil)!
CGImageDestinationAddImage(dest, img, nil)
CGImageDestinationFinalize(dest)
print("Saved: \(outURL.path)")
