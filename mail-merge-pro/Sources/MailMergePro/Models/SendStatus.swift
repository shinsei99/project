//
//  SendStatus.swift
//  MailMergePro
//
//  宛先1件ごとの送信ステータスを表す列挙型。
//  - Models 層は UI（SwiftUI）に依存させない方針のため、
//    色やアイコンといった見た目の情報はここには持たせず、View 層のヘルパで解決する。
//  - 表示用の日本語ラベルだけはドメインの一部としてここで提供する。
//

import Foundation

/// 送信処理における各宛先の状態。
///
/// 状態遷移の想定:
///   `.pending`（未送信） → `.sending`（送信中） → `.sent`（成功） / `.failed`（失敗）
///   バリデーション不正などで送信対象外になった場合は `.skipped`。
enum SendStatus: String, Codable, CaseIterable, Equatable {
    /// 未送信（初期状態）
    case pending
    /// 送信中
    case sending
    /// 送信成功
    case sent
    /// 送信失敗（`Recipient.errorMessage` に理由が入る）
    case failed
    /// 送信対象外（メールアドレス不正などで意図的にスキップ）
    case skipped

    /// 画面表示用の日本語ラベル。
    var label: String {
        switch self {
        case .pending: return "未送信"
        case .sending: return "送信中"
        case .sent:    return "送信済み"
        case .failed:  return "失敗"
        case .skipped: return "対象外"
        }
    }

    /// 送信が完了して結果が確定した状態かどうか（成功・失敗・対象外）。
    /// 進捗計算や再送判定に利用する。
    var isFinished: Bool {
        switch self {
        case .sent, .failed, .skipped: return true
        case .pending, .sending:       return false
        }
    }
}
