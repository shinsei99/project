//
//  TemplateStore.swift
//  MailMergePro
//
//  テンプレートの永続化を司る Service クラス。
//  - 保存形式: JSON 1ファイル（templates.json）に全テンプレートを配列で保存。
//  - 役割を「読み込み・保存」に限定し、編集ロジック（追加/削除/リネーム）は
//    ViewModel 側に置く。ここはあくまで I/O の責務に徹する。
//

import Foundation

/// テンプレート永続化サービスが投げるエラー。
enum TemplateStoreError: LocalizedError {
    case loadFailed(underlying: Error)
    case saveFailed(underlying: Error)

    var errorDescription: String? {
        switch self {
        case .loadFailed(let e):
            return "テンプレートの読み込みに失敗しました: \(e.localizedDescription)"
        case .saveFailed(let e):
            return "テンプレートの保存に失敗しました: \(e.localizedDescription)"
        }
    }
}

/// テンプレートを JSON ファイルへ読み書きする永続化サービス。
///
/// テスト容易性のため `protocol` を切っておき、本番実装と差し替え可能にする。
protocol TemplateStoring {
    /// 保存済みテンプレートをすべて読み込む。ファイルが無ければ空配列。
    func loadAll() throws -> [Template]
    /// テンプレート配列をまるごと保存する（全置換）。
    func saveAll(_ templates: [Template]) throws
}

/// `TemplateStoring` のファイルベース実装。
final class TemplateStore: TemplateStoring {

    /// 保存ファイル名。
    private let fileName: String

    /// 読みやすい JSON を出力するためのエンコーダ。
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder

    /// - Parameter fileName: 保存ファイル名（既定 "templates.json"）。
    init(fileName: String = "templates.json") {
        self.fileName = fileName

        let enc = JSONEncoder()
        enc.outputFormatting = [.prettyPrinted, .sortedKeys]
        self.encoder = enc
        self.decoder = JSONDecoder()
    }

    /// 保存済みテンプレートを読み込む。
    /// - Returns: テンプレート配列。ファイル未作成時は空配列を返す（初回起動を正常系として扱う）。
    func loadAll() throws -> [Template] {
        do {
            let url = try AppPaths.fileURL(fileName)
            // 初回起動などでファイルが無い場合は空配列（エラーにしない）。
            guard FileManager.default.fileExists(atPath: url.path) else {
                return []
            }
            let data = try Data(contentsOf: url)
            return try decoder.decode([Template].self, from: data)
        } catch {
            throw TemplateStoreError.loadFailed(underlying: error)
        }
    }

    /// テンプレート配列を JSON に書き出す（アトミック保存）。
    /// - Parameter templates: 保存する全テンプレート。
    func saveAll(_ templates: [Template]) throws {
        do {
            let url = try AppPaths.fileURL(fileName)
            let data = try encoder.encode(templates)
            // .atomic で書き込み途中のクラッシュによるファイル破損を防ぐ。
            try data.write(to: url, options: [.atomic])
        } catch {
            throw TemplateStoreError.saveFailed(underlying: error)
        }
    }
}
