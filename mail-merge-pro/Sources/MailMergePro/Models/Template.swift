//
//  Template.swift
//  MailMergePro
//
//  メールテンプレート（件名＋本文）のモデル。
//  Codable に準拠し、TemplateStore 経由で JSON としてローカル保存する。
//

import Foundation

/// 保存可能なメールテンプレート。
///
/// - `id` を安定キーにして一覧の選択・更新・削除を行う。
/// - 件名・本文には差し込みコード `{name}` などをそのまま含められる。
struct Template: Identifiable, Equatable, Codable {

    /// 一意な識別子。
    let id: UUID

    /// テンプレート名（一覧表示・リネーム対象）。
    var name: String

    /// 件名（差し込みコードを含められる）。
    var subject: String

    /// 本文（差し込みコードを含められる）。
    var body: String

    /// メンバーワイズ初期化子。
    /// - Parameter id: 既定で新規 UUID を採番。
    init(
        id: UUID = UUID(),
        name: String,
        subject: String = "",
        body: String = ""
    ) {
        self.id = id
        self.name = name
        self.subject = subject
        self.body = body
    }

    /// 新規作成時の空テンプレートを生成するファクトリ。
    /// - Parameter name: 既定名。
    static func makeEmpty(name: String = "新しいテンプレート") -> Template {
        Template(name: name, subject: "", body: "")
    }
}
