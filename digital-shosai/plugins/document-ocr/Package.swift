// swift-tools-version: 5.9
import PackageDescription

// デジタル書斎の中だけで使うローカルプラグイン。
// **`ios/` は gitignore なので、ネイティブのコードはここに置く**（`npx cap add ios` で
// プロジェクトを作り直しても消えない）。実体は `npm install ./plugins/document-ocr` →
// `npx cap sync ios` で CapApp-SPM に取り込まれる。
let package = Package(
    name: "DocumentOcr",
    platforms: [.iOS(.v15)],
    products: [
        .library(
            name: "DocumentOcr",
            targets: ["DocumentOCRPlugin"])
    ],
    dependencies: [
        .package(url: "https://github.com/ionic-team/capacitor-swift-pm.git", from: "8.0.0")
    ],
    targets: [
        .target(
            name: "DocumentOCRPlugin",
            dependencies: [
                .product(name: "Capacitor", package: "capacitor-swift-pm"),
                .product(name: "Cordova", package: "capacitor-swift-pm")
            ],
            path: "ios/Sources/DocumentOCRPlugin")
    ]
)
