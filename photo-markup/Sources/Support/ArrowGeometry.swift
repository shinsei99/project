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
}

/// 注釈テキストのフォント解決と選択肢。
enum AnnotationFont {
    static func uiFont(name: String, size: CGFloat, bold: Bool) -> UIFont {
        if !name.isEmpty, let f = UIFont(name: name, size: size) { return f }
        return bold ? .boldSystemFont(ofSize: size) : .systemFont(ofSize: size)
    }

    /// 書体の選択肢（日本語表示に耐える代表フォント）。
    static let choices: [(label: String, name: String)] = [
        ("標準", ""),
        ("丸ゴ", "HiraMaruProN-W4"),
        ("明朝", "HiraMinProN-W6"),
        ("太ゴ", "HiraginoSans-W8"),
    ]
}
