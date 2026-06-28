//
//  RecipientImportView.swift
//  MailMergePro
//
//  サイドバーの「宛先読込」セクション。
//  CSV のファイル選択・ドロップ、読込件数表示、一覧表示を担う。
//

import SwiftUI
import UniformTypeIdentifiers

struct RecipientImportView: View {
    @ObservedObject var viewModel: MailMergeViewModel

    /// ファイル選択パネルの表示状態。
    @State private var isImporterPresented = false

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // セクション見出し＋件数。
            HStack {
                Label("宛先", systemImage: "person.2")
                    .font(.headline)
                Spacer()
                Text("\(viewModel.recipientCount) 件")
                    .foregroundStyle(.secondary)
                    .font(.subheadline)
            }

            // 読込ボタン。
            Button {
                isImporterPresented = true
            } label: {
                Label("CSV を読み込む", systemImage: "square.and.arrow.down")
                    .frame(maxWidth: .infinity)
            }
            .controlSize(.large)

            // ドロップ領域＋一覧。
            recipientList
                // Finder からの CSV ドロップに対応。
                .dropDestination(for: URL.self) { urls, _ in
                    if let first = urls.first {
                        viewModel.importRecipients(from: first)
                        return true
                    }
                    return false
                }
        }
        .fileImporter(
            isPresented: $isImporterPresented,
            allowedContentTypes: [.commaSeparatedText, .plainText, UTType(filenameExtension: "csv") ?? .data],
            allowsMultipleSelection: false
        ) { result in
            switch result {
            case .success(let urls):
                if let url = urls.first { viewModel.importRecipients(from: url) }
            case .failure(let error):
                viewModel.errorMessage = error.localizedDescription
            }
        }
    }

    /// 宛先一覧（空時はドロップ案内）。
    @ViewBuilder
    private var recipientList: some View {
        if viewModel.recipients.isEmpty {
            ContentUnavailableView {
                Label("宛先がありません", systemImage: "tray")
            } description: {
                Text("CSV をドロップ、またはボタンから読み込んでください")
            }
            .frame(maxWidth: .infinity, minHeight: 120)
            .background(.quinary, in: RoundedRectangle(cornerRadius: 8))
        } else {
            List(viewModel.recipients) { recipient in
                HStack(spacing: 8) {
                    Image(systemName: recipient.status.systemImage)
                        .foregroundStyle(recipient.status.color)
                    VStack(alignment: .leading, spacing: 1) {
                        Text(recipient.name.isEmpty ? "(名前なし)" : recipient.name)
                        Text(recipient.email)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                }
            }
            .frame(minHeight: 160)
        }
    }
}
