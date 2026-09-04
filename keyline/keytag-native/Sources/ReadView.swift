import SwiftUI

struct ReadView: View {
    @EnvironmentObject private var store: Store
    @EnvironmentObject private var router: Router
    @EnvironmentObject private var lending: LendingModel

    @State private var nfc = NFCService()
    @State private var scanning = false
    @State private var lead = "タグをかざすと、その鍵の貸出・返却ができます。"
    @State private var readError = ""

    // 貸出の入力
    @State private var selected: BorrowerOption?
    @State private var newName = ""
    @State private var newCompany = ""
    @State private var newPhone = ""
    @State private var kind: BorrowerKind = .vendor
    @State private var due: DueOption?
    @State private var showRaw = false

    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 16) {
                    scanCard
                    if lending.unregistered { unregisteredCard }
                    if let asset = lending.asset { lendingCard(asset) }
                    if !lending.message.isEmpty {
                        MessageLine(text: lending.message, isError: lending.messageIsError)
                            .padding(.horizontal, 4)
                    }
                }
                .padding()
            }
            .background(Color(.systemGroupedBackground))
            .navigationTitle("読み取り")
        }
        .navigationViewStyle(.stack)
    }

    // MARK: - かざす

    private var scanCard: some View {
        Card(title: "") {
            VStack(spacing: 12) {
                Button {
                    Task { await scan() }
                } label: {
                    HStack {
                        Image(systemName: "wave.3.right.circle.fill").font(.title2)
                        Text(scanning ? "タグに近づけてください…" : "タグをかざす").bold()
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
                }
                .buttonStyle(.borderedProminent)
                .disabled(scanning)

                Text(lead).font(.footnote).foregroundColor(.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)

                if !NFCService.isAvailable, !ShotMode.on {
                    Text("この端末ではNFCを使えません（実機のiPhoneが必要です）。台帳の行をタップすると、タグなしで中身を確認できます。")
                        .font(.caption).foregroundColor(.orange)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                MessageLine(text: readError, isError: true)
            }
        }
    }

    private func scan() async {
        readError = ""
        scanning = true
        defer { scanning = false }
        do {
            let tag = try await nfc.read()
            lead = "読み取りました"
            await lending.present(tag: tag, store: store)
            resetInputs()
        } catch let e as NFCError {
            if case .canceled = e { return }
            readError = e.localizedDescription
        } catch {
            readError = error.localizedDescription
        }
    }

    private func resetInputs() {
        selected = nil
        newName = ""; newCompany = ""; newPhone = ""
        kind = .vendor
        due = lending.dues.first
    }

    // MARK: - 台帳に無いタグ

    private var unregisteredCard: some View {
        Card(title: "このタグはまだ登録されていません") {
            VStack(alignment: .leading, spacing: 10) {
                FieldRow(label: "タグID", value: lending.tag?.uid ?? "")
                if let f = lending.tag?.fields {
                    FieldRow(label: "書かれた内容", value: [f.property, f.name, f.numbers, f.box]
                        .filter { !$0.isEmpty }.joined(separator: " / "))
                }
                Button {
                    let f = lending.tag?.fields
                    var draft = Router.Draft()
                    draft.property = f?.property ?? ""
                    draft.name = f?.name ?? ""
                    draft.numbers = f?.numbers ?? ""
                    if let box = f?.box, let sep = box.lastIndex(of: "-") {
                        draft.boxCode = String(box[box.startIndex..<sep])
                        draft.boxPosition = String(box[box.index(after: sep)...])
                    } else {
                        draft.boxCode = f?.box ?? ""
                    }
                    router.openWrite(with: draft)
                } label: {
                    Text("この鍵を登録する").frame(maxWidth: .infinity).padding(.vertical, 8)
                }
                .buttonStyle(.borderedProminent)
            }
        }
    }

    // MARK: - 貸出・返却

    @ViewBuilder
    private func lendingCard(_ a: Asset) -> some View {
        Card(title: "") {
            VStack(alignment: .leading, spacing: 14) {
                HStack {
                    StatusBadge(text: a.badgeText, kind: a.badgeKind)
                    Spacer()
                    if case .server = lending.source {
                        Label("サーバー", systemImage: "network").font(.caption2).foregroundColor(.secondary)
                    }
                }
                VStack(alignment: .leading, spacing: 2) {
                    if !a.propertyName.isEmpty {
                        Text(a.propertyName).font(.footnote).foregroundColor(.secondary)
                    }
                    Text(a.name).font(.title3).bold()
                }
                FieldRow(label: "鍵番号", value: a.itemNumbers + (a.totalKeys > 1 ? "  計\(a.totalKeys)本" : ""))
                FieldRow(label: "保管場所", value: a.box.isEmpty ? "" :
                            a.box + (a.boxName.isEmpty ? "" : "（\(a.boxName)）"))

                if a.isOut { returnSection(a) }
                if a.canLend { lendSection(a) }

                DisclosureGroup("タグの中身", isExpanded: $showRaw) {
                    VStack(alignment: .leading, spacing: 4) {
                        FieldRow(label: "タグID", value: lending.tag?.uid ?? "")
                        ForEach(Array((lending.tag?.records ?? []).enumerated()), id: \.offset) { _, r in
                            FieldRow(label: r.kind.rawValue, value: r.value)
                        }
                    }
                    .padding(.top, 6)
                }
                .font(.footnote)
            }
        }
    }

    @ViewBuilder
    private func returnSection(_ a: Asset) -> some View {
        Divider()
        VStack(alignment: .leading, spacing: 8) {
            Text("貸出先").font(.footnote).foregroundColor(.secondary)
            VStack(alignment: .leading, spacing: 2) {
                Text(a.borrower?.name ?? "").bold()
                if let c = a.borrower?.company, !c.isEmpty { Text(c).font(.footnote) }
                if let p = a.borrower?.phone, !p.isEmpty {
                    Link(p, destination: URL(string: "tel:" + p)!).font(.footnote)
                }
            }
            FieldRow(label: "貸出", value: a.checkedOutAt.isEmpty ? "" : "\(a.checkedOutAt)（\(a.elapsed)経過）")
            FieldRow(label: "返却予定", value: a.dueAt.isEmpty ? "指定なし" : a.dueAt)

            Text((a.totalKeys > 1 ? "\(a.totalKeys)本すべて揃っているか確かめて、" : "")
                 + (a.box.isEmpty ? "所定の位置に戻してから押してください。" : "\(a.box) に戻してから押してください。"))
                .font(.caption).foregroundColor(.secondary)

            Button {
                Task { await lending.returnKey(store: store); resetInputs() }
            } label: {
                Text(lending.busy ? "処理中…" : "返却する").frame(maxWidth: .infinity).padding(.vertical, 8)
            }
            .buttonStyle(.borderedProminent)
            .disabled(lending.busy)
        }
    }

    @ViewBuilder
    private func lendSection(_ a: Asset) -> some View {
        Divider()
        VStack(alignment: .leading, spacing: 10) {
            if !lending.borrowers.isEmpty {
                Text("貸出先").font(.footnote).foregroundColor(.secondary)
                ForEach(lending.borrowers) { b in
                    Button {
                        if selected?.id == b.id { selected = nil } else {
                            selected = b
                            newName = ""; newCompany = ""; newPhone = ""
                        }
                    } label: {
                        HStack {
                            VStack(alignment: .leading, spacing: 1) {
                                Text(b.name)
                                Text(b.subtitle).font(.caption).foregroundColor(.secondary)
                            }
                            Spacer()
                            if selected?.id == b.id {
                                Image(systemName: "checkmark.circle.fill").foregroundColor(.accentColor)
                            }
                        }
                        .padding(.vertical, 6)
                    }
                    .buttonStyle(.plain)
                }
            }

            DisclosureGroup("新しい貸出先を入力") {
                VStack(spacing: 8) {
                    TextField("お名前", text: $newName)
                    TextField("会社名（任意）", text: $newCompany)
                    TextField("電話番号（任意）", text: $newPhone).keyboardType(.phonePad)
                    Picker("区分", selection: $kind) {
                        ForEach(BorrowerKind.allCases) { k in Text(k.japanese).tag(k) }
                    }
                    .pickerStyle(.segmented)
                }
                .textFieldStyle(.roundedBorder)
                .padding(.top, 6)
                .onChange(of: newName) { _ in if !newName.isEmpty { selected = nil } }
            }
            .font(.footnote)

            Text("返却予定").font(.footnote).foregroundColor(.secondary)
            Picker("返却予定", selection: Binding(
                get: { due ?? lending.dues.first ?? DueOption() },
                set: { due = $0 })) {
                ForEach(lending.dues) { d in Text(d.label).tag(d) }
            }
            .pickerStyle(.menu)

            Button {
                Task {
                    await lending.checkout(selected: selected, newName: newName, newCompany: newCompany,
                                           newPhone: newPhone, kind: kind,
                                           due: due ?? lending.dues.first, store: store)
                    if !lending.messageIsError { resetInputs() }
                }
            } label: {
                Text(lending.busy ? "処理中…" : "貸出する").frame(maxWidth: .infinity).padding(.vertical, 8)
            }
            .buttonStyle(.borderedProminent)
            .disabled(lending.busy)
        }
        .onAppear { if due == nil { due = lending.dues.first } }
    }
}
