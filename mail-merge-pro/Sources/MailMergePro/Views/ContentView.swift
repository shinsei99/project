//
//  ContentView.swift
//  MailMergePro
//
//  アプリのルート画面。macOS 標準の NavigationSplitView による3ペイン構成。
//  ・サイドバー: 宛先読込 + テンプレート
//  ・コンテンツ: メール作成（件名・本文・添付）
//  ・インスペクタ: 差し込み後プレビュー
//  下部にコントロールバー、送信中・完了はシートで提示する。
//

import SwiftUI

struct ContentView: View {
    /// 画面全体の状態を持つ ViewModel。
    @StateObject private var viewModel = MailMergeViewModel()

    var body: some View {
        NavigationSplitView {
            // 左カラム：操作系。
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    RecipientImportView(viewModel: viewModel)
                    Divider()
                    TemplateListView(viewModel: viewModel)
                }
                .padding()
            }
            .navigationSplitViewColumnWidth(min: 260, ideal: 300, max: 360)
        } content: {
            // 中央カラム：メール作成。
            ScrollView {
                MailComposeView(viewModel: viewModel)
            }
            .navigationSplitViewColumnWidth(min: 360, ideal: 480)
        } detail: {
            // 右カラム：プレビュー。
            PreviewView(viewModel: viewModel)
                .navigationSplitViewColumnWidth(min: 300, ideal: 360)
        }
        .navigationTitle("Mail Merge Pro")
        // 下部コントロールバー。
        .safeAreaInset(edge: .bottom) {
            SendControlBar(viewModel: viewModel)
        }
        // 起動時にテンプレートと送信元アカウントを読込。
        .task {
            viewModel.loadTemplates()
            viewModel.loadAccounts()
        }
        // 送信中モーダル。
        .sheet(isPresented: .constant(viewModel.isSending)) {
            SendProgressView(viewModel: viewModel)
                .interactiveDismissDisabled() // 誤って閉じられないように。
        }
        // 送信完了モーダル（summary が出たら表示）。
        .sheet(isPresented: Binding(
            get: { viewModel.summary != nil && !viewModel.isSending },
            set: { if !$0 { viewModel.summary = nil } }
        )) {
            SendResultView(viewModel: viewModel) {
                viewModel.summary = nil
            }
        }
        // エラーアラート（全 Service 共通の出口）。
        .alert(
            "エラー",
            isPresented: Binding(
                get: { viewModel.errorMessage != nil },
                set: { if !$0 { viewModel.errorMessage = nil } }
            )
        ) {
            Button("OK", role: .cancel) { viewModel.errorMessage = nil }
        } message: {
            Text(viewModel.errorMessage ?? "")
        }
        .frame(minWidth: 1000, minHeight: 640)
    }
}
