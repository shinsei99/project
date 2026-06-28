//
//  Attachment.swift
//  MailMergePro
//
//  添付ファイル1件を表すモデル。
//  実体はファイル URL で保持し、送信直前に存在チェックを行う
//  （ドロップ後に元ファイルが移動・削除される「添付ファイル紛失」に対応するため）。
//

import Foundation

/// 添付ファイル。
///
/// 設計意図:
///  - URL を保持しておき、送信時に `fileExists` で実在を再確認する。
///  - Sandbox（App Store 公開）を想定し、将来はセキュリティスコープ付きブックマークへ
///    置き換えられるよう、URL アクセスはこのモデル経由に集約しておく。
struct Attachment: Identifiable, Equatable {

    /// 一意な識別子。
    let id: UUID

    /// ファイルの場所。
    let url: URL

    /// メンバーワイズ初期化子。
    init(id: UUID = UUID(), url: URL) {
        self.id = id
        self.url = url
    }

    /// 表示用ファイル名。
    var fileName: String {
        url.lastPathComponent
    }

    /// ファイルが現在も実在するか（送信前の「添付ファイル紛失」検知用）。
    var fileExists: Bool {
        FileManager.default.fileExists(atPath: url.path)
    }

    /// 人間が読めるファイルサイズ表記（例: "1.2 MB"）。実在しなければ "—"。
    var humanReadableSize: String {
        guard
            let values = try? url.resourceValues(forKeys: [.fileSizeKey]),
            let bytes = values.fileSize
        else { return "—" }
        return ByteCountFormatter.string(fromByteCount: Int64(bytes), countStyle: .file)
    }
}
