import Foundation
import Compression

/// Excel（.xlsx）の書き出しと読み込み。**外部ライブラリを使わない。**
///
/// ★なぜ自前で書くか
///   ライブラリを足すと依存が増え、他のアプリと同じ土台に見える材料が増える。
///   xlsx は実体が **ZIP + XML** なので、必要な範囲だけなら自分で扱える。
///   - 書き出し … 無圧縮（stored）のZIPを組む。Excel も Numbers もそのまま開ける
///   - 読み込み … stored と deflate の両方に対応（Excel が書くのは deflate）。
///                展開は OS 標準の Compression（zlib＝生deflate）を使う
///
/// 対応する範囲は「1シート・文字列と数値のセル」まで。数式・書式は読まない（台帳には不要）。
enum XLSX {

    // MARK: - 書き出し

    /// 見出し行＋データ行から .xlsx のバイト列を作る。
    static func build(sheetName: String, header: [String], rows: [[String]]) -> Data {
        var entries: [ZipWriter.Entry] = []
        entries.append(.init(name: "[Content_Types].xml", data: Data(contentTypes.utf8)))
        entries.append(.init(name: "_rels/.rels", data: Data(rootRels.utf8)))
        entries.append(.init(name: "xl/workbook.xml", data: Data(workbook(sheetName: sheetName).utf8)))
        entries.append(.init(name: "xl/_rels/workbook.xml.rels", data: Data(workbookRels.utf8)))
        entries.append(.init(name: "xl/styles.xml", data: Data(styles.utf8)))
        entries.append(.init(name: "xl/worksheets/sheet1.xml",
                             data: Data(sheet(header: header, rows: rows).utf8)))
        return ZipWriter.archive(entries)
    }

    private static let contentTypes = """
    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
    <Default Extension="xml" ContentType="application/xml"/>
    <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
    <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
    <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
    </Types>
    """

    private static let rootRels = """
    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
    </Relationships>
    """

    private static func workbook(sheetName: String) -> String {
        """
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" \
        xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
        <sheets><sheet name="\(escape(sheetName))" sheetId="1" r:id="rId1"/></sheets>
        </workbook>
        """
    }

    private static let workbookRels = """
    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
    <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
    </Relationships>
    """

    /// 見出しを太字にするためだけの最小の書式。
    private static let styles = """
    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
    <fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>
    <font><b/><sz val="11"/><name val="Calibri"/></font></fonts>
    <fills count="1"><fill><patternFill patternType="none"/></fill></fills>
    <borders count="1"><border/></borders>
    <cellStyleXfs count="1"><xf/></cellStyleXfs>
    <cellXfs count="2"><xf xfId="0"/><xf fontId="1" applyFont="1" xfId="0"/></cellXfs>
    </styleSheet>
    """

    private static func sheet(header: [String], rows: [[String]]) -> String {
        var xml = """
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
        """
        xml += row(index: 1, cells: header, styleIndex: 1)
        for (i, r) in rows.enumerated() {
            xml += row(index: i + 2, cells: r, styleIndex: 0)
        }
        xml += "</sheetData></worksheet>"
        return xml
    }

    /// 文字列セルは inlineStr で書く（sharedStrings を作らずに済む）。
    private static func row(index: Int, cells: [String], styleIndex: Int) -> String {
        var out = "<row r=\"\(index)\">"
        for (c, value) in cells.enumerated() {
            let ref = columnName(c) + String(index)
            let s = styleIndex > 0 ? " s=\"\(styleIndex)\"" : ""
            if value.isEmpty {
                out += "<c r=\"\(ref)\"\(s)/>"
            } else {
                out += "<c r=\"\(ref)\"\(s) t=\"inlineStr\"><is><t xml:space=\"preserve\">\(escape(value))</t></is></c>"
            }
        }
        return out + "</row>"
    }

    static func columnName(_ index: Int) -> String {
        var n = index, out = ""
        repeat {
            out = String(UnicodeScalar(UInt8(65 + n % 26))) + out
            n = n / 26 - 1
        } while n >= 0
        return out
    }

