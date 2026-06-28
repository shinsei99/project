//
//  ResultExporter.swift
//  MailMergePro
//
//  送信完了後の結果ログを CSV としてエクスポートする Service。
//  保存先 URL の決定（NSSavePanel）は View 側に任せ、ここは
//  「結果 → CSV 文字列化 → 書き出し」の責務に徹する。
//

import Foundation

/// 結果エクスポートのエラー。
enum ResultExportError: LocalizedError {
    case writeFailed(underlying: Error)

    var errorDescription: String? {
        switch self {
        case .writeFailed(let e):
            return "結果ログの書き出しに失敗しました: \(e.localizedDescription)"
        }
    }
}

/// 送信結果を CSV に出力するサービス。
enum ResultExporter {

    /// 列ヘッダ。
    private static let header = ["名前", "メールアドレス", "ステータス", "エラー内容"]

    /// 送信結果から CSV 文字列を生成する。
    /// - Parameter summary: 集計結果。
    /// - Returns: BOM 付き UTF-8 を想定した CSV 本文（Excel での文字化け防止用 BOM は書き出し時に付与）。
    static func csvString(from summary: SendSummary) -> String {
        var lines: [String] = []
        lines.append(header.map(escapeField).joined(separator: ","))

        for row in summary.rows {
            let fields = [
                row.name,
                row.email,
                row.status.label,
                row.errorMessage ?? ""
            ]
            lines.append(fields.map(escapeField).joined(separator: ","))
        }
        return lines.joined(separator: "\r\n")
    }

    /// 結果を指定 URL に CSV ファイルとして書き出す。
    /// Excel で開いた際の日本語文字化けを防ぐため UTF-8 BOM を付与する。
    /// - Parameters:
    ///   - summary: 集計結果。
    ///   - url: 保存先（拡張子 .csv を想定）。
    static func export(_ summary: SendSummary, to url: URL) throws {
        let csv = csvString(from: summary)
        let bom = Data([0xEF, 0xBB, 0xBF])
        var data = bom
        data.append(Data(csv.utf8))
        do {
            try data.write(to: url, options: [.atomic])
        } catch {
            throw ResultExportError.writeFailed(underlying: error)
        }
    }

    /// CSV フィールドのエスケープ（カンマ・引用符・改行を含む場合は "" で囲む）。
    private static func escapeField(_ field: String) -> String {
        if field.contains(",") || field.contains("\"") || field.contains("\n") || field.contains("\r") {
            let escaped = field.replacingOccurrences(of: "\"", with: "\"\"")
            return "\"\(escaped)\""
        }
        return field
    }
}
