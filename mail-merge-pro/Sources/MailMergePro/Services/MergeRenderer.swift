//
//  MergeRenderer.swift
//  MailMergePro
//
//  差し込み（マージ）処理。テンプレート文字列中の `{key}` を
//  受信者の対応値で置換する。プレビュー表示と実送信の両方で同じ実装を使うことで、
//  「プレビューと実際の送信内容が食い違う」事故を防ぐ。
//

import Foundation

/// 差し込みコードを置換するレンダラ。
enum MergeRenderer {

    /// `{name}` のような差し込みコードを検出する正規表現。
    /// キーは英数字とアンダースコアのみ許可（将来 `{contract_no}` 等に対応）。
    private static let pattern = try! NSRegularExpression(pattern: #"\{([A-Za-z0-9_]+)\}"#)

    /// テンプレート文字列を受信者データで差し込み置換する。
    /// - Parameters:
    ///   - template: `{name}` 等を含む元文字列（件名 or 本文）。
    ///   - recipient: 置換に使う受信者。
    /// - Returns: 置換後の文字列。対応値が無いコードは元のまま残す（消さない）。
    static func render(_ template: String, with recipient: Recipient) -> String {
        let nsString = template as NSString
        let fullRange = NSRange(location: 0, length: nsString.length)
        var result = template

        // 後方のマッチから置換していくことで、置換による文字数ズレで
        // 前方のレンジが無効化されるのを防ぐ。
        let matches = pattern.matches(in: template, range: fullRange).reversed()
        for match in matches {
            guard match.numberOfRanges == 2 else { continue }
            let keyRange = match.range(at: 1)
            let key = nsString.substring(with: keyRange)

            // 対応値が無ければ置換しない（コードをそのまま残す）。
            guard let value = recipient.mergeValue(forKey: key) else { continue }

            let wholeRange = match.range(at: 0)
            if let swiftRange = Range(wholeRange, in: result) {
                result.replaceSubrange(swiftRange, with: value)
            }
        }
        return result
    }
}
