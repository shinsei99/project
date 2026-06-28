//
//  TemplateListView.swift
//  MailMergePro
//
//  サイドバーの「テンプレート」セクション。
//  一覧表示、追加・削除・リネーム、クリックで件名/本文へ反映。
//

import SwiftUI

struct TemplateListView: View {
    @ObservedObject var viewModel: MailMergeViewModel

    /// リネーム対象のテンプレートと入力中の名前。
    @State private var renamingTemplate: Template?
    @State private var renameText: String = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Label("テンプレート", systemImage: "doc.text")
                    .font(.headline)
                Spacer()
                // 追加ボタン。
                Button {
                    viewModel.addTemplate()
                } label: {
                    Image(systemName: "plus")
                }
                .buttonStyle(.borderless)
                .help("テンプレートを追加")

                // 現在の内容を選択中テンプレートへ保存。
                Button {
                    viewModel.saveCurrentIntoSelectedTemplate()
                } label: {
                    Image(systemName: "square.and.arrow.down")
                }
                .buttonStyle(.borderless)
                .disabled(viewModel.selectedTemplateID == nil)
                .help("現在の件名・本文を選択中テンプレートへ保存")
            }

            if viewModel.templates.isEmpty {
                Text("「＋」でテンプレートを追加できます")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            } else {
                List(selection: $viewModel.selectedTemplateID) {
                    ForEach(viewModel.templates) { template in
                        templateRow(template)
                            .tag(template.id)
                    }
                }
                .frame(minHeight: 120)
            }
        }
        // リネーム用の入力シート。
        .sheet(item: $renamingTemplate) { template in
            renameSheet(for: template)
        }
    }

    /// テンプレート1行。クリックで反映、右クリックでメニュー。
    private func templateRow(_ template: Template) -> some View {
        HStack {
            Text(template.name)
            Spacer()
        }
        .contentShape(Rectangle())
        .onTapGesture {
            viewModel.applyTemplate(template)
        }
        .contextMenu {
            Button("件名・本文に反映") { viewModel.applyTemplate(template) }
            Button("名前を変更…") {
                renameText = template.name
                renamingTemplate = template
            }
            Divider()
            Button("削除", role: .destructive) { viewModel.deleteTemplate(template) }
        }
    }

    /// リネーム入力シート。
    private func renameSheet(for template: Template) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("テンプレート名を変更")
                .font(.headline)
            TextField("名前", text: $renameText)
                .textFieldStyle(.roundedBorder)
                .frame(width: 280)
            HStack {
                Spacer()
                Button("キャンセル") { renamingTemplate = nil }
                Button("変更") {
                    viewModel.renameTemplate(template, to: renameText)
                    renamingTemplate = nil
                }
                .keyboardShortcut(.defaultAction)
                .disabled(renameText.trimmingCharacters(in: .whitespaces).isEmpty)
            }
        }
        .padding(20)
    }
}
