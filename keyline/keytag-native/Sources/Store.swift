import Foundation

/// 台帳と設定の置き場（端末内のみ）。
///
/// ★このアプリは**サーバーが無くても全部動く**のが設計の芯。
///   App Store の審査員は社内LANに入れないので、ここが崩れると審査を通らない。
///   サーバー連携は「設定でURLを入れた人だけ」の追加機能。
@MainActor
final class Store: ObservableObject {
    @Published var ledger: [KeyRecord] = []
    @Published var conf = Conf()

    private let ledgerURL: URL
    private let confURL: URL

    init(directory: URL? = nil) {
        let dir = directory ?? FileManager.default
            .urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        ledgerURL = dir.appendingPathComponent("keytag-ledger.json")
        confURL = dir.appendingPathComponent("keytag-conf.json")
        load()
    }

    // MARK: - 保存

    private func load() {
        let dec = JSONDecoder()
        dec.dateDecodingStrategy = .iso8601
        if let d = try? Data(contentsOf: ledgerURL), let v = try? dec.decode([KeyRecord].self, from: d) {
            ledger = v
        }
        if let d = try? Data(contentsOf: confURL), let v = try? dec.decode(Conf.self, from: d) {
            conf = v
        }
    }

    func saveLedger() {
        let enc = JSONEncoder()
        enc.dateEncodingStrategy = .iso8601
        try? enc.encode(ledger).write(to: ledgerURL, options: .atomic)
    }

    func saveConf() {
        let enc = JSONEncoder()
        enc.dateEncodingStrategy = .iso8601
        try? enc.encode(conf).write(to: confURL, options: .atomic)
    }

    // MARK: - 台帳

    /// 書き込んだ内容を台帳へ入れる。
    /// 同じタグに書き直した場合は、**貸出状態と履歴を引き継いで**中身だけ更新する。
    @discardableResult
    func addToLedger(_ f: NDEF.Fields, plan: NDEF.Plan, uid: String) -> KeyRecord {
        var rec = KeyRecord()
        rec.uid = uid
        rec.property = f.property
        rec.name = f.name
        rec.numbers = f.numbers
        rec.boxCode = f.boxCode
        rec.boxPosition = f.boxPosition
        rec.url = f.url
        rec.written = plan.text
        rec.bytes = plan.bytes

        if !uid.isEmpty, let i = ledger.firstIndex(where: { !$0.uid.isEmpty && $0.uid == uid }) {
            let old = ledger[i]
            rec.id = old.id
            rec.status = old.status
            rec.borrower = old.borrower
            rec.since = old.since
            rec.due = old.due
            rec.history = old.history
            ledger.remove(at: i)
        }
        ledger.insert(rec, at: 0)
        if ledger.count > 2000 { ledger = Array(ledger.prefix(2000)) }
        saveLedger()
        return rec
    }

    /// 端末内の台帳から鍵を探す。uid が最優先。
    func findLocal(_ t: TagRead) -> KeyRecord? {
        if !t.uid.isEmpty, let r = ledger.first(where: { !$0.uid.isEmpty && $0.uid == t.uid }) { return r }
        if let url = t.url, !url.isEmpty, let r = ledger.first(where: { $0.url == url }) { return r }
        // uid を控える前に書いたタグのために、書いた文字が一致するものも見る
        if let text = t.text, !text.isEmpty { return ledger.first { !$0.written.isEmpty && $0.written == text } }
        return nil
    }

    func index(of id: String) -> Int? { ledger.firstIndex { $0.id == id } }

