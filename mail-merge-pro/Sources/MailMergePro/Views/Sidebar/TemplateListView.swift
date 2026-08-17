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

    /// 「名前を付けて保存」シートの表示状態と入力中の名前。
    @State private var isSavingNew: Bool = false
    @State private var newTemplateName: String = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("テンプレート", systemImage: "doc.text")
                .font(.headline)

            // 目立つメインボタン：今の件名・本文をテンプレートとして保存。
            Button {
                newTemplateName = ""
                isSavingNew = true
            } label: {
                Label("このメールをテンプレート保存", systemImage: "square.and.arrow.down")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .disabled(!viewModel.hasComposableContent)
            .help("現在の件名・本文に名前を付けて、新しいテンプレートとして保存します")

            // 補助操作：選択中への上書き保存。
            Button {
                viewModel.saveCurrentIntoSelectedTemplate()
            } label: {
                Label("選択中のテンプレートに上書き保存", systemImage: "arrow.down.doc")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
            .disabled(viewModel.selectedTemplateID == nil)
            .help("いま選んでいるテンプレートを、現在の件名・本文で上書きします")

            Divider()

            if viewModel.templates.isEmpty {
                Text("上の「テンプレート保存」ボタンで、いまのメールを保存できます。保存したテンプレートはここに一覧表示されます。")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            } else {
                Text("保存済みテンプレート（クリックで呼び出し）")
                    .font(.caption)
                    .foregroundStyle(.secondary)
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
        // 「名前を付けて保存」用の入力シート。
        .sheet(isPresented: $isSavingNew) {
            saveNewSheet()
        }
    }

    /// 「名前を付けて保存」入力シート。
    private func saveNewSheet() -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("テンプレートとして保存")
                .font(.headline)
            Text("現在の件名・本文を新しいテンプレートとして保存します。")
                .font(.caption)
                .foregroundStyle(.secondary)
            TextField("テンプレート名", text: $newTemplateName)
                .textFieldStyle(.roundedBorder)
                .frame(width: 280)
            HStack {
                Spacer()
                Button("キャンセル") { isSavingNew = false }
                Button("保存") {
                    viewModel.saveAsNewTemplate(name: newTemplateName)
                    isSavingNew = false
                }
                .keyboardShortcut(.defaultAction)
                .disabled(newTemplateName.trimmingCharacters(in: .whitespaces).isEmpty)
            }
        }
        .padding(20)
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
