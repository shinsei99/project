import Foundation

/// NDEF の組み立てと寸法計算。
///
/// ★サーバー側の `keyline/ndef.py` と **同じ形式**で書く必要がある。
///   片方だけ直すと、アプリで書いたタグをサーバーが読めない（またはその逆）。
///   書式・区切り文字・削る順番を変えるときは必ず両方を直すこと。
///
/// 書き込む内容（2レコード）
///   1. URLレコード     http://<サーバー>/t/<token>   … 単体モードでは省略される
///   2. テキストレコード 物件名|鍵の名称|鍵番号|ボックス-位置  … 圏外でも読める控え
enum NDEF {
    static let separator = "|"

    /// タグの容量（NXPの仕様値・ユーザーメモリ）
    static let capacity: [String: Int] = ["NTAG213": 144, "NTAG215": 504, "NTAG216": 888]
    static let tagTypes = ["NTAG213", "NTAG215", "NTAG216"]

    static let tnfWellKnown: UInt8 = 1
    static let typeURI: [UInt8] = [0x55]    // 'U'
    static let typeText: [UInt8] = [0x54]   // 'T'

    /// NDEF の URI Identifier Code。'http://' が 7バイト → 1バイトになる
    static let uriPrefixes: [(UInt8, String)] = [
        (0x01, "http://www."), (0x02, "https://www."),
        (0x03, "http://"), (0x04, "https://"),
    ]

    struct Record: Equatable {
        var tnf: UInt8 = NDEF.tnfWellKnown
        var type: [UInt8]
        var id: [UInt8] = []
        var payload: [UInt8]
    }

    struct Fields: Equatable {
        var property = ""
        var name = ""
        var numbers = ""
        var boxCode = ""
        var boxPosition = ""
        var url = ""
    }

    struct Plan: Equatable {
        var records: [Record] = []
        var text = ""
        var bytes = 0
        var capacity = 0
        var truncated = false
        var fits = true
        var tagType = "NTAG213"
        var free: Int { max(0, capacity - bytes) }
        var percent: Double { capacity == 0 ? 0 : min(1, Double(bytes) / Double(capacity)) }
    }

    // MARK: - 組み立て

    static func byteLen(_ s: String) -> Int { s.utf8.count }
    private static func bytes(_ s: String) -> [UInt8] { Array(s.utf8) }

    static func uriRecord(_ url: String) -> Record {
        var code: UInt8 = 0x00
        var rest = url
        for (c, prefix) in uriPrefixes where url.hasPrefix(prefix) {
            code = c
            rest = String(url.dropFirst(prefix.count))
            break
        }
        return Record(type: typeURI, payload: [code] + bytes(rest))
    }

    static func textRecord(_ text: String, lang: String = "ja") -> Record {
        Record(type: typeText, payload: [UInt8(lang.utf8.count)] + bytes(lang) + bytes(text))
    }

    /// タグ上で実際に消費するバイト数（レコードのヘッダとTLVの包みを含む）。
    /// ここを甘く見ると「書いたつもりで入っていない」が起きるので、`ndef.py` と同じ数え方をする。
    static func messageSize(_ records: [Record]) -> Int {
        var msg = 0
        for r in records {
            let short = r.payload.count < 256
            msg += 1 + 1 + (short ? 1 : 4) + r.type.count + r.payload.count
            if !r.id.isEmpty { msg += 1 + r.id.count }
        }
        return msg < 255 ? msg + 3 : msg + 5     // TLV（0x03 + 長さ + 終端0xFE）
    }

    // MARK: - 控えテキスト

    static func boxLabel(_ code: String, _ position: String) -> String {
        let c = code.trimmingCharacters(in: .whitespaces)
        let p = position.trimmingCharacters(in: .whitespaces)
        if !c.isEmpty && !p.isEmpty { return "\(c)-\(p)" }
        if !c.isEmpty { return c }
        return p.isEmpty ? "" : "位置\(p)"
    }

    static func infoText(_ f: Fields) -> String {
        [f.property, f.name, f.numbers, boxLabel(f.boxCode, f.boxPosition)]
            .filter { !$0.isEmpty }
            .joined(separator: separator)
    }

    /// UTF-8で budget バイトに収まるまで後ろを削る。日本語は1文字3バイト。
    static func cut(_ text: String, budget: Int) -> String {
        if byteLen(text) <= budget { return text }
        let b = max(budget - 3, 0)               // '…' の分
        var out = ""
        var used = 0
        for ch in text {
            let n = byteLen(String(ch))
            if used + n > b { break }
            out.append(ch)
            used += n
        }
        return out.isEmpty ? "" : out + "…"
    }

