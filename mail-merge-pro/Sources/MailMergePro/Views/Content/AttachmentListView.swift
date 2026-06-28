//
//  AttachmentListView.swift
//  MailMergePro
//
//  添付ファイルエリア。複数ファイルのドラッグ＆ドロップ／選択、一覧表示、削除。
//

import SwiftUI

struct AttachmentListView: View {
    @ObservedObject var viewModel: MailMergeViewModel

    @State private var isImporterPresented = false

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Label("添付ファイル", systemImage: "paperclip")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                Spacer()
                Button {
                    isImporterPresented = true
                } label: {
                    Label("追加", systemImage: "plus")
                }
                .buttonStyle(.borderless)
            }

            if viewModel.attachments.isEmpty {
                Text("ここにファイルをドラッグ＆ドロップ、または「追加」")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 44)
                    .background(.quinary, in: RoundedRectangle(cornerRadius: 6))
            } else {
                VStack(spacing: 2) {
                    ForEach(viewModel.attachments) { attachment in
                        attachmentRow(attachment)
                    }
                }
            }
        }
        // 複数ファイルのドロップに対応。
        .dropDestination(for: URL.self) { urls, _ in
            viewModel.addAttachments(urls)
            return !urls.isEmpty
        }
        .fileImporter(
            isPresented: $isImporterPresented,
            allowedContentTypes: [.item],
            allowsMultipleSelection: true
        ) { result in
            if case .success(let urls) = result {
                viewModel.addAttachments(urls)
            }
        }
    }

    /// 添付1行。紛失時は赤字で警告。
    private func attachmentRow(_ attachment: Attachment) -> some View {
        HStack {
            Image(systemName: attachment.fileExists ? "doc" : "exclamationmark.triangle.fill")
                .foregroundStyle(attachment.fileExists ? Color.secondary : Color.red)
            VStack(alignment: .leading, spacing: 0) {
                Text(attachment.fileName)
                Text(attachment.fileExists ? attachment.humanReadableSize : "ファイルが見つかりません")
                    .font(.caption)
                    .foregroundStyle(attachment.fileExists ? Color.secondary : Color.red)
            }
            Spacer()
            Button {
                viewModel.removeAttachment(attachment)
            } label: {
                Image(systemName: "xmark.circle.fill")
                    .foregroundStyle(.secondary)
            }
            .buttonStyle(.borderless)
        }
        .padding(.vertical, 2)
    }
}
