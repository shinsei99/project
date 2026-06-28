//
//  MailAccountProvider.swift
//  MailMergePro
//
//  Apple Mail に登録された有効アカウントの一覧を取得する Service。
//  送信元プルダウンの選択肢を作るために使う。
//

import Foundation

/// アカウント取得のインターフェース（テスト時に差し替え可能）。
protocol MailAccountProviding {
    /// 有効なアカウント一覧を返す。取得できなければ空配列。
    func fetchAccounts() throws -> [MailAccount]
}

/// AppleScript で Mail のアカウントを取得する実装。
final class MailAccountProvider: MailAccountProviding {

    func fetchAccounts() throws -> [MailAccount] {
        // 有効アカウントごとに「名前<TAB>先頭アドレス」を改行区切りで返す。
        let source = """
        tell application "Mail"
            set outText to ""
            repeat with a in every account
                try
                    if enabled of a then
                        set addrs to email addresses of a
                        if (count of addrs) > 0 then
                            set outText to outText & (name of a) & "\\t" & (item 1 of addrs) & "\\n"
                        end if
                    end if
                end try
            end repeat
            return outText
        end tell
        """

        let raw = try AppleScriptRunner.run(source)
        return parse(raw)
    }

    /// "名前\tアドレス\n..." を MailAccount 配列へ変換する。
    private func parse(_ raw: String) -> [MailAccount] {
        var accounts: [MailAccount] = []
        for line in raw.split(separator: "\n") {
            let parts = line.components(separatedBy: "\t")
            guard parts.count == 2 else { continue }
            let name = parts[0].trimmingCharacters(in: .whitespaces)
            let email = parts[1].trimmingCharacters(in: .whitespaces)
            guard !email.isEmpty else { continue }
            // 同一アドレスの重複は除外。
            if accounts.contains(where: { $0.email == email }) { continue }
            accounts.append(MailAccount(name: name, email: email))
        }
        return accounts
    }
}
