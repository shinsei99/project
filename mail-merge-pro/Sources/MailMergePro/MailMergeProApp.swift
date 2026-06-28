//
//  MailMergeProApp.swift
//  MailMergePro
//
//  アプリのエントリポイント（@main）。
//  SwiftUI App ライフサイクルでメインウィンドウを1枚表示する。
//

import SwiftUI

@main
struct MailMergeProApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        // macOS 標準のウィンドウスタイル。
        .windowStyle(.titleBar)
        .windowToolbarStyle(.unified)
        .commands {
            // 既定の「新規ウィンドウ」コマンドは不要なので抑制してもよいが、
            // 将来の複数ウィンドウ対応を見据えてここでは標準のままにしておく。
        }
    }
}
