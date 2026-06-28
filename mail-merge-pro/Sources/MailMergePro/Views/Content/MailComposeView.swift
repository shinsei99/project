//
//  MailComposeView.swift
//  MailMergePro
//
//  中央カラムの「メール作成」エリア。件名・本文を編集する。
//  本文には差し込みコード {name} 等をそのまま入力できる。
//

import SwiftUI

struct MailComposeView: View {
    @ObservedObject var viewModel: MailMergeViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("メール作成", systemImage: "square.and.pencil")
                .font(.headline)

            // 件名。
            VStack(alignment: .leading, spacing: 4) {
                Text("件名")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                TextField("件名を入力（例: {name} 様へのご案内）", text: $viewModel.subject)
                    .textFieldStyle(.roundedBorder)
            }

            // 本文。
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text("本文")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    Spacer()
                    Text("差し込みコード: {name}")
                        .font(.caption)
                        .foregroundStyle(.tertiary)
                }
                TextEditor(text: $viewModel.body)
                    .font(.body)
                    .frame(minHeight: 200)
                    .overlay(
                        RoundedRectangle(cornerRadius: 6)
                            .stroke(.quaternary, lineWidth: 1)
                    )
            }

            // 添付ファイル。
            AttachmentListView(viewModel: viewModel)
        }
        .padding()
    }
}
