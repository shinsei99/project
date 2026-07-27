import Foundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

// 送付書メーカー アイコン（社内ツール既存ファミリー準拠：角丸ソリッド背景＋白フラット線画）
// モチーフ：書類（送付"書"＝見積書と同系の横線）＋ 封筒（送付）
let size = 1024
let cs = CGColorSpaceCreateDeviceRGB()
guard let ctx = CGContext(data: nil, width: size, height: size, bitsPerComponent: 8,
                          bytesPerRow: 0, space: cs,
                          bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { fatalError() }
let S = CGFloat(size)

// ── 背景: coral #E15B4C + 角丸（既存アイコンと同じ角丸200）──
let bg = CGColor(red: 225/255, green: 91/255, blue: 76/255, alpha: 1)
let bgPath = CGPath(roundedRect: CGRect(x: 0, y: 0, width: S, height: S),
                    cornerWidth: 200, cornerHeight: 200, transform: nil)
ctx.setFillColor(bg); ctx.addPath(bgPath); ctx.fillPath()

let W = CGColor(red: 1, green: 1, blue: 1, alpha: 1)
let coral = CGColor(red: 225/255, green: 91/255, blue: 76/255, alpha: 1)

// ── 送付"書"（白い書類・上部）──
// CoreGraphics は原点が左下
let dx0: CGFloat = 322, dx1: CGFloat = 702      // 幅380
let dy0: CGFloat = 452, dy1: CGFloat = 884      // 高さ432
let fold: CGFloat = 92                            // 右上の折り返し
let doc = CGMutablePath()
doc.move(to:    CGPoint(x: dx0, y: dy0))
doc.addLine(to: CGPoint(x: dx1, y: dy0))
doc.addLine(to: CGPoint(x: dx1, y: dy1 - fold))
doc.addLine(to: CGPoint(x: dx1 - fold, y: dy1))
doc.addLine(to: CGPoint(x: dx0, y: dy1))
doc.closeSubpath()
ctx.setFillColor(W); ctx.addPath(doc); ctx.fillPath()
// 折り返しの三角（薄いcoralで陰影）
let tri = CGMutablePath()
tri.move(to:    CGPoint(x: dx1 - fold, y: dy1))
tri.addLine(to: CGPoint(x: dx1,        y: dy1 - fold))
tri.addLine(to: CGPoint(x: dx1 - fold, y: dy1 - fold))
tri.closeSubpath()
ctx.setFillColor(CGColor(red: 225/255, green: 91/255, blue: 76/255, alpha: 0.28))
ctx.addPath(tri); ctx.fillPath()

// ── 書類の本文ライン（coral・丸端、見積書と同系）──
ctx.setStrokeColor(coral); ctx.setLineCap(.round)
let lx1: CGFloat = 372
let lineDefs: [(CGFloat, CGFloat)] = [ (820, 1.0), (760, 1.0), (700, 0.72) ]  // (y, 長さ比)
for (y, ratio) in lineDefs {
    ctx.setLineWidth(26)
    ctx.move(to:    CGPoint(x: lx1, y: y))
    ctx.addLine(to: CGPoint(x: lx1 + (dx1 - 50 - lx1) * ratio, y: y))
    ctx.strokePath()
}

// ── 封筒（白い本体・下部、書類の下端を覆う＝送付イメージ）──
let ex0: CGFloat = 168, ex1: CGFloat = 856      // 幅688
let ey0: CGFloat = 176, ey1: CGFloat = 566      // 高さ390
let env = CGPath(roundedRect: CGRect(x: ex0, y: ey0, width: ex1 - ex0, height: ey1 - ey0),
                 cornerWidth: 44, cornerHeight: 44, transform: nil)
ctx.setFillColor(W); ctx.addPath(env); ctx.fillPath()

// ── 封筒のフラップ（coralのV）＋下側の折り線 ──
ctx.setStrokeColor(coral); ctx.setLineCap(.round); ctx.setLineJoin(.round)
ctx.setLineWidth(30)
// 上向きV（フラップ）
ctx.move(to:    CGPoint(x: ex0 + 26, y: ey1 - 26))
ctx.addLine(to: CGPoint(x: (ex0 + ex1) / 2, y: ey0 + (ey1 - ey0) * 0.44))
ctx.addLine(to: CGPoint(x: ex1 - 26, y: ey1 - 26))
ctx.strokePath()

// ── 出力 ──
guard let img = ctx.makeImage() else { fatalError() }
let outURL = URL(fileURLWithPath: CommandLine.arguments.count > 1
    ? CommandLine.arguments[1] : "/tmp/soufu-maker-icon.png")
let dest = CGImageDestinationCreateWithURL(outURL as CFURL, UTType.png.identifier as CFString, 1, nil)!
CGImageDestinationAddImage(dest, img, nil)
CGImageDestinationFinalize(dest)
print("Saved: \(outURL.path)")
