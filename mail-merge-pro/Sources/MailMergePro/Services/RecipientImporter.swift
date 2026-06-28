//
//  RecipientImporter.swift
//  MailMergePro
//
//  宛先ファイルの読み込みを司る Service。
//  現状は CSV に対応（Excel(.xlsx) は将来 CoreXLSX 等の追加で拡張予定）。
//  - 1行目をヘッダとみなし、列名から「名前」「メール」列を柔軟に判定する。
//  - 名前・メール以外の列は Recipient.extraFields に格納し、差し込み拡張に備える。
//

import Foundation

/// 宛先読み込みのエラー。
enum RecipientImportError: LocalizedError {
    case unreadableFile(underlying: Error)
    case emptyFile
    case missingEmailColumn
    case unsupportedFileType(ext: String)

    var errorDescription: String? {
        switch self {
        case .unreadableFile(let e):
            return "ファイルを読み込めませんでした: \(e.localizedDescription)"
        case .emptyFile:
            return "ファイルが空、またはデータ行がありません。"
        case .missingEmailColumn:
            return "メールアドレスの列が見つかりませんでした。ヘッダに『email』『メール』『アドレス』等を含めてください。"
        case .unsupportedFileType(let ext):
            return "未対応のファイル形式です（.\(ext)）。現在は CSV に対応しています。"
        }
    }
}

/// 宛先インポートのインターフェース（テスト時に差し替え可能）。
protocol RecipientImporting {
    /// 指定ファイルから宛先一覧を読み込む。
    func importRecipients(from url: URL) throws -> [Recipient]
}

/// CSV を読み込む `RecipientImporting` 実装。
final class RecipientImporter: RecipientImporting {

    /// 名前列とみなすヘッダ候補（小文字・前後空白除去で比較）。
    private let nameHeaders: Set<String> = ["name", "名前", "氏名", "宛名", "お名前"]
    /// メール列とみなすヘッダ候補。
    private let emailHeaders: Set<String> = ["email", "e-mail", "mail", "メール", "メールアドレス", "アドレス"]

    func importRecipients(from url: URL) throws -> [Recipient] {
        let ext = url.pathExtension.lowercased()
        switch ext {
        case "csv", "txt":
            return try importCSV(from: url)
        case "xlsx", "xls":
            // 当面は未対応（CSV 先行方針）。将来ここに Excel パーサを追加する。
            throw RecipientImportError.unsupportedFileType(ext: ext)
        default:
            throw RecipientImportError.unsupportedFileType(ext: ext)
        }
    }

    // MARK: - CSV

    /// CSV ファイルを読み込んで Recipient 配列へ変換する。
    private func importCSV(from url: URL) throws -> [Recipient] {
        let text: String
        do {
            text = try readText(from: url)
        } catch {
            throw RecipientImportError.unreadableFile(underlying: error)
        }

        let rows = CSVParser.parse(text)
        guard rows.count >= 2 else {
            // ヘッダのみ、または空。
            throw RecipientImportError.emptyFile
        }

        // ヘッダ行から列の役割を決定する。
        let header = rows[0].map { $0.trimmingCharacters(in: .whitespaces) }
        let lowerHeader = header.map { $0.lowercased() }

        let emailIndex = lowerHeader.firstIndex(where: { emailHeaders.contains($0) })
        let nameIndex = lowerHeader.firstIndex(where: { nameHeaders.contains($0) })

        guard let emailIdx = emailIndex else {
            throw RecipientImportError.missingEmailColumn
        }

        // データ行を Recipient に変換。
        var recipients: [Recipient] = []
        for row in rows.dropFirst() {
            // 完全な空行はスキップ。
            if row.allSatisfy({ $0.trimmingCharacters(in: .whitespaces).isEmpty }) { continue }

            let email = value(in: row, at: emailIdx)
            let name = nameIndex.map { value(in: row, at: $0) } ?? ""

            // 名前・メール以外の列を extraFields に格納（差し込み拡張用）。
            var extra: [String: String] = [:]
            for (i, columnName) in header.enumerated() {
                if i == emailIdx { continue }
                if let n = nameIndex, i == n { continue }
                let key = columnName.lowercased()
                guard !key.isEmpty else { continue }
                extra[key] = value(in: row, at: i)
            }

            recipients.append(
                Recipient(name: name, email: email, extraFields: extra)
            )
        }

        guard !recipients.isEmpty else {
            throw RecipientImportError.emptyFile
        }
        return recipients
    }

    /// 文字コードを推測してテキスト読み込み（UTF-8 → Shift_JIS の順に試行）。
    /// 日本語 CSV は Shift_JIS で書き出されることが多いため両対応する。
    private func readText(from url: URL) throws -> String {
        let data = try Data(contentsOf: url)
        if let utf8 = String(data: data, encoding: .utf8) {
            return utf8
        }
        // Shift_JIS（CP932）フォールバック。
        let cfEnc = CFStringConvertEncodingToNSStringEncoding(CFStringEncoding(CFStringEncodings.dosJapanese.rawValue))
        if let sjis = String(data: data, encoding: String.Encoding(rawValue: cfEnc)) {
            return sjis
        }
        // 最後の手段として可能な限り読む。
        return String(decoding: data, as: UTF8.self)
    }

    /// 行から安全に値を取り出す（列数不足でも落ちないように）。
    private func value(in row: [String], at index: Int) -> String {
        guard index < row.count else { return "" }
        return row[index].trimmingCharacters(in: .whitespacesAndNewlines)
    }
}

/// RFC 4180 を概ね満たす最小の CSV パーサ。
/// ダブルクォートで囲まれたフィールド内のカンマ・改行・エスケープ済みクォート("")を正しく扱う。
enum CSVParser {

    /// CSV テキストを行×フィールドの二次元配列へ変換する。
    static func parse(_ text: String) -> [[String]] {
        var rows: [[String]] = []
        var field = ""
        var record: [String] = []
        var inQuotes = false

        // 改行コードを LF に正規化（CRLF / CR → LF）。
        let normalized = text
            .replacingOccurrences(of: "\r\n", with: "\n")
            .replacingOccurrences(of: "\r", with: "\n")

        let chars = Array(normalized)
        var i = 0
        while i < chars.count {
            let c = chars[i]
            if inQuotes {
                if c == "\"" {
                    // 次も " なら、エスケープされた1個の " 。
                    if i + 1 < chars.count, chars[i + 1] == "\"" {
                        field.append("\"")
                        i += 1
                    } else {
                        inQuotes = false
                    }
                } else {
                    field.append(c)
                }
            } else {
                switch c {
                case "\"":
                    inQuotes = true
                case ",":
                    record.append(field)
                    field = ""
                case "\n":
                    record.append(field)
                    rows.append(record)
                    record = []
                    field = ""
                default:
                    field.append(c)
                }
            }
            i += 1
        }
        // 最終フィールド／行を確定。
        record.append(field)
        rows.append(record)
        return rows
    }
}
