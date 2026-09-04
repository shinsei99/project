import Foundation

/// 自社サーバー（KeyLine など）との連携。
///
/// ★仕様は `keytag/server-api/API.md` にある公開仕様。参照実装も同じフォルダに置いてある。
///   接続先は利用者が設定画面で入れる方式なので、**誰でも自分のサーバーで使える**。
/// ★サーバーに繋がらないときは、呼び出し側が端末内の台帳に切り替える。現場を止めないため。
struct KeyTagAPI {
    var server: String
    var token: String

    struct Failure: LocalizedError {
        let message: String
        var errorDescription: String? { message }
    }

    // MARK: - 応答の形

    struct PairResponse: Decodable {
        var ok: Bool
        var token: String?
        var organization: String?
        var error: String?
    }

    struct PingResponse: Decodable {
        var ok: Bool
        var organization: String?
        var user: String?
        var error: String?
    }

    struct RegisterResponse: Decodable {
        var ok: Bool
        var url: String?
        var error: String?
    }

    struct AssetResponse: Decodable {
        var ok: Bool
        var found: Bool?
        var asset: Asset?
        var borrowers: [BorrowerOption]?
        var dues: [DueOption]?
        var error: String?
    }

    struct ActionResponse: Decodable {
        var ok: Bool
        var asset: Asset?
        var error: String?
    }

    // MARK: - 呼び出し

    /// ペアリングだけは認証不要。6桁コードをトークンに引き換える。
    static func pair(server: String, code: String) async throws -> PairResponse {
        let r: PairResponse = try await request(server: server, token: "", path: "/api/pair",
                                                body: ["code": code])
        guard r.ok else { throw Failure(message: r.error ?? "連携できませんでした") }
        return r
    }

    func ping() async throws -> PingResponse {
        let r: PingResponse = try await Self.request(server: server, token: token, path: "/api/ping", body: nil)
        guard r.ok else { throw Failure(message: r.error ?? "接続できません") }
        return r
    }

    /// 鍵を1件登録して、タグに書く URL を受け取る。
    func register(property: String, name: String, boxPosition: String,
                  numbers: [String], quantities: [Int]) async throws -> String? {
        let body: [String: Any] = [
            "property_name": property, "name": name, "box_position": boxPosition,
            "item_number": numbers, "item_qty": quantities.map(String.init),
        ]
        let r: RegisterResponse = try await Self.request(server: server, token: token,
                                                         path: "/api/register", body: body)
        guard r.ok else { throw Failure(message: r.error ?? "登録できませんでした") }
        return r.url
    }

    func asset(token tagToken: String) async throws -> AssetResponse {
        let encoded = tagToken.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? tagToken
        let r: AssetResponse = try await Self.request(server: server, token: token,
                                                      path: "/api/asset?token=" + encoded, body: nil)
        guard r.ok else { throw Failure(message: r.error ?? "取得できませんでした") }
        return r
    }

    func checkout(tagToken: String, borrowerID: String, newName: String, newKind: String,
                  newCompany: String, newPhone: String, dueAt: String) async throws -> Asset? {
        let body: [String: Any] = [
            "token": tagToken, "borrower_id": borrowerID, "new_name": newName,
            "new_kind": newKind, "new_company": newCompany, "new_phone": newPhone,
            "due_at": dueAt,
        ]
        let r: ActionResponse = try await Self.request(server: server, token: token,
                                                       path: "/api/checkout", body: body)
        guard r.ok else { throw Failure(message: r.error ?? "貸出できませんでした") }
        return r.asset
    }

    func returnKey(tagToken: String) async throws -> Asset? {
        let r: ActionResponse = try await Self.request(server: server, token: token,
                                                       path: "/api/return", body: ["token": tagToken])
        guard r.ok else { throw Failure(message: r.error ?? "返却できませんでした") }
        return r.asset
    }

    // MARK: - 土台

    private static func request<T: Decodable>(server: String, token: String, path: String,
                                              body: [String: Any]?) async throws -> T {
        let base = server.trimmingCharacters(in: .whitespaces)
            .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        guard let url = URL(string: base + path) else {
            throw Failure(message: "サーバーのURLが正しくありません")
        }
        var req = URLRequest(url: url)
        req.timeoutInterval = 12
        if let body {
            req.httpMethod = "POST"
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try JSONSerialization.data(withJSONObject: body)
        }
        if !token.isEmpty {
            req.setValue("Bearer " + token, forHTTPHeaderField: "Authorization")
        }
        let (data, _) = try await URLSession.shared.data(for: req)
        do {
            return try JSONDecoder().decode(T.self, from: data)
        } catch {
            throw Failure(message: "サーバーの応答を読めませんでした")
        }
    }
}
