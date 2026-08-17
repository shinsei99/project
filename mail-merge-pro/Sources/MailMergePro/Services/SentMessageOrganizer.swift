//
//  SentMessageOrganizer.swift
//  MailMergePro
//
//  一斉送信後の Mail の後始末を行う Service。
//  ① 送信控え（Sent）を残さない：送信に使ったアカウントの「送信済み」から
//     バッチ時間内のメールをゴミ箱へ移す。
//  ② 下書きの残骸を残さない：`visible:false` での AppleScript 送信では、
//     送信後も「下書き(Drafts)」にコピーが残ることがあるため、これも掃除する。
//  送信の記録が必要な場合は、アプリの結果CSV（ResultExporter）を利用する。
//
//  ※ Apple Mail の制約により、送信メッセージにカスタムヘッダを付けられないため、
//    「バッチ開始時刻以降のメール」を時間で対象にする。送信実行中に手動作成した
//    下書き等を巻き込む可能性があるが、いずれも削除＝ゴミ箱への移動なので復元できる。
//
//  ※ App Store（Sandbox）公開時は、Apple Events 自動化の権限が必要:
//     - Info.plist: NSAppleEventsUsageDescription
//     - Entitlement: com.apple.security.automation.apple-events（com.apple.mail 宛）
//

import Foundation

/// 送信後の後始末サービス。
enum SentMessageOrganizer {

    /// 送信済み控え・下書きの残骸を、一定時間内のぶんだけゴミ箱へ移す。
    /// - Parameters:
    ///   - accountName: 送信に使った Mail アカウント名。
    ///   - sinceSeconds: 「現在からこの秒数以内」を対象にする（バッチ所要時間＋バッファ）。
    static func purgeAfterSend(accountName: String, sinceSeconds: Int) throws {
        let acctLit = AppleScriptRunner.quote(accountName)
        let seconds = max(60, sinceSeconds) // 最低60秒は遡る

        // 送信済み・下書きの取り方はアカウント種別で差があるため、複数候補を try で試し、
        // どれも失敗しても例外を投げずに完了する（後始末は best-effort。送信には影響させない）。
        let source = """
        tell application "Mail"
            set cutoffDate to (current date) - \(seconds)
            set boxesToClean to {}

            try
                set theAccount to account \(acctLit)
                -- アカウントの「送信済み」「下書き」メールボックス。
                try
                    set end of boxesToClean to (sent mailbox of theAccount)
                end try
                try
                    set end of boxesToClean to (drafts mailbox of theAccount)
                end try
                -- 名前に Sent / 送信済 / Draft / 下書き を含むメールボックス。
                try
                    repeat with mb in (every mailbox of theAccount)
                        set mbName to (name of mb) as string
                        if mbName contains "Sent" or mbName contains "送信済" or mbName contains "Draft" or mbName contains "下書" then
                            set end of boxesToClean to mb
                        end if
                    end repeat
                end try
            end try

            -- アプリ全体（統合）の送信済み・下書き。残骸の下書きはここに出ることが多い。
            try
                set end of boxesToClean to sent mailbox
            end try
            try
                set end of boxesToClean to drafts mailbox
            end try

            -- 各メールボックスから、バッチ開始以降のメールをゴミ箱へ。
            repeat with theBox in boxesToClean
                try
                    set toPurge to (every message of theBox whose date sent ≥ cutoffDate)
                    -- インデックスずれを避けるため末尾から削除（delete＝ゴミ箱へ移動）。
                    repeat with i from (count of toPurge) to 1 by -1
                        try
                            delete (item i of toPurge)
                        end try
                    end repeat
                end try
            end repeat
        end tell
        """

        try AppleScriptRunner.run(source)
    }
}
