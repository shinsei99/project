import Foundation

// 台帳の1件。
//
// ★uid（タグ固有の番号）で鍵を特定する。タグに書いた文字は後から変わり得るが uid は変わらない。
//   サーバーが無くても「かざした鍵がどれか」が確実に決まる。
//   Excel から読み込んだだけの鍵は、まだタグに書いていないので uid が空になる。
struct KeyRecord: Codable, Identifiable, Equatable {
    var id: String = "k" + String(UUID().uuidString.prefix(10))
    var uid: String = ""
    var at: Date = Date()
    var property: String = ""
    var name: String = ""
    var numbers: String = ""
    var boxCode: String = ""
    var boxPosition: String = ""
    var url: String = ""
    var written: String = ""
    var bytes: Int = 0
    var status: Status = .inStock
    var borrower: Borrower?
    var since: Date?
    var due: Date?
    var history: [LendHistory] = []

    enum Status: String, Codable { case inStock = "in", out = "out" }

    var label: String { property.isEmpty ? name : "\(property) / \(name)" }
    var boxLabel: String { NDEF.boxLabel(boxCode, boxPosition) }
    var isOverdue: Bool {
        guard status == .out, let due else { return false }
        return due < Date()
    }
    /// 鍵番号の文字列から合計本数を数える（`10001 / 10003 ×3` → 4）。
    var totalKeys: Int {
        numbers.components(separatedBy: " / ").filter { !$0.isEmpty }.reduce(0) { sum, s in
            if let r = s.range(of: #"×\s*(\d+)"#, options: .regularExpression),
               let n = Int(s[r].dropFirst().trimmingCharacters(in: .whitespaces)) { return sum + n }
            return sum + 1
        }
    }
}

struct Borrower: Codable, Equatable {
    var name: String = ""
    var company: String = ""
    var kind: String = ""
    var phone: String = ""
}

struct LendHistory: Codable, Equatable {
    var name: String = ""
    var company: String = ""
    var kind: String = ""
    var at: Date?
    var returned: Date?
    var due: Date?
}

// MARK: - 画面が使う形（端末内・サーバーで同じ形にそろえる）

/// 鍵1件の状態。サーバーの `/api/asset` が返す `asset` と同じ形。
/// 端末内の台帳から作るときは `Store.asset(for:)` が組み立てる。
struct Asset: Codable, Equatable {
    var propertyName: String = ""
    var name: String = ""
    var label: String = ""
    var itemNumbers: String = ""
    var totalKeys: Int = 0
    var box: String = ""
    var boxName: String = ""
    var status: String = "in_stock"          // in_stock | checked_out
    var statusLabel: String = "保管中"
    var borrower: Borrower?
    var checkedOutAt: String = ""            // 整形済みの文字列（ISOではない）
    var dueAt: String = ""
    var elapsed: String = ""
    var isOverdue: Bool = false

    enum CodingKeys: String, CodingKey {
        case propertyName = "property_name", name, label
        case itemNumbers = "item_numbers", totalKeys = "total_keys"
        case box, boxName = "box_name", status, statusLabel = "status_label"
        case borrower, checkedOutAt = "checked_out_at", dueAt = "due_at"
        case elapsed, isOverdue = "is_overdue"
    }

    var isOut: Bool { status == "checked_out" }
    var canLend: Bool { status == "in_stock" }
}

/// 貸出先の候補。
struct BorrowerOption: Codable, Identifiable, Equatable, Hashable {
    var id: String = ""
    var name: String = ""
    var company: String = ""
    var kind: String = ""
    var openCount: Int = 0

    enum CodingKeys: String, CodingKey { case id, name, company, kind, openCount = "open_count" }

    var subtitle: String {
        let head = company.isEmpty ? kind : company
        return openCount > 0 ? "\(head)・貸出中\(openCount)件" : head
    }
}

/// 返却予定の選択肢。サーバー側で作る場合もあるので、ラベルと値だけ持つ。
struct DueOption: Codable, Identifiable, Equatable, Hashable {
    var label: String = ""
    var value: String = ""        // ISO8601。空文字は「指定しない」
    var id: String { label + value }
}

/// 貸出先の種別。サーバーへは英語の値を送り、端末内には日本語で残す。
enum BorrowerKind: String, CaseIterable, Identifiable {
    case vendor, customer, employee, other
    var id: String { rawValue }
    var japanese: String {
        switch self {
        case .vendor: return "業者"
        case .customer: return "お客様"
        case .employee: return "社員"
        case .other: return "その他"
        }
    }
}

/// かざしたタグ1枚の読み取り結果。
struct TagRead: Equatable {
    var uid: String = ""
    var url: String?
    var text: String?
    var records: [ParsedRecord] = []

    /// テキストレコードを `物件名|鍵の名称|鍵番号|ボックス` に分解したもの。
    var fields: TagFields? {
        guard let text, !text.isEmpty else { return nil }
        let p = text.components(separatedBy: NDEF.separator)
        return TagFields(property: p.count > 0 ? p[0] : "",
                         name: p.count > 1 ? p[1] : "",
                         numbers: p.count > 2 ? p[2] : "",
                         box: p.count > 3 ? p[3] : "")
    }
}

struct TagFields: Equatable {
    var property = "", name = "", numbers = "", box = ""
}

struct ParsedRecord: Equatable {
    enum Kind: String { case url, text, other }
    var kind: Kind
    var value: String
}

/// 接続設定（端末内）。
struct Conf: Codable, Equatable {
    var tagType: String = "NTAG213"
    var server: String = ""
    var token: String = ""
    var org: String = ""

    var isLinked: Bool { !server.isEmpty && !token.isEmpty }
}
