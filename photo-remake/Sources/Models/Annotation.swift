import SwiftUI

/// 画像の上に載せる注釈（テキスト or 矢印）。
/// サイズ・位置はすべて画像に対する正規化値で保持し、プレビューと書き出しを一致させる。
struct Annotation: Identifiable, Equatable {
    enum Kind: Equatable { case text, arrow, mosaic }

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
    /// フォントウェイト（0=UltraLight … 4=Regular … 6=Bold … 8=Black）
    var fontWeightIndex: Int = 6
    /// フォントサイズ（画像の高さに対する割合）。
    var fontHeightFraction: CGFloat = 0.07
    var isVertical: Bool = false          // 縦書き
    var hasOutline: Bool = true
    var outlineColorHex: String = "#000000"
    /// 縁取り太さ（フォントptに対する割合 0...0.25）。
    var outlineWidthRatio: CGFloat = 0.06
    var outlineOpacity: CGFloat = 1
    var hasShadow: Bool = false

    // ---- 矢印（尾→先端の2点で定義。向き・長さは2点から決まる）----
    var arrowStart: CGPoint = CGPoint(x: 0.38, y: 0.58)   // 尾
    var arrowEnd: CGPoint = CGPoint(x: 0.62, y: 0.42)     // 先端（矢じり）
    /// 矢印の軸の太さ（長さに対する割合 0.06...0.30）。
    var arrowThicknessRatio: CGFloat = 0.14

    // ---- モザイク（軸並行の矩形領域。中心＝position、半サイズを正規化で保持）----
    var mosaicHalfW: CGFloat = 0.14
    var mosaicHalfH: CGFloat = 0.06

    static func text(at p: CGPoint = CGPoint(x: 0.5, y: 0.5)) -> Annotation {
        Annotation(kind: .text, position: p)
    }
    static func mosaic(at p: CGPoint = CGPoint(x: 0.5, y: 0.5)) -> Annotation {
        Annotation(kind: .mosaic, position: p, colorHex: "#000000")
    }
    static func arrow(at p: CGPoint = CGPoint(x: 0.5, y: 0.5)) -> Annotation {
        var a = Annotation(kind: .arrow, position: p, colorHex: "#FF2D55")
        a.arrowStart = CGPoint(x: p.x - 0.13, y: p.y + 0.09)
        a.arrowEnd = CGPoint(x: p.x + 0.13, y: p.y - 0.09)
        return a
    }
}
