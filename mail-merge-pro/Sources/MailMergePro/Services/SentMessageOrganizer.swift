//
//  SentMessageOrganizer.swift
//  MailMergePro
//
//  一斉送信したメールを、通常の「送信済み(Sent)」から専用フォルダへ隔離する Service。
//  仕様: どのアカウントから送っても、共通の専用ローカルメールボックスへまとめる。
//
//  ※ Apple Mail の制約により、送信メッセージにカスタムヘッダを付けられないため、
//    「指定アカウントの Sent から、バッチ開始時刻以降に送信されたメール」を対象に移動する。
//    そのため、送信実行中に同じアカウントから手動送信したメールも巻き込む可能性がある点に注意
//    （上位でユーザーに告知する）。
//

import Foundation

/// 送信済みメールの仕分けサービス。
enum SentMessageOrganizer {

    /// 専用フォルダ（ローカル "このMac内"）の名前。
    static let folderName = "Mail Merge Pro 送信済み"

    /// 指定アカウントの Sent から、一定時間内に送信されたメールを専用フォルダへ移動する。
    /// - Parameters:
    ///   - accountName: 送信に使った Mail アカウント名。
    ///   - sinceSeconds: 「現在からこの秒数以内に送信されたメール」を対象にする（バッチ所要時間＋バッファ）。
    ///   - folder: 移動先フォルダ名（既定は専用フォルダ）。
    static func organize(accountName: String, sinceSeconds: Int, folder: String = folderName) throws {
        let acctLit = AppleScriptRunner.quote(accountName)
        let folderLit = AppleScriptRunner.quote(folder)
        let seconds = max(60, sinceSeconds) // 最低60秒は遡る

        let source = """
        tell application "Mail"
            -- 専用フォルダ（ローカルメールボックス）が無ければ作成。
            if not (exists mailbox \(folderLit)) then
                make new mailbox with properties {name:\(folderLit)}
            end if
            set destBox to mailbox \(folderLit)

            -- 対象アカウントの送信済みメールボックス。
            set theAccount to account \(acctLit)
            set acctSent to sent mailbox of theAccount

            -- バッチ開始時刻以降に送信されたメールだけを移動。
            set cutoff to (current date) - \(seconds)
            set toMove to (every message of acctSent whose date sent ≥ cutoff)
            repeat with m in toMove
                move m to destBox
            end repeat
        end tell
        """

        try AppleScriptRunner.run(source)
    }
}
