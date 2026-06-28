//
//  SendResultView.swift
//  MailMergePro
//
//  送信完了画面。成功/失敗件数、失敗宛先一覧、結果 CSV エクスポート。
//

import SwiftUI
import UniformTypeIdentifiers

struct SendResultView: View {
    @ObservedObject var viewModel: MailMergeViewModel
    /// この画面を閉じるためのクロージャ。
    let onClose: () -> Void

    @State private var isExporterPresented = false

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("送信完了")
                .font(.title2.bold())

            if let summary = viewModel.summary {
                // 集計サマリ。
                HStack(spacing: 24) {
                    summaryBadge(count: summary.successCount, label: "成功", color: .green)
                    summaryBadge(count: summary.failureCount, label: "失敗", color: .red)
                    summaryBadge(count: summary.skippedCount, label: "対象外", color: .orange)
                    summaryBadge(count: summary.totalCount, label: "合計", color: .secondary)
                }

                // 失敗・対象外一覧。
                if summary.failedRows.isEmpty {
                    Label("すべて正常に送信しました", systemImage: "checkmark.circle.fill")
                        .foregroundStyle(.green)
                } else {
                    Text("失敗・対象外の宛先")
                        .font(.headline)
                    Table(summary.failedRows) {
                        TableColumn("名前", value: \.name)
                        TableColumn("メール", value: \.email)
                        TableColumn("状態") { Text($0.status.label) }
                        TableColumn("エラー内容") { Text($0.errorMessage ?? "") }
                    }
                    .frame(minHeight: 200)
                }

                // 操作ボタン。
                HStack {
                    Button {
                        isExporterPresented = true
                    } label: {
                        Label("結果ログを CSV 保存", systemImage: "square.and.arrow.up")
                    }
                    Spacer()
                    Button("閉じる") { onClose() }
                        .keyboardShortcut(.defaultAction)
                }
            }
        }
        .padding(24)
        .frame(minWidth: 560, minHeight: 420)
        // 結果 CSV のエクスポート先選択。
        .fileExporter(
            isPresented: $isExporterPresented,
            document: CSVDocument(text: csvText),
            contentType: .commaSeparatedText,
            defaultFilename: "送信結果"
        ) { result in
            if case .failure(let error) = result {
                viewModel.errorMessage = error.localizedDescription
            }
        }
    }

    /// 現在の集計から CSV テキストを得る。
    private var csvText: String {
        guard let summary = viewModel.summary else { return "" }
        return ResultExporter.csvString(from: summary)
    }

    /// 件数バッジ。
    private func summaryBadge(count: Int, label: String, color: Color) -> some View {
        VStack {
            Text("\(count)")
                .font(.system(size: 28, weight: .bold))
                .foregroundStyle(color)
            Text(label)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .frame(minWidth: 70)
    }
}

/// fileExporter 用に CSV をラップする最小の FileDocument。
/// （UTF-8 BOM 付きで書き出し、Excel での文字化けを防ぐ）
struct CSVDocument: FileDocument {
    static var readableContentTypes: [UTType] { [.commaSeparatedText] }

    var text: String

    init(text: String) { self.text = text }

    init(configuration: ReadConfiguration) throws {
        if let data = configuration.file.regularFileContents {
            self.text = String(decoding: data, as: UTF8.self)
        } else {
            self.text = ""
        }
    }

    func fileWrapper(configuration: WriteConfiguration) throws -> FileWrapper {
        var data = Data([0xEF, 0xBB, 0xBF]) // UTF-8 BOM
        data.append(Data(text.utf8))
        return FileWrapper(regularFileWithContents: data)
    }
}
