//
//  SendControlBar.swift
//  MailMergePro
//
//  画面下部のコントロールバー。
//  ・テスト送信（自分宛て）
//  ・本番送信（テスト成功まで無効、押下で確認ダイアログ）
//

import SwiftUI

struct SendControlBar: View {
    @ObservedObject var viewModel: MailMergeViewModel

    /// 本番送信の確認ダイアログ表示状態。
    @State private var isConfirmPresented = false

    var body: some View {
        HStack(spacing: 16) {
            // 送信元アカウント選択。
            HStack(spacing: 6) {
                Image(systemName: "person.crop.circle")
                    .foregroundStyle(.secondary)
                Picker("送信元", selection: $viewModel.selectedAccount) {
                    if viewModel.accounts.isEmpty {
                        Text("アカウントなし").tag(Optional<MailAccount>.none)
                    } else {
                        Text("選択してください").tag(Optional<MailAccount>.none)
                        ForEach(viewModel.accounts) { account in
                            Text(account.displayName).tag(Optional(account))
                        }
                    }
                }
                .labelsHidden()
                .frame(maxWidth: 240)

                // アカウント再読込。
                Button {
                    viewModel.loadAccounts()
                } label: {
                    Image(systemName: "arrow.clockwise")
                }
                .buttonStyle(.borderless)
                .help("送信元アカウントを再読込")
            }

            Divider().frame(height: 24)

            // テスト送信エリア。
            HStack(spacing: 8) {
                TextField("自分のメールアドレス", text: $viewModel.testAddress)
                    .textFieldStyle(.roundedBorder)
                    .frame(width: 220)

                Button {
                    Task { await viewModel.sendTest() }
                } label: {
                    Label("テスト送信", systemImage: "paperplane")
                }
                .disabled(!viewModel.canSendTest)

                // テスト成功インジケータ。
                if viewModel.testSucceeded {
                    Label("テスト成功", systemImage: "checkmark.seal.fill")
                        .foregroundStyle(.green)
                        .font(.caption)
                }
            }

            Spacer()

            // 本番送信ボタン（テスト成功まで無効）。
            Button {
                isConfirmPresented = true
            } label: {
                Label("本番送信（\(viewModel.recipientCount)件）", systemImage: "paperplane.fill")
                    .padding(.horizontal, 4)
            }
            .controlSize(.large)
            .buttonStyle(.borderedProminent)
            .disabled(!viewModel.canSendProduction)
            .help(viewModel.testSucceeded ? "一斉送信を開始します" : "先にテスト送信を成功させてください")
        }
        .padding(.horizontal)
        .padding(.vertical, 10)
        .background(.bar)
        // 送信前確認ダイアログ：件数・件名・添付数を提示。
        .confirmationDialog(
            "本番送信を開始しますか？",
            isPresented: $isConfirmPresented,
            titleVisibility: .visible
        ) {
            Button("送信を開始", role: .destructive) {
                viewModel.startProductionSend()
            }
            Button("キャンセル", role: .cancel) {}
        } message: {
            Text("""
            送信元: \(viewModel.selectedAccount?.email ?? "未選択")
            送信件数: \(viewModel.recipientCount) 件
            件名: \(viewModel.subject)
            添付ファイル: \(viewModel.attachments.count) 個
            """)
        }
    }
}
