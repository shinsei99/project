import SwiftUI

@main
struct KeyTagApp: App {
    @StateObject private var store = Store()
    @StateObject private var router = Router()
    @StateObject private var lending = LendingModel()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(store)
                .environmentObject(router)
                .environmentObject(lending)
                .onAppear(perform: applyDebugLaunchOptions)
        }
    }
}

extension KeyTagApp {
    /// 開発ビルドだけの起動オプション。**`#if DEBUG` なので配信物には入らない。**
    ///
    /// なぜ要るか: シミュレータのウインドウを掴めない環境では画面をタップで切り替えられず、
    /// 「直したかどうかを目で見る」ができない（`simtap.py` が System Events で止まる）。
    /// 起動時に開く画面とサンプル投入を指定できれば、撮るだけで各画面を確認できる。
    ///
    ///   xcrun simctl launch --console booted com.shinsei99.keytag \
    ///       KEYTAG_TAB=ledger KEYTAG_SAMPLES=1
    func applyDebugLaunchOptions() {
        #if DEBUG
        let env = ProcessInfo.processInfo.environment
        if env["KEYTAG_SAMPLES"] == "1", store.ledger.isEmpty { store.addSamples() }
        // 貸出・返却の画面は台帳の行をタップして開くので、ここからも開けるようにする
        switch env["KEYTAG_OPEN"] {
        case "out":
            if let r = store.ledger.first(where: { $0.status == .out }) {
                lending.openLocal(r, store: store); router.tab = .read
            }
        case "in":
            if let r = store.ledger.first(where: { $0.status == .inStock }) {
                lending.openLocal(r, store: store); router.tab = .read
            }
        default: break
        }
        // 書き込み画面を「入力済み」の状態で開く（空の入力欄はストア用の絵にならない）
        if env["KEYTAG_DRAFT"] == "1" {
            router.openWrite(with: .init(property: "本社ビル", name: "1階エントランス",
                                         numbers: "10001 / 10002 / 10003 ×3",
                                         boxCode: "BOX-01", boxPosition: "01"))
        }
        switch env["KEYTAG_TAB"] {
        case "write": router.tab = .write
        case "ledger": router.tab = .ledger
        case "settings": router.tab = .settings
        case "read": router.tab = .read
        default: break
        }
        #endif
    }
}

/// ストア用スクショを撮るときだけ立てる印。**`#if DEBUG` なので配信物では常に false。**
///
/// なぜ要るか: シミュレータには NFC が無いので「この端末ではNFCを使えません」という
/// 注意書きが出る。**実機では絶対に出ない文言**なので、そのまま撮るとストアの絵が
/// 実物と食い違う。実機と同じ絵を撮るために、この印が立っているあいだだけ隠す。
enum ShotMode {
    static var on: Bool {
        #if DEBUG
        return ProcessInfo.processInfo.environment["KEYTAG_SHOTS"] == "1"
        #else
        return false
        #endif
    }
}

/// 画面のあいだの受け渡し（タブ切り替えと、書き込み画面への下書き）。
@MainActor
final class Router: ObservableObject {
    enum Tab: Hashable { case read, write, ledger, settings }

    @Published var tab: Tab = .read
    /// 「この鍵を登録する」「再書込」で書き込み画面に持っていく内容
    @Published var draft: Draft?

    struct Draft: Equatable {
        var property = ""
        var name = ""
        var numbers = ""
        var boxCode = ""
        var boxPosition = ""
    }

    func openWrite(with draft: Draft) {
        self.draft = draft
        tab = .write
    }
}

struct RootView: View {
    @EnvironmentObject private var router: Router

    var body: some View {
        TabView(selection: $router.tab) {
            ReadView()
                .tabItem { Label("読み取り", systemImage: "wave.3.right") }
                .tag(Router.Tab.read)
            WriteView()
                .tabItem { Label("書き込み", systemImage: "square.and.pencil") }
                .tag(Router.Tab.write)
            LedgerView()
                .tabItem { Label("台帳", systemImage: "list.bullet.rectangle") }
                .tag(Router.Tab.ledger)
            SettingsView()
                .tabItem { Label("設定", systemImage: "gearshape") }
                .tag(Router.Tab.settings)
        }
    }
}
