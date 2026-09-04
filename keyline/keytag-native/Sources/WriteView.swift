import SwiftUI

struct WriteView: View {
    @EnvironmentObject private var store: Store
    @EnvironmentObject private var router: Router

    @State private var property = ""
    @State private var name = ""
    @State private var boxCode = ""
    @State private var boxPosition = ""
    @State private var keys: [KeyEntry] = [KeyEntry()]
    @State private var message = ""
    @State private var messageIsError = false
    @State private var writing = false
    @State private var nfc = NFCService()

    struct KeyEntry: Identifiable, Equatable {
        var id = UUID()
        var number = ""
        var quantity = 1
    }

    private var fields: NDEF.Fields {
        NDEF.Fields(property: property.trimmingCharacters(in: .whitespaces),
                    name: name.trimmingCharacters(in: .whitespaces),
                    numbers: numbersText,
                    boxCode: boxCode.trimmingCharacters(in: .whitespaces),
                    boxPosition: boxPosition.trimmingCharacters(in: .whitespaces),
                    url: "")
    }

    private var numbersText: String {
        keys.filter { !$0.number.trimmingCharacters(in: .whitespaces).isEmpty }
            .map { $0.quantity > 1 ? "\($0.number) ×\($0.quantity)" : $0.number }
            .joined(separator: " / ")
    }

    private var plan: NDEF.Plan { NDEF.plan(fields, tagType: store.conf.tagType) }

    var body: some View {
        NavigationView {
            Form {
                Section("鍵の情報") {
                    TextField("物件名（任意）", text: $property)
                    if !store.propertyNames.isEmpty {
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 6) {
                                ForEach(store.propertyNames, id: \.self) { p in
                                    Button(p) { property = p }
                                        .font(.caption)
                                        .buttonStyle(.bordered)
                                }
                            }
                        }
                    }
                    TextField("鍵の名称（例: 101号室 玄関）", text: $name)
                }

                Section("鍵番号と本数") {
                    ForEach($keys) { $k in
                        HStack {
                            TextField("10001", text: $k.number)
                            Text("×").foregroundColor(.secondary)
                            Stepper(value: $k.quantity, in: 1...99) {
                                Text("\(k.quantity) 本").frame(width: 56, alignment: .leading)
                            }
                            .labelsHidden()
                            Text("\(k.quantity) 本").font(.footnote).foregroundColor(.secondary)
                            if keys.count > 1 {
                                Button {
                                    keys.removeAll { $0.id == k.id }
                                } label: { Image(systemName: "minus.circle.fill").foregroundColor(.red) }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                    Button {
                        keys.append(KeyEntry())
                    } label: { Label("鍵番号を追加", systemImage: "plus.circle") }
                }

                Section("保管場所") {
                    TextField("ボックス（例: BOX-01）", text: $boxCode)
                    TextField("位置（例: 03）", text: $boxPosition)
                    Button("物件名・保管場所を消す") {
                        property = ""; boxCode = ""; boxPosition = ""
                    }
                    .font(.footnote)
                }

                Section("タグに書かれる内容") {
                    VStack(alignment: .leading, spacing: 8) {
                        Text(plan.text.isEmpty ? "（まだ何も入力されていません）" : plan.text)
                            .font(.callout)
                        ProgressView(value: plan.percent)
                            .tint(!plan.fits ? .red : (plan.truncated ? .orange : .accentColor))
                        Text("\(plan.bytes) / \(plan.capacity) バイト（\(store.conf.tagType)）")
                            .font(.caption).foregroundColor(.secondary)
                        if plan.truncated && plan.fits {
                            Text("容量が足りないため名前を短くします。鍵番号と保管場所は必ず残ります。")
                                .font(.caption).foregroundColor(.orange)
                        }
                        if !plan.fits {
                            Text("このタグには収まりません。設定でタグの種類を変えるか、名前を短くしてください。")
                                .font(.caption).foregroundColor(.red)
                        }
                    }
                }

                Section {
                    Button {
                        Task { await write() }
                    } label: {
                        HStack {
                            Image(systemName: "square.and.arrow.down.on.square")
                            Text(writing ? "タグに近づけてください…" : "タグに書き込む").bold()
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 6)
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(writing || !plan.fits)

                    MessageLine(text: message, isError: messageIsError)

                    if store.conf.isLinked {
                        Label("書き込む前に \(store.conf.org.isEmpty ? "サーバー" : store.conf.org) へ登録します",
                              systemImage: "network")
                            .font(.caption).foregroundColor(.secondary)
                    }
                }
            }
            .navigationTitle("書き込み")
            .onAppear(perform: applyDraft)
            .onChange(of: router.draft) { _ in applyDraft() }
        }
        .navigationViewStyle(.stack)
    }

    private func applyDraft() {
        guard let d = router.draft else { return }
        property = d.property
        name = d.name
        boxCode = d.boxCode
        boxPosition = d.boxPosition
        keys = parseNumbers(d.numbers)
        router.draft = nil
    }

    /// `10001 / 10003 ×3` を入力欄の形に戻す。
    private func parseNumbers(_ s: String) -> [KeyEntry] {
        let parts = s.components(separatedBy: " / ").filter { !$0.isEmpty }
        let entries: [KeyEntry] = parts.map { part in
            if let r = part.range(of: #"\s*×\s*\d+$"#, options: .regularExpression) {
                let qty = Int(part[r].replacingOccurrences(of: "×", with: "")
                    .trimmingCharacters(in: .whitespaces)) ?? 1
                return KeyEntry(number: String(part[part.startIndex..<r.lowerBound])
                    .trimmingCharacters(in: .whitespaces), quantity: qty)
            }
            return KeyEntry(number: part.trimmingCharacters(in: .whitespaces), quantity: 1)
        }
        return entries.isEmpty ? [KeyEntry()] : entries
    }

    // MARK: - 書き込み

    private func write() async {
        message = ""; messageIsError = false
        var f = fields
        guard !f.name.isEmpty else {
            message = "鍵の名称を入れてください"; messageIsError = true
            return
        }
        writing = true
        defer { writing = false }

        // 連携が設定されていれば、先にサーバーへ登録してURLを受け取る。
        // 失敗しても単体の書き込みは続ける（現場を止めないため）。
        if store.conf.isLinked {
            let api = KeyTagAPI(server: store.conf.server, token: store.conf.token)
            let entries = keys.filter { !$0.number.trimmingCharacters(in: .whitespaces).isEmpty }
            do {
                if let url = try await api.register(property: f.property, name: f.name,
                                                    boxPosition: f.boxPosition,
                                                    numbers: entries.map(\.number),
                                                    quantities: entries.map(\.quantity)) {
                    f.url = url
                }
            } catch {
                message = "サーバーに登録できませんでした。タグにはこの端末の情報だけ書きます。"
                messageIsError = true
            }
        }

        let p = NDEF.plan(f, tagType: store.conf.tagType)
        guard p.fits else {
            message = "このタグには収まりません"; messageIsError = true
            return
        }

        do {
            let tag = try await nfc.write(p.records, capacity: p.capacity)
            store.addToLedger(f, plan: p, uid: tag.uid)
            message = "書き込みました：" + (p.text.isEmpty ? "URLのみ" : p.text)
            messageIsError = false
            // 次の鍵へ。物件名・ボックスは残し、位置を繰り上げる
            name = ""
            keys = [KeyEntry()]
            boxPosition = NDEF.nextPosition(boxPosition)
        } catch let e as NFCError {
            if case .canceled = e { return }
            message = e.localizedDescription; messageIsError = true
        } catch {
            message = error.localizedDescription; messageIsError = true
        }
    }
}
