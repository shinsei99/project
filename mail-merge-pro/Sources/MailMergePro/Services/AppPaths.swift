//
//  AppPaths.swift
//  MailMergePro
//
//  アプリ専用の保存先ディレクトリ（Application Support）を解決するユーティリティ。
//  Sandbox 有効時/無効時のどちらでも `FileManager` が適切なコンテナを返すため、
//  パス解決をこの1か所に集約しておくことで将来の権限管理を簡潔に保つ。
//

import Foundation

/// アプリのローカル保存先パスを提供する名前空間。
enum AppPaths {

    /// アプリ識別用のフォルダ名（Application Support 配下に作成）。
    private static let folderName = "MailMergePro"

    /// `~/Library/Application Support/MailMergePro/` を返す。
    /// ディレクトリが無ければ作成する。
    /// - Throws: ディレクトリ作成に失敗した場合。
    /// - Returns: 保存先ディレクトリの URL。
    static func supportDirectory() throws -> URL {
        let base = try FileManager.default.url(
            for: .applicationSupportDirectory,
            in: .userDomainMask,
            appropriateFor: nil,
            create: true
        )
        let dir = base.appendingPathComponent(folderName, isDirectory: true)
        if !FileManager.default.fileExists(atPath: dir.path) {
            try FileManager.default.createDirectory(
                at: dir,
                withIntermediateDirectories: true
            )
        }
        return dir
    }

    /// 保存先ディレクトリ配下の任意ファイル URL を返す。
    /// - Parameter fileName: ファイル名（例: "templates.json"）。
    static func fileURL(_ fileName: String) throws -> URL {
        try supportDirectory().appendingPathComponent(fileName, isDirectory: false)
    }
}
