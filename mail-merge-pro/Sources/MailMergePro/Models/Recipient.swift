//
//  Recipient.swift
//  MailMergePro
//
//  1件の宛先データを表すモデル。
//  将来の「複数差し込み項目」拡張に備え、名前・アドレス以外の任意項目を
//  辞書（extraFields）で柔軟に保持できる設計にしている。
//

import Foundation

/// 宛先（受信者）1件分のデータ。
///
/// 設計意図:
///  - `extraFields` に CSV/Excel の任意列（会社名・契約番号など）を格納し、
///    差し込みコード `{company}` のような将来拡張をモデル変更なしで吸収する。
///  - 送信処理中に `status` / `errorMessage` を書き換えるため struct を `var` で更新する
///    （ViewModel 側で配列要素を差し替える）。
struct Recipient: Identifiable, Equatable, Codable {

    /// 一意な識別子。読み込みごとに採番する。
    let id: UUID

    /// 宛先の表示名。差し込みコード `{name}` の置換に使う。
    var name: String

    /// メールアドレス。送信先。
    var email: String

    /// 送信ステータス（初期値は未送信）。
    var status: SendStatus

    /// 送信失敗時のエラーメッセージ。成功時は nil。
    var errorMessage: String?

    /// 名前・アドレス以外の差し込み項目（列名 → 値）。
    /// 例: ["company": "株式会社サンプル", "contract_no": "A-1024"]
    var extraFields: [String: String]

    /// メンバーワイズ初期化子。
    /// - Parameters:
    ///   - id: 既定で新規 UUID を採番。
    ///   - extraFields: 追加の差し込み項目。既定は空。
    init(
        id: UUID = UUID(),
        name: String,
        email: String,
        status: SendStatus = .pending,
        errorMessage: String? = nil,
        extraFields: [String: String] = [:]
    ) {
        self.id = id
        self.name = name
        self.email = email
        self.status = status
        self.errorMessage = errorMessage
        self.extraFields = extraFields
    }

    // MARK: - 差し込み（マージ）

    /// 差し込みコードのキー（小文字）→ 実値 を返す統一アクセサ。
    /// `name` と `email` は予約キーとして優先的に解決し、
    /// それ以外は `extraFields` から探す。
    /// - Parameter key: 差し込みコードのキー（例: "name"）。
    /// - Returns: 対応する値。存在しなければ nil。
    func mergeValue(forKey key: String) -> String? {
        switch key.lowercased() {
        case "name":  return name
        case "email": return email
        default:      return extraFields[key.lowercased()]
        }
    }

    // MARK: - バリデーション

    /// メールアドレスが形式的に妥当かどうかの簡易判定。
    /// 送信前のスキップ判定（`.skipped`）に利用する。
    var hasValidEmail: Bool {
        Recipient.isValidEmail(email)
    }

    /// RFC を厳密には満たさないが実用上十分な簡易メールアドレス検証。
    /// - Parameter address: 検証対象。
    /// - Returns: 妥当そうなら true。
    static func isValidEmail(_ address: String) -> Bool {
        let trimmed = address.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return false }
        // ローカル部@ドメイン部.TLD の最小限パターン。
        let pattern = #"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$"#
        return trimmed.range(of: pattern, options: [.regularExpression, .caseInsensitive]) != nil
    }
}
