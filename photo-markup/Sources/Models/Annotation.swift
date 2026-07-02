import SwiftUI

/// 画像の上に載せる注釈（テキスト or 矢印）。
/// サイズ・位置はすべて画像に対する正規化値で保持し、プレビューと書き出しを一致させる。
struct Annotation: Identifiable, Equatable {
    enum Kind: Equatable { case text, arrow }

    let id = UUID()
    var kind: Kind

    /// 中心位置（画像フレーム内の 0...1 正規化座標）。
    var position: CGPoint = CGPoint(x: 0.5, y: 0.5)
    /// 回転角。
    var rotation: Angle = .zero
    /// 主色（テキスト色 / 矢印色）。
    var colorHex: String = "#FF2D55"

    // ---- テキスト ----
    var text: String = "テキスト"
    var fontName: String = ""            // 空ならシステムフォント
    var isBold: Bool = true
    /// フォントサイズ（画像の高さに対する割合）。
    var fontHeightFraction: CGFloat = 0.07
    var hasOutline: Bool = true
    var outlineColorHex: String = "#000000"
    /// 縁取り太さ（フォントptに対する割合 0...0.25）。
    var outlineWidthRatio: CGFloat = 0.06
    var outlineOpacity: CGFloat = 1
    var hasShadow: Bool = false

    // ---- 矢印 ----
    /// 矢印の長さ（画像短辺に対する割合）。
    var arrowLengthFraction: CGFloat = 0.32
    /// 矢印の軸の太さ（長さに対する割合）。
    var arrowThicknessRatio: CGFloat = 0.14

    static func text(at p: CGPoint = CGPoint(x: 0.5, y: 0.5)) -> Annotation {
        Annotation(kind: .text, position: p)
    }
    static func arrow(at p: CGPoint = CGPoint(x: 0.5, y: 0.5)) -> Annotation {
        Annotation(kind: .arrow, position: p, colorHex: "#FF2D55")
    }
}
