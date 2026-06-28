//
//  SendResult.swift
//  MailMergePro
//
//  本番送信の結果を集計・エクスポートするためのモデル群。
//  - SendResultRow: 宛先1件分の結果（CSV の1行に対応）。
//  - SendSummary:   成功・失敗件数などの集計＋失敗一覧。
//

import Foundation

/// 宛先1件分の送信結果（結果ログ CSV の1行に対応）。
struct SendResultRow: Identifiable, Equatable {
    let id: UUID
    /// 宛先名。
    let name: String
    /// 宛先アドレス。
    let email: String
    /// 最終ステータス（sent / failed / skipped）。
    let status: SendStatus
    /// 失敗・対象外の理由。成功時は nil。
    let errorMessage: String?

    /// Recipient から結果行を生成する。
    init(from recipient: Recipient) {
        self.id = recipient.id
        self.name = recipient.name
        self.email = recipient.email
        self.status = recipient.status
        self.errorMessage = recipient.errorMessage
    }
}

/// 送信完了後の集計結果。完了画面の表示と CSV 出力に使う。
struct SendSummary: Equatable {

    /// 全宛先の結果行。
    let rows: [SendResultRow]

    init(recipients: [Recipient]) {
        self.rows = recipients.map(SendResultRow.init(from:))
    }

    /// 成功件数。
    var successCount: Int { rows.filter { $0.status == .sent }.count }

    /// 失敗件数。
    var failureCount: Int { rows.filter { $0.status == .failed }.count }

    /// 対象外（スキップ）件数。
    var skippedCount: Int { rows.filter { $0.status == .skipped }.count }

    /// 総件数。
    var totalCount: Int { rows.count }

    /// 失敗・対象外の宛先のみ（完了画面の「失敗一覧」表示用）。
    var failedRows: [SendResultRow] {
        rows.filter { $0.status == .failed || $0.status == .skipped }
    }
}
