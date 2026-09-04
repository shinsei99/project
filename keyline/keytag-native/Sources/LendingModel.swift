import Foundation

/// 貸出・返却の状態。
///
/// ★データの置き場は2つある。画面は同じで、ここだけが違う。
///   local  … この端末の台帳。サーバー不要。**これが既定**
///   server … 自社の鍵管理サーバー（設定で連携したときだけ）。
///            二重貸出の判定はサーバー側でやるので、2台で同時に操作しても壊れない。
@MainActor
final class LendingModel: ObservableObject {

    enum Source: Equatable {
        case server(token: String)
        case local(id: String)
    }

    @Published var tag: TagRead?
    @Published var source: Source?
    @Published var asset: Asset?
    @Published var borrowers: [BorrowerOption] = []
    @Published var dues: [DueOption] = []
    @Published var message = ""
    @Published var messageIsError = false
    @Published var busy = false
    /// 読めたが台帳にもサーバーにも無いタグ（＝これから登録する鍵）
    @Published var unregistered = false

    var isActive: Bool { asset != nil }

    func clear() {
        tag = nil; source = nil; asset = nil
        borrowers = []; dues = []
        message = ""; messageIsError = false; unregistered = false
    }

    private func say(_ text: String, error: Bool = false) {
        message = text
        messageIsError = error
    }

    // MARK: - かざした結果を開く

    func present(tag t: TagRead, store: Store) async {
        clear()
        tag = t

        // ① サーバー連携していて、そのサーバーのタグなら、サーバーを見る
        if let token = NDEF.keylineToken(t.url), store.conf.isLinked {
            let api = KeyTagAPI(server: store.conf.server, token: store.conf.token)
            do {
                let r = try await api.asset(token: token)
                if r.found == true, let a = r.asset {
                    source = .server(token: token)
                    asset = a
                    borrowers = r.borrowers ?? []
                    dues = r.dues ?? store.localDues()
                    return
                }
                say("このタグはサーバーに登録されていません。", error: false)
            } catch {
                say("サーバーに繋がりませんでした。この端末の記録で操作します。", error: true)
            }
        }

        // ② それ以外は端末内の台帳で操作する（サーバー不要）
        guard let rec = store.findLocal(t) else {
            unregistered = true
            return
        }
        openLocal(rec, store: store)
    }

    /// 台帳の行から直接開く（タグを持っていないときの確認用）。
    func openLocal(_ rec: KeyRecord, store: Store) {
        tag = tag ?? TagRead(uid: rec.uid, url: rec.url.isEmpty ? nil : rec.url)
        source = .local(id: rec.id)
        asset = store.asset(for: rec)
        borrowers = store.localBorrowers()
        dues = store.localDues()
        unregistered = false
    }

    // MARK: - 貸出

    func checkout(selected: BorrowerOption?, newName: String, newCompany: String,
                  newPhone: String, kind: BorrowerKind, due: DueOption?, store: Store) async {
        guard let source else { return }
        let name = newName.trimmingCharacters(in: .whitespaces)
        if selected == nil && name.isEmpty {
            say("貸出先を選ぶか、お名前を入力してください", error: true)
            return
        }
        busy = true
        defer { busy = false }

        switch source {
        case .server(let token):
            let api = KeyTagAPI(server: store.conf.server, token: store.conf.token)
            do {
                let a = try await api.checkout(tagToken: token, borrowerID: selected?.id ?? "",
                                               newName: name, newKind: kind.rawValue,
                                               newCompany: newCompany, newPhone: newPhone,
                                               dueAt: due?.value ?? "")
                asset = a
                say("貸出しました")
            } catch {
                say(error.localizedDescription, error: true)
            }

        case .local(let id):
            let borrower: Borrower = {
                if let s = selected {
                    return Borrower(name: s.name, company: s.company, kind: s.kind, phone: "")
                }
                return Borrower(name: name, company: newCompany, kind: kind.japanese, phone: newPhone)
            }()
            do {
                let rec = try store.checkoutLocal(id: id, borrower: borrower, due: due?.value ?? "")
                asset = store.asset(for: rec)
                say("貸出しました")
            } catch {
                say(error.localizedDescription, error: true)
            }
        }
    }

    // MARK: - 返却

    func returnKey(store: Store) async {
        guard let source else { return }
        busy = true
        defer { busy = false }

        switch source {
        case .server(let token):
            let api = KeyTagAPI(server: store.conf.server, token: store.conf.token)
            do {
                let a = try await api.returnKey(tagToken: token)
                // 返却後は貸出先の候補を取り直す（直近に借りた人が上に来るように）
                if let fresh = try? await api.asset(token: token), fresh.found == true, let fa = fresh.asset {
                    asset = fa
                    borrowers = fresh.borrowers ?? borrowers
                    dues = fresh.dues ?? dues
                } else {
                    asset = a
                }
                say("返却しました")
            } catch {
                say(error.localizedDescription, error: true)
            }

        case .local(let id):
            do {
                let rec = try store.returnLocal(id: id)
                asset = store.asset(for: rec)
                borrowers = store.localBorrowers()
                dues = store.localDues()
                say("返却しました")
            } catch {
                say(error.localizedDescription, error: true)
            }
        }
    }
}