    private static func escape(_ s: String) -> String {
        s.replacingOccurrences(of: "&", with: "&amp;")
            .replacingOccurrences(of: "<", with: "&lt;")
            .replacingOccurrences(of: ">", with: "&gt;")
            .replacingOccurrences(of: "\"", with: "&quot;")
    }

    // MARK: - 読み込み

    struct Sheet {
        var header: [String] = []
        var rows: [[String]] = []
    }

    enum ReadError: LocalizedError {
        case notZip, noSheet, broken(String)
        var errorDescription: String? {
            switch self {
            case .notZip: return "Excelのファイルとして読めませんでした"
            case .noSheet: return "シートが見つかりませんでした"
            case .broken(let m): return "読み込みに失敗しました（\(m)）"
            }
        }
    }

    /// .xlsx を読んで、先頭シートの見出し行と本文を返す。
    static func read(_ data: Data) throws -> Sheet {
        let files = try ZipReader.entries(data)
        guard let sheetXML = files.first(where: { $0.key.hasSuffix("worksheets/sheet1.xml") })?.value
                ?? files.first(where: { $0.key.contains("worksheets/") })?.value else {
            throw ReadError.noSheet
        }
        // 共有文字列（Excel が書き出すファイルはこちらを使うことが多い）
        var shared: [String] = []
        if let ss = files["xl/sharedStrings.xml"] {
            shared = SharedStringsParser.parse(ss)
        }
        let grid = SheetParser.parse(sheetXML, shared: shared)
        guard let head = grid.first else { return Sheet() }
        return Sheet(header: head, rows: Array(grid.dropFirst()))
    }

    /// CSV も読めるようにしておく（Excelを持っていない相手から受け取ることがある）。
    static func readCSV(_ data: Data) -> Sheet {
        var text = String(data: data, encoding: .utf8)
            ?? String(data: data, encoding: .shiftJIS) ?? ""
        if text.hasPrefix("\u{FEFF}") { text.removeFirst() }

        var rows: [[String]] = []
        var row: [String] = []
        var field = ""
        var inQuotes = false
        var i = text.startIndex
        while i < text.endIndex {
            let ch = text[i]
            if inQuotes {
                if ch == "\"" {
                    let next = text.index(after: i)
                    if next < text.endIndex, text[next] == "\"" { field.append("\""); i = next }
                    else { inQuotes = false }
                } else { field.append(ch) }
            } else {
                switch ch {
                case "\"": inQuotes = true
                case ",": row.append(field); field = ""
                case "\r": break
                case "\n": row.append(field); field = ""; rows.append(row); row = []
                default: field.append(ch)
                }
            }
            i = text.index(after: i)
        }
        if !field.isEmpty || !row.isEmpty { row.append(field); rows.append(row) }
        rows = rows.filter { !$0.allSatisfy(\.isEmpty) }
        guard let head = rows.first else { return Sheet() }
        return Sheet(header: head, rows: Array(rows.dropFirst()))
    }
}

// MARK: - ZIP 書き

enum ZipWriter {
    struct Entry {
        var name: String
        var data: Data
    }

    /// 無圧縮（stored）でZIPを組む。台帳のサイズなら圧縮は要らない。
    static func archive(_ entries: [Entry]) -> Data {
        var out = Data()
        var central = Data()
        var offsets: [Int] = []

        for e in entries {
            offsets.append(out.count)
            let name = Array(e.name.utf8)
            let crc = CRC32.checksum(e.data)
            var local = Data()
            local.append(le32(0x04034b50))
            local.append(le16(20))            // version needed
            local.append(le16(0x0800))        // flags: UTF-8
            local.append(le16(0))             // method: stored
            local.append(le16(0))             // time
            local.append(le16(0x21))          // date（1980-01-01。中身に影響しない）
            local.append(le32(crc))
            local.append(le32(UInt32(e.data.count)))
            local.append(le32(UInt32(e.data.count)))
            local.append(le16(UInt16(name.count)))
            local.append(le16(0))
            local.append(contentsOf: name)
            local.append(e.data)
            out.append(local)
        }

        for (i, e) in entries.enumerated() {
            let name = Array(e.name.utf8)
            central.append(le32(0x02014b50))
            central.append(le16(20))          // version made by
            central.append(le16(20))          // version needed
            central.append(le16(0x0800))
            central.append(le16(0))
            central.append(le16(0))
            central.append(le16(0x21))
            central.append(le32(CRC32.checksum(e.data)))
            central.append(le32(UInt32(e.data.count)))
            central.append(le32(UInt32(e.data.count)))
            central.append(le16(UInt16(name.count)))
            central.append(le16(0))           // extra
            central.append(le16(0))           // comment
            central.append(le16(0))           // disk
            central.append(le16(0))           // internal attrs
            central.append(le32(0))           // external attrs
            central.append(le32(UInt32(offsets[i])))
            central.append(contentsOf: name)
        }

        let cdOffset = out.count
        out.append(central)
        out.append(le32(0x06054b50))
        out.append(le16(0))
        out.append(le16(0))
        out.append(le16(UInt16(entries.count)))
        out.append(le16(UInt16(entries.count)))
        out.append(le32(UInt32(central.count)))
        out.append(le32(UInt32(cdOffset)))
        out.append(le16(0))
        return out
    }

