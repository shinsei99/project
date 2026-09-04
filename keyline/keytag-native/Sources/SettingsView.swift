import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var store: Store

    @State private var serverURL = ""
    @State private var pairCode = ""
    @State private var message = ""
    @State private var messageIsError = false
    @State private var busy = false
    @State private var confirmClear = false

    var body: some View {
        NavigationView {
            Form {
                Section("タグの種類") {
                    Picker("タグ", selection: Binding(
                        get: { store.conf.tagType },
                        set: { store.conf.tagType = $0; store.saveConf() })) {
                        ForEach(NDEF.tagTypes, id: \.self) { t in
                            Text("\(t)（\(NDEF.capacity[t] ?? 0) バイト）").tag(t)
                        }
                    }
                    Text("書ける文字数が変わります。迷ったら NTAG213（もっとも一般的）。")
                        .font(.caption).foregroundColor(.secondary)
                }

                Section("サーバー連携（任意）") {
                    if store.conf.isLinked {
                        Label("\(store.conf.org.isEmpty ? "サーバー" : store.conf.org) と連携中",
                              systemImage: "checkmark.circle.fill")
                            .foregroundColor(.green)
                        Text(store.conf.server).font(.caption).foregroundColor(.secondary)
                        Button("接続を確認") { Task { await ping() } }.disabled(busy)
                        Button("連携をやめる", role: .destructive) {
                            store.conf.token = ""; store.conf.org = ""
                            store.saveConf()
                            say("連携をやめました。単体モードで動きます。")
                        }
                    } else {
                        TextField("サーバーのURL（例: http://192.168.1.20:8765）", text: $serverURL)
                            .keyboardType(.URL)
                            .autocapitalization(.none)
                            .disableAutocorrection(true)
                        TextField("6桁のコード", text: $pairCode).keyboardType(.numberPad)
                        Button("連携する") { Task { await pair() } }.disabled(busy)
                        Text("複数人で同じ台帳を見たいときだけ設定します。**設定しなくても全機能が使えます**（鍵の情報はこの端末に保存されます）。")
                            .font(.caption).foregroundColor(.secondary)
                    }
                    MessageLine(text: message, isError: messageIsError)
                }

                Section("お試し") {
                    Button("サンプルの鍵を5件入れる") {
                        store.addSamples()
                        say("サンプルを5件入れました。「台帳」を開いてみてください")
                    }
                    Text("NFCタグが手元になくても、台帳・貸出・返却の動きを確かめられます。")
                        .font(.caption).foregroundColor(.secondary)
                }

                Section("この端末の記録") {
                    Button("すべての記録を消す", role: .destructive) { confirmClear = true }
                        .confirmationDialog("この端末に保存した鍵の記録をすべて消します。よろしいですか？",
                                            isPresented: $confirmClear, titleVisibility: .visible) {
                            Button("すべて消す", role: .destructive) {
                                store.clearAll()
                                say("すべての記録を消しました")
                            }
                            Button("やめる", role: .cancel) {}
                        }
                }

                Section("このアプリについて") {
                    FieldRow(label: "バージョン", value: version)
                    Link("サーバー連携の公開仕様と参照実装",
                         destination: URL(string: "https://shinsei99.github.io/project/keytagnfc-support/")!)
                    Text("鍵や備品に貼ったNFCタグを読み書きして、貸出と返却を記録する業務用のアプリです。タグ自体にも内容を書くので、電波の届かない場所でも中身が読めます。")
                        .font(.caption).foregroundColor(.secondary)
                }
            }
            .navigationTitle("設定")
            .onAppear { if serverURL.isEmpty { serverURL = store.conf.server } }
        }
        .navigationViewStyle(.stack)
    }

    private var version: String {
        let v = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0"
        let b = Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "1"
        return "\(v)（build \(b)）"
    }

    private func pair() async {
        let url = serverURL.trimmingCharacters(in: .whitespaces)
            .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        guard !url.isEmpty else { say("サーバーのURLを入れてください", error: true); return }
        guard pairCode.count == 6, pairCode.allSatisfy(\.isNumber) else {
            say("6桁の数字を入れてください", error: true); return
        }
        busy = true
        defer { busy = false }
        do {
            let r = try await KeyTagAPI.pair(server: url, code: pairCode)
            store.conf.server = url
            store.conf.token = r.token ?? ""
            store.conf.org = r.organization ?? ""
            store.saveConf()
            pairCode = ""
            say("\(store.conf.org.isEmpty ? "サーバー" : store.conf.org) と連携しました")
        } catch {
            say("接続できません。URLと、同じWi-Fiに繋がっているか確認してください。", error: true)
        }
    }

    private func ping() async {
        busy = true
        defer { busy = false }
        let api = KeyTagAPI(server: store.conf.server, token: store.conf.token)
        do {
            let r = try await api.ping()
            say("\(r.organization ?? "")（\(r.user ?? "")）に接続できました")
        } catch {
            say("接続できません。連携をやり直してください。", error: true)
        }
    }

    private func say(_ text: String, error: Bool = false) {
        message = text
        messageIsError = error
    }
}
