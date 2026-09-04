import SwiftUI
import UniformTypeIdentifiers

struct LedgerView: View {
    @EnvironmentObject private var store: Store
    @EnvironmentObject private var router: Router
    @EnvironmentObject private var lending: LendingModel

    @State private var search = ""
    @State private var exporting = false
    @State private var importing = false
    @State private var exportDoc = ExportDocument(data: Data(), name: "鍵台帳.xlsx")
    @State private var message = ""
    @State private var messageIsError = false

    private var rows: [KeyRecord] {
        let all = store.sortedLedger
        let q = search.trimmingCharacters(in: .whitespaces)
        guard !q.isEmpty else { return all }
        return all.filter {
            [$0.property, $0.name, $0.numbers, $0.boxLabel, $0.borrower?.name ?? ""]
                .contains { $0.localizedCaseInsensitiveContains(q) }
        }
    }

    var body: some View {
        NavigationView {
            List {
                if !message.isEmpty {
                    MessageLine(text: message, isError: messageIsError)
                }
                if store.ledger.isEmpty {
                    Text("まだ鍵がありません。「書き込み」でタグに書くか、Excelから読み込んでください。")
                        .font(.footnote).foregroundColor(.secondary)
                }
                ForEach(rows) { r in
                    Button {
                        lending.clear()
                        lending.openLocal(r, store: store)
                        router.tab = .read
                    } label: {
                        row(r)
                    }
                    .buttonStyle(.plain)
                    .swipeActions(edge: .trailing) {
                        Button {
                            router.openWrite(with: Router.Draft(
                                property: r.property, name: r.name, numbers: r.numbers,
                                boxCode: r.boxCode, boxPosition: r.boxPosition))
                        } label: { Label("再書込", systemImage: "square.and.pencil") }
                        .tint(.accentColor)
                    }
                }
            }
            .listStyle(.insetGrouped)
            .searchable(text: $search, prompt: "物件名・鍵の名称・鍵番号")
            .navigationTitle("台帳（\(store.ledger.count)）")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Menu {
                        Button {
                            exportDoc = ExportDocument(data: LedgerFile.xlsx(from: store.ledger),
                                                       name: "鍵台帳.xlsx")
                            exporting = true
                        } label: { Label("Excelで書き出す", systemImage: "square.and.arrow.up") }

                        Button {
                            exportDoc = ExportDocument(data: LedgerFile.csv(from: store.ledger),
                                                       name: "鍵台帳.csv")
                            exporting = true
                        } label: { Label("CSVで書き出す", systemImage: "square.and.arrow.up") }

                        Divider()

                        Button {
                            importing = true
                        } label: { Label("Excel / CSV を読み込む", systemImage: "square.and.arrow.down") }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                    }
                }
            }
            .fileExporter(isPresented: $exporting, document: exportDoc,
                          contentType: exportDoc.contentType, defaultFilename: exportDoc.name) { result in
                switch result {
                case .success: say("書き出しました")
                case .failure(let e): say(e.localizedDescription, error: true)
                }
            }
            .fileImporter(isPresented: $importing,
                          allowedContentTypes: [ExportDocument.xlsxType, .commaSeparatedText, .data],
                          allowsMultipleSelection: false) { result in
                handleImport(result)
            }
        }
        .navigationViewStyle(.stack)
    }

    private func row(_ r: KeyRecord) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 6) {
                if r.status == .out {
                    StatusBadge(text: r.isOverdue ? "超過" : "貸出中", kind: r.isOverdue ? .overdue : .out)
                }
                if r.uid.isEmpty {
                    StatusBadge(text: "タグ未書込", kind: .inStock)
                }
                Text(r.label).font(.body)
            }
            Text(subtitle(r)).font(.caption).foregroundColor(.secondary)
        }
        .padding(.vertical, 2)
    }

    private func subtitle(_ r: KeyRecord) -> String {
        if r.status == .out {
            return [(r.borrower?.name ?? "") + " が借用中",
                    r.due == nil ? "返却予定なし" : "返却予定 " + Fmt.dateTime(r.due),
                    r.boxLabel].filter { !$0.isEmpty }.joined(separator: "  ・  ")
        }
        return [r.numbers, r.boxLabel,
                r.history.isEmpty ? "" : "貸出\(r.history.count)回"]
            .filter { !$0.isEmpty }.joined(separator: "  ・  ")
    }

    // MARK: - 読み込み

    private func handleImport(_ result: Result<[URL], Error>) {
        do {
            guard let url = try result.get().first else { return }
            // ファイル選択で渡されるURLは保護されているので、開く前に権限を取る
            let needsStop = url.startAccessingSecurityScopedResource()
            defer { if needsStop { url.stopAccessingSecurityScopedResource() } }

            let data = try Data(contentsOf: url)
            let sheet = try LedgerFile.sheet(from: data, filename: url.lastPathComponent)
            guard !sheet.header.isEmpty else {
                say("見出し行が見つかりませんでした（1行目に「鍵の名称」などの見出しが要ります）", error: true)
                return
            }
            let r = LedgerFile.apply(sheet, to: store)
            say(r.summary, error: r.added == 0 && r.updated == 0)
        } catch {
            say(error.localizedDescription, error: true)
        }
    }

    private func say(_ text: String, error: Bool = false) {
        message = text
        messageIsError = error
    }
}

/// 書き出し用の入れ物（Excel と CSV で使い回す）。
struct ExportDocument: FileDocument {
    static let xlsxType = UTType(filenameExtension: "xlsx") ?? .data
    static var readableContentTypes: [UTType] { [xlsxType, .commaSeparatedText, .data] }
    static var writableContentTypes: [UTType] { [xlsxType, .commaSeparatedText, .data] }

    var data: Data
    var name: String

    var contentType: UTType {
        name.hasSuffix(".csv") ? .commaSeparatedText : Self.xlsxType
    }

    init(data: Data, name: String) {
        self.data = data
        self.name = name
    }

    init(configuration: ReadConfiguration) throws {
        data = configuration.file.regularFileContents ?? Data()
        name = configuration.file.filename ?? "台帳"
    }

    func fileWrapper(configuration: WriteConfiguration) throws -> FileWrapper {
        FileWrapper(regularFileWithContents: data)
    }
}