    private static func le16(_ v: UInt16) -> Data { withUnsafeBytes(of: v.littleEndian) { Data($0) } }
    private static func le32(_ v: UInt32) -> Data { withUnsafeBytes(of: v.littleEndian) { Data($0) } }
}

// MARK: - ZIP 読み

enum ZipReader {
    /// ZIP の中身を「パス → 中身」で返す。stored と deflate に対応。
    static func entries(_ data: Data) throws -> [String: Data] {
        let bytes = [UInt8](data)
        guard bytes.count > 22 else { throw XLSX.ReadError.notZip }

        // 末尾から EOCD（0x06054b50）を探す
        var eocd = -1
        let lower = max(0, bytes.count - 66_000)
        var i = bytes.count - 22
        while i >= lower {
            if bytes[i] == 0x50, bytes[i+1] == 0x4b, bytes[i+2] == 0x05, bytes[i+3] == 0x06 { eocd = i; break }
            i -= 1
        }
        guard eocd >= 0 else { throw XLSX.ReadError.notZip }

        let count = Int(u16(bytes, eocd + 10))
        var p = Int(u32(bytes, eocd + 16))       // central directory の位置
        var out: [String: Data] = [:]

        for _ in 0..<count {
            guard p + 46 <= bytes.count, u32(bytes, p) == 0x02014b50 else { break }
            let method = Int(u16(bytes, p + 10))
            let compSize = Int(u32(bytes, p + 20))
            let uncompSize = Int(u32(bytes, p + 24))
            let nameLen = Int(u16(bytes, p + 28))
            let extraLen = Int(u16(bytes, p + 30))
            let commentLen = Int(u16(bytes, p + 32))
            let localOffset = Int(u32(bytes, p + 42))
            let name = String(decoding: bytes[(p + 46)..<(p + 46 + nameLen)], as: UTF8.self)

            // ローカルヘッダを見て本体の開始位置を求める（extra の長さが中央と違うことがある）
            if localOffset + 30 <= bytes.count, u32(bytes, localOffset) == 0x04034b50 {
                let lnameLen = Int(u16(bytes, localOffset + 26))
                let lextraLen = Int(u16(bytes, localOffset + 28))
                let start = localOffset + 30 + lnameLen + lextraLen
                let end = start + compSize
                if end <= bytes.count {
                    let raw = Data(bytes[start..<end])
                    if method == 0 {
                        out[name] = raw
                    } else if method == 8, let inflated = inflate(raw, expected: uncompSize) {
                        out[name] = inflated
                    }
                }
            }
            p += 46 + nameLen + extraLen + commentLen
        }
        if out.isEmpty { throw XLSX.ReadError.notZip }
        return out
    }

    /// 生 deflate の展開。OS標準の Compression（COMPRESSION_ZLIB＝生deflate）を使う。
    private static func inflate(_ data: Data, expected: Int) -> Data? {
        let capacity = max(expected, data.count * 8, 64 * 1024)
        var out = Data(count: capacity)
        let written = out.withUnsafeMutableBytes { dst -> Int in
            data.withUnsafeBytes { src -> Int in
                guard let d = dst.bindMemory(to: UInt8.self).baseAddress,
                      let s = src.bindMemory(to: UInt8.self).baseAddress else { return 0 }
                return compression_decode_buffer(d, capacity, s, data.count, nil, COMPRESSION_ZLIB)
            }
        }
        guard written > 0 else { return nil }
        return out.prefix(written)
    }