    /// 端末内の貸出先の候補。直近に貸した順。
    func localBorrowers() -> [BorrowerOption] {
        var seen: [String: (BorrowerOption, Date)] = [:]
        for r in ledger {
            var entries: [(String, String, String, Date?)] = r.history.map { ($0.name, $0.company, $0.kind, $0.at) }
            if let b = r.borrower { entries.append((b.name, b.company, b.kind, r.since)) }
            for (name, company, kind, at) in entries where !name.isEmpty {
                let key = name + "|" + company
                let when = at ?? Date.distantPast
                if let prev = seen[key], prev.1 >= when { continue }
                seen[key] = (BorrowerOption(id: key, name: name, company: company, kind: kind), when)
            }
        }
        return seen.values.sorted { $0.1 > $1.1 }.prefix(20).map(\.0)
    }

    /// 端末内の1件を、画面が使う形に直す（サーバーの返す形に合わせる）。
    func asset(for r: KeyRecord) -> Asset {
        var a = Asset()
        a.propertyName = r.property
        a.name = r.name
        a.label = r.label
        a.itemNumbers = r.numbers
        a.totalKeys = r.totalKeys
        a.box = r.boxLabel
        a.status = r.status == .out ? "checked_out" : "in_stock"
        a.statusLabel = r.status == .out ? "貸出中" : "保管中"
        a.borrower = r.borrower
        a.checkedOutAt = Fmt.dateTime(r.since)
        a.dueAt = Fmt.dateTime(r.due)
        a.elapsed = Fmt.elapsed(r.since)
        a.isOverdue = r.isOverdue
        return a
    }

    /// 返却予定の選択肢（端末内）。サーバー連携時はサーバーが返すものを使う。
    func localDues() -> [DueOption] {
        let now = Date()
        let cal = Calendar.current
        var out: [DueOption] = []
        func at18(_ d: Date) -> Date {
            cal.date(bySettingHour: 18, minute: 0, second: 0, of: d) ?? d
        }
        let today18 = at18(now)
        if today18 > now { out.append(DueOption(label: "今日 18:00", value: Fmt.iso(today18))) }
        out.append(DueOption(label: "明日 18:00", value: Fmt.iso(at18(now.addingTimeInterval(86400)))))
        out.append(DueOption(label: "2時間後", value: Fmt.iso(now.addingTimeInterval(7200))))
        out.append(DueOption(label: "3日後", value: Fmt.iso(now.addingTimeInterval(259200))))
        out.append(DueOption(label: "指定しない", value: ""))
        return out
    }

    // MARK: - 貸出・返却（端末内）

    enum LendError: LocalizedError {
        case alreadyOut, notOut, missing
        var errorDescription: String? {
            switch self {
            case .alreadyOut: return "この鍵はすでに貸出中です"
            case .notOut: return "この鍵は貸出中ではありません"
            case .missing: return "この鍵が台帳に見つかりません"
            }
        }
    }

    func checkoutLocal(id: String, borrower: Borrower, due: String) throws -> KeyRecord {
        guard let i = index(of: id) else { throw LendError.missing }
        guard ledger[i].status == .inStock else { throw LendError.alreadyOut }
        ledger[i].status = .out
        ledger[i].borrower = borrower
        ledger[i].since = Date()
        ledger[i].due = due.isEmpty ? nil : Fmt.date(fromISO: due)
        saveLedger()
        return ledger[i]
    }

    func returnLocal(id: String) throws -> KeyRecord {
        guard let i = index(of: id) else { throw LendError.missing }
        guard ledger[i].status == .out else { throw LendError.notOut }
        // 履歴に積んでから状態を戻す。誰にいつ貸したかが消えないようにする
        let b = ledger[i].borrower
        ledger[i].history.insert(LendHistory(name: b?.name ?? "", company: b?.company ?? "",
                                             kind: b?.kind ?? "", at: ledger[i].since,
                                             returned: Date(), due: ledger[i].due), at: 0)
        if ledger[i].history.count > 200 { ledger[i].history = Array(ledger[i].history.prefix(200)) }
        ledger[i].status = .inStock
        ledger[i].borrower = nil
        ledger[i].since = nil
        ledger[i].due = nil
        saveLedger()
        return ledger[i]
    }

    // MARK: - 一覧の並び

