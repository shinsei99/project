//
//  MailComposeView.swift
//  MailMergePro
//
//  中央カラムの「メール作成」エリア。件名・本文を編集する。
//  本文には差し込みコード {name} 等をそのまま入力できるほか、
//  「差し込み」ボタンでカーソル位置に挿入できる。
//

import SwiftUI
import AppKit

struct MailComposeView: View {
    @ObservedObject var viewModel: MailMergeViewModel

    /// 本文エディタ操作用コントローラ（差し込み挿入で使用）。
    @State private var bodyController = BodyEditorController()

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("メール作成", systemImage: "square.and.pencil")
                .font(.headline)

            // 差し込みコード挿入バー。
            mergeFieldBar

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
                Text("本文")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                BodyEditor(text: $viewModel.body, controller: bodyController)
                    .frame(minHeight: 200)
            }

            // 添付ファイル。
            AttachmentListView(viewModel: viewModel)
        }
        .padding()
    }

    // MARK: - 差し込みバー

    /// 差し込みコードを挿入するボタン列。
    /// 件名・本文のうち、いまカーソルがある方へ挿入する。
    private var mergeFieldBar: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("差し込み（件名・本文のカーソル位置に挿入）")
                .font(.caption)
                .foregroundStyle(.secondary)
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    ForEach(viewModel.availableMergeKeys, id: \.self) { key in
                        Button {
                            insert("{\(key)}")
                        } label: {
                            Label(displayLabel(for: key), systemImage: "plus.circle")
                        }
                        .buttonStyle(.bordered)
                        .focusable(false)          // クリックで入力欄のフォーカスを奪わない
                        .help("{\(key)} をカーソル位置に挿入します")
                    }
                }
                .padding(.vertical, 1)
            }
        }
    }

    /// 差し込みキーの表示ラベル。
    private func displayLabel(for key: String) -> String {
        switch key {
        case "name":  return "名前"
        case "email": return "メール"
        default:      return key   // CSV の任意列名（会社名など）はそのまま表示
        }
    }

    /// カーソル位置へ差し込みコードを挿入する。
    /// - 件名（TextField）にフォーカスがある場合はそのフィールドエディタへ挿入。
    /// - それ以外（本文にフォーカス／どこも未フォーカス）は本文エディタへ挿入。
    ///   本文は Controller が NSTextView を直接保持しているため確実に効く。
    private func insert(_ code: String) {
        // 件名など、本文以外のテキスト欄にフォーカスがあればそちらへ。
        if let textView = NSApp.keyWindow?.firstResponder as? NSTextView,
           textView !== bodyController.textView {
            let range = textView.selectedRange()
            if textView.shouldChangeText(in: range, replacementString: code) {
                textView.replaceCharacters(in: range, with: code)
                textView.didChangeText()
            }
            return
        }
        // 既定の挿入先は本文。
        bodyController.insert(code)
    }
}
