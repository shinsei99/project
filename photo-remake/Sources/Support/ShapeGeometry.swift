import CoreGraphics
import UIKit

/// 図形注釈の種類。
enum ShapeKind: String, CaseIterable, Equatable, Identifiable {
    case rect          // 四角
    case roundedRect   // 角丸四角
    case ellipse       // 丸・楕円
    case triangle      // 三角
    case diamond       // ひし形
    case pentagon      // 五角形
    case hexagon       // 六角形
    case star          // 星
    case heart         // ハート
    case bubble        // 吹き出し
    case cross         // 十字（＋）
    case xmark         // バツ（×）

    var id: String { rawValue }

    var label: String {
        switch self {
        case .rect: return "四角"
        case .roundedRect: return "角丸"
        case .ellipse: return "丸"
        case .triangle: return "三角"
        case .diamond: return "ひし形"
        case .pentagon: return "五角形"
        case .hexagon: return "六角形"
        case .star: return "星"
        case .heart: return "ハート"
        case .bubble: return "吹き出し"
        case .cross: return "十字"
        case .xmark: return "バツ"
        }
    }

    /// 追加した直後の既定サイズ（正規化・半サイズ）。細長い形は縦横比を変えておく。
    var defaultHalfSize: CGSize {
        switch self {
        case .bubble: return CGSize(width: 0.20, height: 0.13)
        case .heart, .star, .pentagon, .hexagon, .cross, .xmark, .triangle, .diamond:
            return CGSize(width: 0.15, height: 0.15)
        case .rect, .roundedRect, .ellipse:
            return CGSize(width: 0.20, height: 0.13)
        }
    }
}

/// 図形注釈のパス生成。プレビュー(SwiftUI)と書き出し(UIKit)で同じ関数を使い、形を一致させる。
/// すべて閉じたパスなので、塗り・枠線のどちらでも成立する。
enum ShapeGeometry {

    /// `rect` にぴったり収まる図形パス。
    static func path(_ kind: ShapeKind, in rect: CGRect) -> CGPath {
        guard rect.width > 0, rect.height > 0 else { return CGMutablePath() }
        switch kind {
        case .rect:
            return CGPath(rect: rect, transform: nil)
        case .roundedRect:
            let r = min(rect.width, rect.height) * 0.18
            return CGPath(roundedRect: rect, cornerWidth: r, cornerHeight: r, transform: nil)
        case .ellipse:
            return CGPath(ellipseIn: rect, transform: nil)
        case .bubble:
            return bubblePath(in: rect)
        default:
            // 単位矩形(0,0)-(1,1)で作ってから rect へ引き伸ばす
            var t = CGAffineTransform(translationX: rect.minX, y: rect.minY)
                .scaledBy(x: rect.width, y: rect.height)
            let unit = unitPath(kind)
            return unit.copy(using: &t) ?? unit
        }
    }

    // MARK: - 単位矩形内のパス

    private static func unitPath(_ kind: ShapeKind) -> CGPath {
        switch kind {
        case .triangle:
            return polygon([CGPoint(x: 0.5, y: 0), CGPoint(x: 1, y: 1), CGPoint(x: 0, y: 1)])
        case .diamond:
            return polygon([CGPoint(x: 0.5, y: 0), CGPoint(x: 1, y: 0.5),
                            CGPoint(x: 0.5, y: 1), CGPoint(x: 0, y: 0.5)])
        case .pentagon:
            return polygon(normalized(regular(sides: 5)))
        case .hexagon:
            return polygon(normalized(regular(sides: 6)))
        case .star:
            return polygon(normalized(star(points: 5, innerRatio: 0.42)))
        case .cross:
            return polygon(crossPoints())
        case .xmark:
            let c = CGPoint(x: 0.5, y: 0.5)
            return polygon(normalized(crossPoints().map { rotate($0, around: c, by: .pi / 4) }))
        case .heart:
            return heartPath()
        default:
            return CGPath(rect: CGRect(x: 0, y: 0, width: 1, height: 1), transform: nil)
        }
    }

    /// 中心(0.5,0.5)・半径0.5の正多角形（頂点が真上から始まる）。
    private static func regular(sides: Int) -> [CGPoint] {
        (0..<sides).map { i in
            let a = -CGFloat.pi / 2 + CGFloat(i) * 2 * .pi / CGFloat(sides)
            return CGPoint(x: 0.5 + 0.5 * cos(a), y: 0.5 + 0.5 * sin(a))
        }
    }

    /// 星形（外周と内周の頂点を交互に）。
    private static func star(points: Int, innerRatio: CGFloat) -> [CGPoint] {
        (0..<(points * 2)).map { i in
            let a = -CGFloat.pi / 2 + CGFloat(i) * .pi / CGFloat(points)
            let r: CGFloat = i.isMultiple(of: 2) ? 0.5 : 0.5 * innerRatio
            return CGPoint(x: 0.5 + r * cos(a), y: 0.5 + r * sin(a))
        }
    }

