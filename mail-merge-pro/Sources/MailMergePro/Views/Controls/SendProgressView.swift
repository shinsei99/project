//
//  SendProgressView.swift
//  MailMergePro
//
//  送信中に表示するモーダル。進捗バー、現在の宛先、キャンセルボタン。
//

import SwiftUI

struct SendProgressView: View {
    @ObservedObject var viewModel: MailMergeViewModel

    var body: some View {
        VStack(spacing: 20) {
            Text("送信中…")
                .font(.title2.bold())

            // 進捗バー（0〜totalToSend）。
            ProgressView(
                value: Double(viewModel.sentProgress),
                total: Double(max(viewModel.totalToSend, 1))
            )
            .frame(width: 360)

            // 「58 / 132 現在送信中: 山田太郎」
            VStack(spacing: 4) {
                Text("\(viewModel.sentProgress) / \(viewModel.totalToSend)")
                    .font(.headline)
                    .monospacedDigit()
                if !viewModel.currentRecipientName.isEmpty {
                    Text("現在送信中: \(viewModel.currentRecipientName)")
                        .foregroundStyle(.secondary)
                }
            }

            // 送信全体のキャンセル。
            Button(role: .destructive) {
                viewModel.cancelSend()
            } label: {
                Label("送信を中止", systemImage: "stop.circle")
            }
            .controlSize(.large)
        }
        .padding(40)
        .frame(minWidth: 440)
    }
}
