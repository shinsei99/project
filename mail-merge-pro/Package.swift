// swift-tools-version:5.9
//
//  Package.swift
//  MailMergePro
//
//  開発・動作確認用の Swift Package 定義。
//  `swift build` / `swift run MailMergePro` で起動できる実行ターゲット。
//  ※ App Store（Sandbox）公開時は別途 Xcode プロジェクト化し、
//    Apple Events 自動化の権限（entitlement / Info.plist）を付与する。
//

import PackageDescription

let package = Package(
    name: "MailMergePro",
    platforms: [
        .macOS(.v14) // NavigationSplitView 3カラム・inspector・ContentUnavailableView 等を使用
    ],
    targets: [
        .executableTarget(
            name: "MailMergePro",
            path: "Sources/MailMergePro"
        )
    ]
)
