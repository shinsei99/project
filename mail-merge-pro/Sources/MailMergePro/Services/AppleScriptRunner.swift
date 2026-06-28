//
//  AppleScriptRunner.swift
//  MailMergePro
//
//  NSAppleScript 実行の共通ラッパ。
//  文字列リテラルのエスケープと、実行・エラー伝播を1か所に集約する。
//  （MailSender / MailAccountProvider / SentMessageOrganizer から共用）
//

import Foundation

/// AppleScript 実行に関するエラー。
enum AppleScriptError: LocalizedError {
    case compileFailed
    case executionFailed(message: String)

    var errorDescription: String? {
        switch self {
        case .compileFailed:
            return "スクリプトの生成に失敗しました。"
        case .executionFailed(let message):
            return "Apple Mail の操作に失敗しました: \(message)"
        }
    }
}

/// AppleScript を組み立て・実行するためのユーティリティ。
enum AppleScriptRunner {

    /// スクリプトを実行し、戻り値を文字列として返す（戻り値が無ければ空文字）。
    /// - Parameter source: AppleScript ソース。
    /// - Throws: コンパイル/実行失敗時。
    @discardableResult
    static func run(_ source: String) throws -> String {
        guard let script = NSAppleScript(source: source) else {
            throw AppleScriptError.compileFailed
        }
        var errorInfo: NSDictionary?
        let descriptor = script.executeAndReturnError(&errorInfo)
        if let errorInfo {
            let message = (errorInfo[NSAppleScript.errorMessage] as? String) ?? "不明なエラー"
            throw AppleScriptError.executionFailed(message: message)
        }
        return descriptor.stringValue ?? ""
    }

    /// Swift 文字列を AppleScript の二重引用符リテラルへ変換する。
    /// バックスラッシュ・引用符・改行・タブをエスケープし、`"..."` 形式で返す。
    static func quote(_ string: String) -> String {
        var s = string
        s = s.replacingOccurrences(of: "\\", with: "\\\\")
        s = s.replacingOccurrences(of: "\"", with: "\\\"")
        s = s.replacingOccurrences(of: "\n", with: "\\n")
        s = s.replacingOccurrences(of: "\r", with: "\\r")
        s = s.replacingOccurrences(of: "\t", with: "\\t")
        return "\"\(s)\""
    }
}
