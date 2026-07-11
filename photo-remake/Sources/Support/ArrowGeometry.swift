import CoreGraphics
import UIKit

/// 原点中心・+x 方向を向いた矢印パス。プレビュー(SwiftUI)と書き出し(UIKit)で共用し形を一致させる。
enum ArrowGeometry {
    static func path(length: CGFloat, thickness: CGFloat) -> CGPath {
        let p = CGMutablePath()
        let half = length / 2
        let shaftH = thickness
        let headLen = min(length * 0.42, thickness * 2.6)
        let headH = thickness * 2.6
        let shaftEndX = half - headLen

        p.move(to: CGPoint(x: -half, y: -shaftH / 2))
        p.addLine(to: CGPoint(x: shaftEndX, y: -shaftH / 2))
        p.addLine(to: CGPoint(x: shaftEndX, y: -headH / 2))
        p.addLine(to: CGPoint(x: half, y: 0))
        p.addLine(to: CGPoint(x: shaftEndX, y: headH / 2))
        p.addLine(to: CGPoint(x: shaftEndX, y: shaftH / 2))
        p.addLine(to: CGPoint(x: -half, y: shaftH / 2))
        p.closeSubpath()
        return p
    }

    /// 当たり判定・バウンディング用の外形サイズ。
    static func boundingSize(length: CGFloat, thickness: CGFloat) -> CGSize {
        CGSize(width: length, height: thickness * 2.6)
    }

    /// 尾 `a` から先端 `b` へ向かう矢印パス（そのままの座標系で返す）。
    static func pathBetween(from a: CGPoint, to b: CGPoint, thickness: CGFloat) -> CGPath {
        let dx = b.x - a.x, dy = b.y - a.y
        let length = max(1, (dx * dx + dy * dy).squareRoot())
        let angle = atan2(dy, dx)
        let base = path(length: length, thickness: thickness) // 原点中心・+x 向き
        var t = CGAffineTransform(translationX: (a.x + b.x) / 2, y: (a.y + b.y) / 2)
            .rotated(by: angle)
        return base.copy(using: &t) ?? base
    }
}

/// 注釈テキストのフォント解決と選択肢。
enum AnnotationFont {
    static let weights: [UIFont.Weight] = [
        .ultraLight, .thin, .light, .regular, .medium, .semibold, .bold, .heavy, .black
    ]
    static let weightLabels = ["極細", "細", "やや細", "標準", "中", "やや太", "太", "極太", "黒"]

    static func uiFont(name: String, size: CGFloat, weightIndex: Int) -> UIFont {
        let w = weights[max(0, min(weightIndex, weights.count - 1))]
        if !name.isEmpty, let f = UIFont(name: name, size: size) { return f }
        return .systemFont(ofSize: size, weight: w)
    }

    /// 書体の選択肢（日本語表示に耐える代表フォント）。
    static let choices: [(label: String, name: String)] = [
        ("標準", ""),
        ("丸ゴ", "HiraMaruProN-W4"),
        ("明朝", "HiraMinProN-W6"),
        ("太ゴ", "HiraginoSans-W8"),
    ]
}
