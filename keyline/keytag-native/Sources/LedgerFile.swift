import Foundation

/// 台帳の書き出し・読み込み（Excel / CSV）。
///
/// ★何のためにあるか（2026-09-04 追加）
///   1. Excel で鍵の一覧を作っておき、現場ではタグに書くだけにする
///   2. 台帳を人に渡す・受け取る（この端末に閉じ込めない）
///
/// ★読み込みの照合規則
///   - **タグID（uid）が入っていればそれで照合**する。タグに書いた文字は変わり得るが uid は変わらない
///   - uid が空なら「物件名＋鍵の名称」で照合する
///   - 見つかった鍵は**中身だけ更新し、貸出状態と履歴はそのまま残す**
///     （Excel の側に「いま誰が借りているか」を書かせない。現場の記録のほうが正しいため）
///   - 見つからなければ新規に追加する。uid が空なら「タグ未書込」として台帳に並ぶ
enum LedgerFile {

    static let header = ["物件名", "鍵の名称", "鍵番号", "ボックス", "位置",
                         "状態", "貸出先", "会社", "返却予定", "タグID", "登録日時"]

    // MARK: - 書き出し

    static func rows(from ledger: [KeyRecord]) -> [[String]] {
        ledger.map { r in
            [r.property, r.name, r.numbers, r.boxCode, r.boxPosition,
             r.status == .out ? (r.isOverdue ? "貸出中（期限超過）" : "貸出中") : "保管中",
             r.borrower?.name ?? "", r.borrower?.company ?? "",
             Fmt.dateTime(r.due), r.uid, Fmt.dateTime(r.at)]
        }
    }

    static func xlsx(from ledger: [KeyRecord]) -> Data {
        XLSX.build(sheetName: "鍵台帳", header: header, rows: rows(from: ledger))
    }

    /// CSV も残す（Excelを持っていない相手へ渡すため）。先頭のBOMはExcelでの文字化けよけ。
    static func csv(from ledger: [KeyRecord]) -> Data {
        let esc = { (s: String) in "\"" + s.replacingOccurrences(of: "\"", with: "\"\"") + "\"" }
        var text = "\u{FEFF}" + header.map(esc).joined(separator: ",") + "\r\n"
        for r in rows(from: ledger) {
            text += r.map(esc).joined(separator: ",") + "\r\n"
        }
        return Data(text.utf8)
    }

    // MARK: - 読み込み

    struct ImportResult {
        var added = 0
        var updated = 0
        var skipped = 0

        var summary: String {
            if added == 0 && updated == 0 { return "取り込める行がありませんでした" }
            var parts: [String] = []
            if added > 0 { parts.append("新しく \(added) 件") }
            if updated > 0 { parts.append("更新 \(updated) 件") }
            if skipped > 0 { parts.append("読めなかった行 \(skipped)") }
            return parts.joined(separator: " / ")
        }
    }

    /// 見出し行から列の位置を割り出す。列の順番が入れ替わっていても読める。
    private static func columnMap(_ head: [String]) -> [String: Int] {
        var map: [String: Int] = [:]
        for (i, raw) in head.enumerated() {
            let h = raw.trimmingCharacters(in: .whitespaces)
            switch h {
            case "物件名", "物件": map["property"] = i
            case "鍵の名称", "名称", "鍵名": map["name"] = i
            case "鍵番号", "番号": map["numbers"] = i
            case "ボックス", "BOX", "箱": map["box"] = i
            case "位置", "ポジション": map["pos"] = i
            case "タグID", "UID", "uid": map["uid"] = i
            default: break
            }
        }
        return map
    }

    static func sheet(from data: Data, filename: String) throws -> XLSX.Sheet {
        if filename.lowercased().hasSuffix(".csv") { return XLSX.readCSV(data) }
        return try XLSX.read(data)
    }

    /// 読み込んだ表を台帳へ反映する。
    @MainActor
    static func apply(_ sheet: XLSX.Sheet, to store: Store) -> ImportResult {
        let map = columnMap(sheet.header)
        var result = ImportResult()
        // 名称の列が無ければ、それは台帳の表ではない
        guard map["name"] != nil else { return result }

        func cell(_ row: [String], _ key: String) -> String {
            guard let i = map[key], i < row.count else { return "" }
            return row[i].trimmingCharacters(in: .whitespaces)
        }

        for row in sheet.rows {
            let name = cell(row, "name")
            if name.isEmpty { result.skipped += 1; continue }
            let property = cell(row, "property")
            let uid = cell(row, "uid")

            let existing: Int? = {
                if !uid.isEmpty, let i = store.ledger.firstIndex(where: { $0.uid == uid }) { return i }
                return store.ledger.firstIndex { $0.property == property && $0.name == name }
            }()

            if let i = existing {
                // 中身だけ更新する。**貸出状態と履歴は触らない**
                store.ledger[i].property = property
                store.ledger[i].name = name
                store.ledger[i].numbers = cell(row, "numbers")
                store.ledger[i].boxCode = cell(row, "box")
                store.ledger[i].boxPosition = cell(row, "pos")
                if !uid.isEmpty { store.ledger[i].uid = uid }
                result.updated += 1
            } else {
                var rec = KeyRecord()
                rec.uid = uid
                rec.property = property
                rec.name = name
                rec.numbers = cell(row, "numbers")
                rec.boxCode = cell(row, "box")
                rec.boxPosition = cell(row, "pos")
                store.ledger.insert(rec, at: 0)
                result.added += 1
            }
        }
        store.saveLedger()
        return result
    }
}