    /// このタグに何が書けるかを決める。
    ///
    /// ★削る順番が肝。鍵番号とボックスはASCIIで安く、しかも現場で一番使う情報
    ///   （どの鍵か・どこに戻すか）なので必ず残す。削るのは日本語の名前の方。
    ///   `ndef.py` の plan() と同じ規則。
    static func plan(_ f: Fields, tagType: String = "NTAG213") -> Plan {
        let cap = capacity[tagType] ?? capacity["NTAG213"]!
        func build(_ text: String?) -> [Record] {
            var rs: [Record] = []
            if !f.url.isEmpty { rs.append(uriRecord(f.url)) }
            if let text, !text.isEmpty { rs.append(textRecord(text)) }
            return rs
        }

        let text = infoText(f)
        var records = build(text)
        var size = messageSize(records)
        if size <= cap {
            return Plan(records: records, text: text, bytes: size, capacity: cap,
                        truncated: false, fits: true, tagType: tagType)
        }

        // 鍵番号とボックスは残す前提で、名前に使える枠を測る
        let box = boxLabel(f.boxCode, f.boxPosition)
        let cheap = [f.numbers, box].filter { !$0.isEmpty }.joined(separator: separator)
        let base = messageSize(build(cheap.isEmpty ? nil : cheap))
        let budget = cap - base - (cheap.isEmpty ? 0 : 1)

        let names = [f.property, f.name].filter { !$0.isEmpty }
        if budget > 0 && !names.isEmpty {
            let share = budget / names.count
            let cutNames = names.enumerated().map { i, n in
                cut(n, budget: share + (i == names.count - 1 ? budget % names.count : 0))
            }
            let t = (cutNames.filter { !$0.isEmpty } + (cheap.isEmpty ? [] : [cheap]))
                .joined(separator: separator)
            records = build(t)
            size = messageSize(records)
            if size <= cap {
                return Plan(records: records, text: t, bytes: size, capacity: cap,
                            truncated: true, fits: true, tagType: tagType)
            }
        }

        if !cheap.isEmpty {
            records = build(cheap)
            size = messageSize(records)
            if size <= cap {
                return Plan(records: records, text: cheap, bytes: size, capacity: cap,
                            truncated: true, fits: true, tagType: tagType)
            }
        }

        records = build(nil)
        size = messageSize(records)
        return Plan(records: records, text: "", bytes: size, capacity: cap,
                    truncated: true, fits: size <= cap, tagType: tagType)
    }

    // MARK: - 読み取り

    /// 生のNDEFレコード（type と payload）を、画面が使う形に直す。
    static func parseRecord(type: Data, payload: Data) -> ParsedRecord {
        let t = String(decoding: type, as: UTF8.self)
        let p = [UInt8](payload)
        if t == "U", let code = p.first {
            let prefix = uriPrefixes.first { $0.0 == code }?.1 ?? ""
            return ParsedRecord(kind: .url, value: prefix + String(decoding: p.dropFirst(), as: UTF8.self))
        }
        if t == "T", let head = p.first {
            let langLen = Int(head & 0x3f)
            return ParsedRecord(kind: .text, value: String(decoding: p.dropFirst(1 + langLen), as: UTF8.self))
        }
        return ParsedRecord(kind: .other, value: String(decoding: p, as: UTF8.self))
    }

    static func uidString(_ identifier: Data) -> String {
        identifier.map { String(format: "%02X", $0) }.joined(separator: ":")
    }

    /// KeyLineサーバーのURLかどうか（`/t/<トークン>` の形か）。
    static func keylineToken(_ url: String?) -> String? {
        guard let url else { return nil }
        let pattern = #"^https?://[^/]+/t/([a-z0-9]{8,32})$"#
        guard let re = try? NSRegularExpression(pattern: pattern, options: .caseInsensitive),
              let m = re.firstMatch(in: url, range: NSRange(url.startIndex..., in: url)),
              let r = Range(m.range(at: 1), in: url) else { return nil }
        return String(url[r])
    }

    /// 『03』の次は『04』。桁数は保つ。数字でなければそのまま。
    static func nextPosition(_ pos: String) -> String {
        let s = pos.trimmingCharacters(in: .whitespaces)
        guard let re = try? NSRegularExpression(pattern: #"^(\D*)(\d+)(\D*)$"#),
              let m = re.firstMatch(in: s, range: NSRange(s.startIndex..., in: s)),
              let head = Range(m.range(at: 1), in: s),
              let digits = Range(m.range(at: 2), in: s),
              let tail = Range(m.range(at: 3), in: s),
              let n = Int(s[digits]) else { return s }
        let width = s[digits].count
        return String(s[head]) + String(format: "%0\(width)d", n + 1) + String(s[tail])
    }
}