    /// 貸出中を先に、そのうち期限超過を最優先で出す。
    var sortedLedger: [KeyRecord] {
        ledger.sorted { a, b in
            let ao = a.isOverdue ? 0 : 1, bo = b.isOverdue ? 0 : 1
            if ao != bo { return ao < bo }
            let au = a.status == .out ? 0 : 1, bu = b.status == .out ? 0 : 1
            if au != bu { return au < bu }
            return a.at > b.at
        }
    }

    var propertyNames: [String] {
        var seen = Set<String>()
        return ledger.map(\.property).filter { !$0.isEmpty && seen.insert($0).inserted }
    }

    // MARK: - お試し・全消し

    /// ★スクリーンショットのための細工ではなく、必要な機能。
    ///   NFCタグを持っていない人（App Storeの審査員を含む）が、
    ///   台帳・貸出・返却の動きを確かめられないと、このアプリは評価できない。
    func addSamples() {
        struct S { let property, name, numbers, box, pos: String; let lend: Borrower?; let dueHours: Double }
        let samples: [S] = [
            S(property: "本社ビル", name: "1階エントランス", numbers: "10001 / 10002",
              box: "BOX-01", pos: "01", lend: nil, dueHours: 0),
            S(property: "本社ビル", name: "機械室", numbers: "10003 ×3",
              box: "BOX-01", pos: "02",
              lend: Borrower(name: "田中 一郎", company: "〇〇工務店", kind: "業者"), dueHours: 6),
            S(property: "本社ビル", name: "3階会議室", numbers: "10008",
              box: "BOX-01", pos: "03", lend: nil, dueHours: 0),
            S(property: "第2倉庫", name: "シャッター", numbers: "22001 ×2",
              box: "BOX-02", pos: "01",
              lend: Borrower(name: "鈴木 次郎", company: "△△クリーンサービス", kind: "業者"), dueHours: -2),
            S(property: "", name: "社用車 1号", numbers: "CAR-01",
              box: "BOX-01", pos: "10", lend: nil, dueHours: 0),
        ]
        for (i, s) in samples.enumerated() {
            let f = NDEF.Fields(property: s.property, name: s.name, numbers: s.numbers,
                                boxCode: s.box, boxPosition: s.pos, url: "")
            // サンプルだと分かる形のタグID（実物と混ざらないように 00: で始める）
            let uid = "00:" + String(format: "%02d", i + 1) + ":SA:MP:LE:00:00"
            let rec = addToLedger(f, plan: NDEF.plan(f, tagType: conf.tagType), uid: uid)
            if let lend = s.lend, let idx = index(of: rec.id) {
                ledger[idx].status = .out
                ledger[idx].borrower = lend
                ledger[idx].since = Date().addingTimeInterval(-3 * 3600)
                ledger[idx].due = Date().addingTimeInterval(s.dueHours * 3600)
            }
        }
        saveLedger()
    }

    func clearAll() {
        ledger = []
        saveLedger()
    }
}

// MARK: - 表示のための整形

enum Fmt {
    static func dateTime(_ d: Date?) -> String {
        guard let d else { return "" }
        let f = DateFormatter()
        f.locale = Locale(identifier: "ja_JP")
        f.dateFormat = "yyyy/MM/dd HH:mm"
        return f.string(from: d)
    }

    static func elapsed(_ from: Date?) -> String {
        guard let from else { return "" }
        let m = max(0, Int(Date().timeIntervalSince(from) / 60))
        let d = m / 1440, h = (m % 1440) / 60
        if d > 0 { return "\(d)日\(h)時間" }
        if h > 0 { return "\(h)時間\(m % 60)分" }
        return "\(m)分"
    }

    static func iso(_ d: Date) -> String {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f.string(from: d)
    }

    static func date(fromISO s: String) -> Date? {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let d = f.date(from: s) { return d }
        f.formatOptions = [.withInternetDateTime]
        return f.date(from: s)
    }
}
