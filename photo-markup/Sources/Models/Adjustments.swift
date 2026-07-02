import Foundation

/// 画像全体への非破壊補正パラメータ。値はユーザー向けスライダー値。
/// 明るさ/コントラスト/鮮やかさ/飽和/鮮明度: -100...100（0が無補正）
/// シャープ/ノイズ除去: 0...100（0が無補正）
struct Adjustments: Equatable {
    var brightness: Double = 0     // 明るさ
    var contrast: Double = 0       // コントラスト
    var vibrance: Double = 0       // 鮮やかさ（自然な彩度・CIVibrance）
    var saturation: Double = 0     // 飽和（彩度・CIColorControls）
    var clarity: Double = 0        // 鮮明度（局所コントラスト・UnsharpMask大半径）
    var sharpness: Double = 0      // シャープ（CISharpenLuminance）
    var noiseReduction: Double = 0 // ノイズ除去（CINoiseReduction）

    static let identity = Adjustments()
    var isIdentity: Bool { self == .identity }

    /// 各補正項目の定義（UI生成に使う）。
    enum Field: String, CaseIterable, Identifiable {
        case brightness, contrast, vibrance, saturation, clarity, sharpness, noiseReduction
        var id: String { rawValue }

        var label: String {
            switch self {
            case .brightness: return "明るさ"
            case .contrast: return "コントラスト"
            case .vibrance: return "鮮やかさ"
            case .saturation: return "飽和"
            case .clarity: return "鮮明度"
            case .sharpness: return "シャープ"
            case .noiseReduction: return "ノイズ除去"
            }
        }
        var systemImage: String {
            switch self {
            case .brightness: return "sun.max"
            case .contrast: return "circle.lefthalf.filled"
            case .vibrance: return "leaf"
            case .saturation: return "drop"
            case .clarity: return "triangle"
            case .sharpness: return "sparkles"
            case .noiseReduction: return "wand.and.stars"
            }
        }
        /// スライダーの範囲。片側系(0..100)か両側系(-100..100)か。
        var range: ClosedRange<Double> {
            switch self {
            case .sharpness, .noiseReduction: return 0...100
            default: return -100...100
            }
        }
    }

    subscript(_ field: Field) -> Double {
        get {
            switch field {
            case .brightness: return brightness
            case .contrast: return contrast
            case .vibrance: return vibrance
            case .saturation: return saturation
            case .clarity: return clarity
            case .sharpness: return sharpness
            case .noiseReduction: return noiseReduction
            }
        }
        set {
            switch field {
            case .brightness: brightness = newValue
            case .contrast: contrast = newValue
            case .vibrance: vibrance = newValue
            case .saturation: saturation = newValue
            case .clarity: clarity = newValue
            case .sharpness: sharpness = newValue
            case .noiseReduction: noiseReduction = newValue
            }
        }
    }
}
