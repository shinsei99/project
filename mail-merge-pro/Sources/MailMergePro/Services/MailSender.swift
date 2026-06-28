//
//  MailSender.swift
//  MailMergePro
//
//  Apple Mail（標準メールアプリ）を NSAppleScript 経由で制御して送信する Service。
//  SMTP 設定を不要にするための中核。1通分の送信だけを責務とし、
//  バッチ分割・待機・キャンセルは上位（ViewModel）が担う。
//
//  ※ App Store（Sandbox）公開時は、Apple Events 自動化の権限が必要:
//     - Info.plist: NSAppleEventsUsageDescription
//     - Entitlement: com.apple.security.automation.apple-events
//       (送信先として com.apple.mail を許可)
//

import Foundation

/// メール送信のインターフェース（テスト時はモックに差し替え可能）。
protocol MailSending {
    /// 1通送信する。失敗時は throw。
    /// - Parameters:
    ///   - subject: 差し込み置換済みの件名。
    ///   - body: 差し込み置換済みの本文。
    ///   - address: 宛先メールアドレス。
    ///   - senderEmail: 送信元アドレス。nil の場合は Mail の既定アカウントから送る。
    ///   - attachments: 添付ファイル。
    func send(subject: String, body: String, to address: String, senderEmail: String?, attachments: [Attachment]) throws
}

/// 送信時のエラー。
enum MailSenderError: LocalizedError {
    case attachmentMissing(fileName: String)

    var errorDescription: String? {
        switch self {
        case .attachmentMissing(let name):
            return "添付ファイルが見つかりません: \(name)"
        }
    }
}

/// NSAppleScript で Apple Mail を制御する実装。
final class AppleMailSender: MailSending {

    func send(subject: String, body: String, to address: String, senderEmail: String?, attachments: [Attachment]) throws {
        // 送信直前に添付ファイルの実在を再確認（ドロップ後の移動・削除に対応）。
        for attachment in attachments where !attachment.fileExists {
            throw MailSenderError.attachmentMissing(fileName: attachment.fileName)
        }

        let source = Self.buildScript(
            subject: subject,
            body: body,
            address: address,
            senderEmail: senderEmail,
            attachments: attachments
        )

        // AppleScript 実行（エラーは AppleScriptError として伝播）。
        try AppleScriptRunner.run(source)
    }

    // MARK: - AppleScript 生成

    /// 送信用 AppleScript ソースを組み立てる。
    /// 文字列は AppleScript リテラルとして安全にエスケープする。
    private static func buildScript(
        subject: String,
        body: String,
        address: String,
        senderEmail: String?,
        attachments: [Attachment]
    ) -> String {
        let subjectLit = AppleScriptRunner.quote(subject)
        let bodyLit = AppleScriptRunner.quote(body)
        let addressLit = AppleScriptRunner.quote(address)

        // 送信元アカウントが指定されていれば sender プロパティを足す。
        let senderProp: String
        if let senderEmail, !senderEmail.isEmpty {
            senderProp = ", sender:\(AppleScriptRunner.quote(senderEmail))"
        } else {
            senderProp = ""
        }

        // 添付ファイルを本文末尾に追加する行を生成。
        var attachmentLines = ""
        for attachment in attachments {
            let pathLit = AppleScriptRunner.quote(attachment.url.path)
            attachmentLines += """
                    make new attachment with properties {file name:(POSIX file \(pathLit))} at after the last paragraph of content

            """
        }

        // visible:false で UI を出さずに作成・送信する。
        return """
        tell application "Mail"
            set newMessage to make new outgoing message with properties {subject:\(subjectLit), content:\(bodyLit), visible:false\(senderProp)}
            tell newMessage
                make new to recipient at end of to recipients with properties {address:\(addressLit)}
        \(attachmentLines)        end tell
            send newMessage
        end tell
        """
    }
}
