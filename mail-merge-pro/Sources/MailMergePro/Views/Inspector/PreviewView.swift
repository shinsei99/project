//
//  PreviewView.swift
//  MailMergePro
//
//  右カラム（インスペクタ）。選択中の受信者で {name} 等を置換した
//  実際の件名・本文プレビューを表示し、前へ／次へで切り替える。
//

import SwiftUI

struct PreviewView: View {
    @ObservedObject var viewModel: MailMergeViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("プレビュー", systemImage: "eye")
                .font(.headline)

            if viewModel.recipients.isEmpty {
                ContentUnavailableView(
                    "宛先を読み込むとプレビューできます",
                    systemImage: "eye.slash"
                )
            } else {
                // 受信者切り替え。
                navigator

                Divider()

                // 宛先。
                field(title: "宛先", value: viewModel.previewRecipient?.email ?? "")

                // 件名（置換後）。
                field(title: "件名", value: viewModel.previewSubject)

                // 本文（置換後）。
                VStack(alignment: .leading, spacing: 4) {
                    Text("本文")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    ScrollView {
                        Text(viewModel.previewBody)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .textSelection(.enabled)
                    }
                    .frame(maxHeight: .infinity)
                    .padding(8)
                    .background(.quinary, in: RoundedRectangle(cornerRadius: 6))
                }
            }
            Spacer()
        }
        .padding()
    }

    /// 「前へ / 1 / 132 / 次へ」の進捗ナビゲータ。
    private var navigator: some View {
        HStack {
            Button {
                viewModel.showPreviousPreview()
            } label: {
                Image(systemName: "chevron.left")
            }
            .disabled(viewModel.previewIndex <= 0)

            Spacer()
            Text("\(viewModel.previewIndex + 1) / \(viewModel.recipientCount)")
                .monospacedDigit()
                .foregroundStyle(.secondary)
            Spacer()

            Button {
                viewModel.showNextPreview()
            } label: {
                Image(systemName: "chevron.right")
            }
            .disabled(viewModel.previewIndex >= viewModel.recipientCount - 1)
        }
        .buttonStyle(.bordered)
    }

    /// ラベル付きの値表示行。
    private func field(title: String, value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(value)
                .textSelection(.enabled)
        }
    }
}
