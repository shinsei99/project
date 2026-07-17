import SwiftUI
import UIKit

/// 16進カラー（#RRGGBB / #RRGGBBAA）と SwiftUI.Color / UIColor の相互変換。
/// 注釈の色は Hex 文字列で保持し、プレビュー(SwiftUI)と書き出し(UIKit描画)で同じ色を使う。
extension UIColor {
    convenience init(hex: String) {
        var s = hex.trimmingCharacters(in: .whitespacesAndNewlines)
        if s.hasPrefix("#") { s.removeFirst() }
        var value: UInt64 = 0
        Scanner(string: s).scanHexInt64(&value)
        let r, g, b, a: CGFloat
        switch s.count {
        case 8:
            r = CGFloat((value >> 24) & 0xFF) / 255
            g = CGFloat((value >> 16) & 0xFF) / 255
            b = CGFloat((value >> 8) & 0xFF) / 255
            a = CGFloat(value & 0xFF) / 255
        default: // 6桁 or 不正 → 不透明扱い
            r = CGFloat((value >> 16) & 0xFF) / 255
            g = CGFloat((value >> 8) & 0xFF) / 255
            b = CGFloat(value & 0xFF) / 255
            a = 1
        }
        self.init(red: r, green: g, blue: b, alpha: a)
    }

    var hexString: String {
        var r: CGFloat = 0, g: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
        getRed(&r, green: &g, blue: &b, alpha: &a)
        return String(format: "#%02X%02X%02X", Int(r * 255), Int(g * 255), Int(b * 255))
    }
}

extension Color {
    init(hex: String) { self.init(uiColor: UIColor(hex: hex)) }
}

/// 注釈で使うプリセットカラー（参考UIの帯に近い並び）。
enum PalettePresets {
    /// 1段目：濃い・鮮やかな基本色（11色）。
    static let row1: [String] = [
        "#FFFFFF", "#000000", "#FF3B30", "#FF9500", "#FFCC00", "#34C759",
        "#00C7BE", "#007AFF", "#5856D6", "#AF52DE", "#8B5E3C",
    ]
    /// 2段目：淡い・パステル寄り（10色）。1段目とはっきり差が出るよう明度を上げた色。
    static let row2: [String] = [
        "#8E8E93", "#FF9FA8", "#FFD8A8", "#FFF3B0", "#A8E6A3",
        "#A0E7E5", "#A9CCE3", "#C3B1E1", "#E5B8E8", "#C9A17A",
    ]
    /// 互換用（全色）。
    static var colors: [String] { row1 + row2 }
}
