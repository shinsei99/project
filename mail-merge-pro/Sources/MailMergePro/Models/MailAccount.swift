//
//  MailAccount.swift
//  MailMergePro
//
//  Apple Mail に登録された送信アカウントを表すモデル。
//  送信元の選択（プルダウン）と、送信済みフォルダ仕分けの対象アカウント特定に使う。
//

import Foundation

/// Apple Mail のアカウント1件。
///
/// - `name` は Mail 上のアカウント名（例: "iCloud"）。`sent mailbox of account "name"` の参照に使う。
/// - `email` は送信元アドレス。outgoing message の `sender` に設定する。
struct MailAccount: Identifiable, Equatable, Hashable {

    /// 一意キー（アドレスを採用）。
    var id: String { email }

    /// Mail 上のアカウント名。
    let name: String

    /// 送信元メールアドレス。
    let email: String

    /// プルダウン等での表示用ラベル（例: "iCloud — me@icloud.com"）。
    var displayName: String {
        name.isEmpty ? email : "\(name) — \(email)"
    }
}