    /// 十字（＋）。腕の太さは全体の 0.34。
    private static func crossPoints() -> [CGPoint] {
        let a: CGFloat = 0.33, b: CGFloat = 0.67
        return [
            CGPoint(x: a, y: 0), CGPoint(x: b, y: 0), CGPoint(x: b, y: a),
            CGPoint(x: 1, y: a), CGPoint(x: 1, y: b), CGPoint(x: b, y: b),
            CGPoint(x: b, y: 1), CGPoint(x: a, y: 1), CGPoint(x: a, y: b),
            CGPoint(x: 0, y: b), CGPoint(x: 0, y: a), CGPoint(x: a, y: a),
        ]
    }

    private static func rotate(_ p: CGPoint, around c: CGPoint, by angle: CGFloat) -> CGPoint {
        let dx = p.x - c.x, dy = p.y - c.y
        return CGPoint(x: c.x + dx * cos(angle) - dy * sin(angle),
                       y: c.y + dx * sin(angle) + dy * cos(angle))
    }

    /// 頂点群を単位矩形いっぱいに伸縮する（＝指定した枠にぴったり収まる）。
    private static func normalized(_ pts: [CGPoint]) -> [CGPoint] {
        let xs = pts.map(\.x), ys = pts.map(\.y)
        guard let minX = xs.min(), let maxX = xs.max(),
              let minY = ys.min(), let maxY = ys.max(),
              maxX > minX, maxY > minY else { return pts }
        return pts.map { CGPoint(x: ($0.x - minX) / (maxX - minX),
                                 y: ($0.y - minY) / (maxY - minY)) }
    }

    private static func polygon(_ pts: [CGPoint]) -> CGPath {
        let p = CGMutablePath()
        guard let first = pts.first else { return p }
        p.move(to: first)
        for q in pts.dropFirst() { p.addLine(to: q) }
        p.closeSubpath()
        return p
    }

    /// 単位矩形内のハート。
    private static func heartPath() -> CGPath {
        let p = CGMutablePath()
        p.move(to: CGPoint(x: 0.5, y: 1.0))
        p.addCurve(to: CGPoint(x: 0.0, y: 0.30),
                   control1: CGPoint(x: 0.10, y: 0.70), control2: CGPoint(x: 0.0, y: 0.45))
        p.addCurve(to: CGPoint(x: 0.35, y: 0.0),
                   control1: CGPoint(x: 0.0, y: 0.10), control2: CGPoint(x: 0.20, y: 0.0))
        p.addCurve(to: CGPoint(x: 0.5, y: 0.15),
                   control1: CGPoint(x: 0.45, y: 0.0), control2: CGPoint(x: 0.5, y: 0.08))
        p.addCurve(to: CGPoint(x: 0.65, y: 0.0),
                   control1: CGPoint(x: 0.5, y: 0.08), control2: CGPoint(x: 0.55, y: 0.0))
        p.addCurve(to: CGPoint(x: 1.0, y: 0.30),
                   control1: CGPoint(x: 0.80, y: 0.0), control2: CGPoint(x: 1.0, y: 0.10))
        p.addCurve(to: CGPoint(x: 0.5, y: 1.0),
                   control1: CGPoint(x: 1.0, y: 0.45), control2: CGPoint(x: 0.90, y: 0.70))
        p.closeSubpath()
        return p
    }

    /// 吹き出し（角丸の本体＋左下のしっぽ）を1本の閉じたパスで作る。
    /// 単位矩形で作ると角丸がつぶれるため、実寸の rect で直接組み立てる。
    private static func bubblePath(in rect: CGRect) -> CGPath {
        let x0 = rect.minX, x1 = rect.maxX, y0 = rect.minY
        let bodyH = rect.height * 0.78
        let by1 = y0 + bodyH
        let r = max(1, min(rect.width, bodyH) * 0.20)
        let p = CGMutablePath()
        p.move(to: CGPoint(x: x0 + r, y: y0))
        p.addArc(tangent1End: CGPoint(x: x1, y: y0), tangent2End: CGPoint(x: x1, y: by1), radius: r)
        p.addArc(tangent1End: CGPoint(x: x1, y: by1), tangent2End: CGPoint(x: x0, y: by1), radius: r)
        // 下辺を右→左へ。途中でしっぽへ降りて戻る。
        p.addLine(to: CGPoint(x: x0 + rect.width * 0.46, y: by1))
        p.addLine(to: CGPoint(x: x0 + rect.width * 0.20, y: rect.maxY))
        p.addLine(to: CGPoint(x: x0 + rect.width * 0.30, y: by1))
        p.addArc(tangent1End: CGPoint(x: x0, y: by1), tangent2End: CGPoint(x: x0, y: y0), radius: r)
        p.addArc(tangent1End: CGPoint(x: x0, y: y0), tangent2End: CGPoint(x: x1, y: y0), radius: r)
        p.closeSubpath()
        return p
    }
}