    private static func u16(_ b: [UInt8], _ i: Int) -> UInt16 {
        guard i + 1 < b.count else { return 0 }
        return UInt16(b[i]) | UInt16(b[i+1]) << 8
    }

    private static func u32(_ b: [UInt8], _ i: Int) -> UInt32 {
        guard i + 3 < b.count else { return 0 }
        return UInt32(b[i]) | UInt32(b[i+1]) << 8 | UInt32(b[i+2]) << 16 | UInt32(b[i+3]) << 24
    }
}

enum CRC32 {
    private static let table: [UInt32] = (0..<256).map { i -> UInt32 in
        var c = UInt32(i)
        for _ in 0..<8 { c = (c & 1) == 1 ? (0xEDB88320 ^ (c >> 1)) : (c >> 1) }
        return c
    }

    static func checksum(_ data: Data) -> UInt32 {
        var c: UInt32 = 0xFFFFFFFF
        for b in data { c = table[Int((c ^ UInt32(b)) & 0xFF)] ^ (c >> 8) }
        return c ^ 0xFFFFFFFF
    }
}

// MARK: - XML 解析

/// `xl/sharedStrings.xml` → 文字列の配列
final class SharedStringsParser: NSObject, XMLParserDelegate {
    private var out: [String] = []
    private var current = ""
    private var inText = false

    static func parse(_ data: Data) -> [String] {
        let p = SharedStringsParser()
        let parser = XMLParser(data: data)
        parser.delegate = p
        parser.parse()
        return p.out
    }

    func parser(_ parser: XMLParser, didStartElement e: String, namespaceURI: String?,
                qualifiedName: String?, attributes: [String: String] = [:]) {
        if e == "si" { current = "" }
        if e == "t" { inText = true }
    }

    func parser(_ parser: XMLParser, foundCharacters string: String) {
        if inText { current += string }
    }

    func parser(_ parser: XMLParser, didEndElement e: String, namespaceURI: String?, qualifiedName: String?) {
        if e == "t" { inText = false }
        if e == "si" { out.append(current) }
    }
}

/// `xl/worksheets/sheet1.xml` → 行 × 列の文字列
final class SheetParser: NSObject, XMLParserDelegate {
    private var shared: [String] = []
    private var rows: [[String]] = []
    private var row: [String] = []
    private var cellRef = ""
    private var cellType = ""
    private var value = ""
    private var inValue = false

    static func parse(_ data: Data, shared: [String]) -> [[String]] {
        let p = SheetParser()
        p.shared = shared
        let parser = XMLParser(data: data)
        parser.delegate = p
        parser.parse()
        return p.rows
    }

    func parser(_ parser: XMLParser, didStartElement e: String, namespaceURI: String?,
                qualifiedName: String?, attributes a: [String: String] = [:]) {
        switch e {
        case "row": row = []
        case "c":
            cellRef = a["r"] ?? ""
            cellType = a["t"] ?? ""
            value = ""
        case "v", "t": inValue = true
        default: break
        }
    }

    func parser(_ parser: XMLParser, foundCharacters string: String) {
        if inValue { value += string }
    }

    func parser(_ parser: XMLParser, didEndElement e: String, namespaceURI: String?, qualifiedName: String?) {
        switch e {
        case "v", "t":
            inValue = false
        case "c":
            // 列の位置（A1 の "A"）を見て、空セルを詰めずに列を合わせる
            let col = columnIndex(cellRef)
            while row.count < col { row.append("") }
            var text = value
            if cellType == "s", let i = Int(value), i < shared.count { text = shared[i] }
            row.append(text)
        case "row":
            rows.append(row)
        default: break
        }
    }

    private func columnIndex(_ ref: String) -> Int {
        var n = 0
        for ch in ref {
            guard let ascii = ch.asciiValue, ascii >= 65, ascii <= 90 else { break }
            n = n * 26 + Int(ascii - 64)
        }
        return max(0, n - 1)
    }
}
