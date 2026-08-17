//
//  BodyEditor.swift
//  MailMergePro
//
//  本文用の複数行テキストエディタ（NSTextView ベースの NSViewRepresentable）。
//  標準の TextEditor ではカーソル位置への差し込み挿入が安定しないため、
//  内部の NSTextView への参照を Controller 経由で保持し、
//  「差し込みボタン」からカーソル位置へ確実に挿入できるようにする。
//

import SwiftUI
import AppKit

/// 本文エディタの外部操作用コントローラ。
/// View 側が保持し、差し込みボタンから `insert(_:)` を呼ぶ。
final class BodyEditorController {
    /// 実体の NSTextView（representable が登録する）。
    weak var textView: NSTextView?

    /// 現在のカーソル位置（選択範囲）へ文字列を挿入する。
    /// - Parameter string: 挿入する文字列（例: "{name}"）。
    func insert(_ string: String) {
        guard let tv = textView else { return }
        // 直前にボタン操作でフォーカスが外れていても、本文へ確実に入れる。
        tv.window?.makeFirstResponder(tv)
        let range = tv.selectedRange()
        if tv.shouldChangeText(in: range, replacementString: string) {
            tv.replaceCharacters(in: range, with: string)
            tv.didChangeText()
        }
    }
}

/// 本文（複数行・プレーンテキスト）エディタ。
struct BodyEditor: NSViewRepresentable {
    @Binding var text: String
    let controller: BodyEditorController

    func makeNSView(context: Context) -> NSScrollView {
        let scrollView = NSTextView.scrollableTextView()
        guard let textView = scrollView.documentView as? NSTextView else { return scrollView }

        textView.delegate = context.coordinator
        textView.isRichText = false
        textView.allowsUndo = true
        textView.font = .systemFont(ofSize: NSFont.systemFontSize)
        textView.textContainerInset = NSSize(width: 4, height: 6)
        textView.autoresizingMask = [.width]
        textView.isVerticallyResizable = true
        textView.string = text

        scrollView.hasVerticalScroller = true
        scrollView.borderType = .bezelBorder

        controller.textView = textView
        context.coordinator.parent = self
        return scrollView
    }

    func updateNSView(_ nsView: NSScrollView, context: Context) {
        guard let textView = nsView.documentView as? NSTextView else { return }
        context.coordinator.parent = self
        controller.textView = textView
        // 外部（バインディング）から変わったときだけ反映。編集中の再セットは避ける。
        if textView.string != text {
            let previous = textView.selectedRange()
            textView.string = text
            let loc = min(previous.location, (text as NSString).length)
            textView.setSelectedRange(NSRange(location: loc, length: 0))
        }
    }

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    final class Coordinator: NSObject, NSTextViewDelegate {
        var parent: BodyEditor
        init(_ parent: BodyEditor) { self.parent = parent }

        func textDidChange(_ notification: Notification) {
            guard let textView = notification.object as? NSTextView else { return }
            parent.text = textView.string
        }
    }
}
