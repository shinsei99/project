//
//  SendStatusUI.swift
//  MailMergePro
//
//  SendStatus（Models 層・UI非依存）に、View 層でだけ使う見た目情報を付与する拡張。
//  色やアイコンをモデルに持たせない MVVM 方針を保つため、ここに分離している。
//

import SwiftUI

extension SendStatus {

    /// ステータスを表す色。
    var color: Color {
        switch self {
        case .pending: return .secondary
        case .sending: return .blue
        case .sent:    return .green
        case .failed:  return .red
        case .skipped: return .orange
        }
    }

    /// ステータスを表す SF Symbol 名。
    var systemImage: String {
        switch self {
        case .pending: return "circle"
        case .sending: return "paperplane"
        case .sent:    return "checkmark.circle.fill"
        case .failed:  return "xmark.octagon.fill"
        case .skipped: return "minus.circle"
        }
    }
}
