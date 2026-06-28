//
//  MailMergeViewModel.swift
//  MailMergePro
//
//  画面全体の状態と操作を集約する MVVM の ViewModel。
//  View は本オブジェクトの @Published を購読し、ユーザー操作はすべてここのメソッド経由で行う。
//  各 Service（永続化・インポート・送信・エクスポート）は protocol で注入し、テスト容易性を確保する。
//

import Foundation
import Combine

/// メイン画面の状態管理。
/// すべての UI 更新はメインスレッドで行うため `@MainActor` を付与。
@MainActor
final class MailMergeViewModel: ObservableObject {

    // MARK: - 宛先

    /// 読み込んだ宛先一覧。
    @Published private(set) var recipients: [Recipient] = []

    // MARK: - テンプレート

    /// 保存済みテンプレート一覧。
    @Published private(set) var templates: [Template] = []
    /// 現在選択中のテンプレート ID。
    @Published var selectedTemplateID: Template.ID?

    // MARK: - メール作成内容

    /// 件名（差し込みコードを含められる）。変更時はテスト成功状態を無効化。
    @Published var subject: String = "" {
        didSet { invalidateTestIfNeeded(oldValue, subject) }
    }
    /// 本文。
    @Published var body: String = "" {
        didSet { invalidateTestIfNeeded(oldValue, body) }
    }
    /// 添付ファイル一覧。
    @Published private(set) var attachments: [Attachment] = []

    // MARK: - 送信元アカウント

    /// Mail から取得した送信可能アカウント一覧。
    @Published private(set) var accounts: [MailAccount] = []
    /// 選択中の送信元アカウント（送信のたびに1つ選ぶ）。
    @Published var selectedAccount: MailAccount?

    // MARK: - 送信制御

    /// テスト送信の宛先（自分のアドレス）。
    @Published var testAddress: String = ""
    /// テスト送信が成功したか。本番送信ボタンの有効化ゲート。
    @Published private(set) var testSucceeded: Bool = false
    /// バッチ設定（50通 / 30秒）。
    @Published var settings: SendSettings = .default

    // MARK: - 進捗・結果

    /// 送信中かどうか。
    @Published private(set) var isSending: Bool = false
    /// 送信済み件数（進捗バー用）。
    @Published private(set) var sentProgress: Int = 0
    /// 今回の送信対象総数。
    @Published private(set) var totalToSend: Int = 0
    /// 現在送信中の宛先名（「現在送信中: 山田太郎」表示用）。
    @Published private(set) var currentRecipientName: String = ""
    /// 送信完了後の集計。nil の間は結果画面を出さない。
    @Published var summary: SendSummary?

    // MARK: - プレビュー

    /// プレビュー表示中の受信者インデックス。
    @Published var previewIndex: Int = 0

    // MARK: - エラー表示

    /// 表示すべきエラーメッセージ（非 nil でアラート表示）。
    @Published var errorMessage: String?

    // MARK: - 依存 Service

    private let templateStore: TemplateStoring
    private let importer: RecipientImporting
    private let mailSender: MailSending
    private let accountProvider: MailAccountProviding

    /// 本番送信タスク（キャンセル用に保持）。
    private var sendTask: Task<Void, Never>?

    /// 本番送信の開始時刻（送信済みフォルダ仕分けの対象時間範囲の起点）。
    private var batchStartedAt: Date?

    /// 依存性注入。既定で本番実装を使う。
    init(
        templateStore: TemplateStoring = TemplateStore(),
        importer: RecipientImporting = RecipientImporter(),
        mailSender: MailSending = AppleMailSender(),
        accountProvider: MailAccountProviding = MailAccountProvider()
    ) {
        self.templateStore = templateStore
        self.importer = importer
        self.mailSender = mailSender
        self.accountProvider = accountProvider
    }

    // MARK: - 起動時ロード

    /// 保存済みテンプレートを読み込む（アプリ起動時に呼ぶ）。
    func loadTemplates() {
        do {
            templates = try templateStore.loadAll()
        } catch {
            present(error)
        }
    }

    /// 送信元アカウント一覧を Mail から取得する（起動時・更新ボタンで呼ぶ）。
    /// 初回はここで Mail への自動化許可ダイアログが出る場合がある。
    func loadAccounts() {
        do {
            accounts = try accountProvider.fetchAccounts()
            // 未選択なら先頭を既定選択。選択中が消えていたらクリア。
            if let current = selectedAccount, !accounts.contains(current) {
                selectedAccount = nil
            }
            if selectedAccount == nil {
                selectedAccount = accounts.first
            }
        } catch {
            present(error)
        }
    }

    // MARK: - 宛先インポート

    /// ファイルから宛先を読み込む。成功すればプレビュー位置をリセット。
    func importRecipients(from url: URL) {
        do {
            let imported = try importer.importRecipients(from: url)
            recipients = imported
            previewIndex = 0
            invalidateTest() // 宛先が変われば再テストを促す
        } catch {
            present(error)
        }
    }

    /// 宛先件数。
    var recipientCount: Int { recipients.count }

    // MARK: - テンプレート操作

    /// 新規テンプレートを追加して選択する。
    func addTemplate() {
        let new = Template.makeEmpty()
        templates.append(new)
        selectedTemplateID = new.id
        persistTemplates()
    }

    /// テンプレートを削除する。
    func deleteTemplate(_ template: Template) {
        templates.removeAll { $0.id == template.id }
        if selectedTemplateID == template.id { selectedTemplateID = nil }
        persistTemplates()
    }

    /// テンプレート名を変更する。
    func renameTemplate(_ template: Template, to newName: String) {
        guard let idx = templates.firstIndex(where: { $0.id == template.id }) else { return }
        templates[idx].name = newName
        persistTemplates()
    }

    /// テンプレートを件名・本文に反映する（クリック時）。
    func applyTemplate(_ template: Template) {
        subject = template.subject
        body = template.body
        selectedTemplateID = template.id
    }

    /// 現在の件名・本文を、選択中テンプレートへ上書き保存する。
    func saveCurrentIntoSelectedTemplate() {
        guard let id = selectedTemplateID,
              let idx = templates.firstIndex(where: { $0.id == id }) else { return }
        templates[idx].subject = subject
        templates[idx].body = body
        persistTemplates()
    }

    /// テンプレート配列を永続化する。
    private func persistTemplates() {
        do {
            try templateStore.saveAll(templates)
        } catch {
            present(error)
        }
    }

    // MARK: - 添付ファイル操作

    /// 添付ファイルを追加（重複 URL は無視）。
    func addAttachments(_ urls: [URL]) {
        for url in urls where !attachments.contains(where: { $0.url == url }) {
            attachments.append(Attachment(url: url))
        }
        invalidateTest()
    }

    /// 添付ファイルを削除。
    func removeAttachment(_ attachment: Attachment) {
        attachments.removeAll { $0.id == attachment.id }
        invalidateTest()
    }

    // MARK: - プレビュー

    /// プレビュー対象の受信者（範囲外なら nil）。
    var previewRecipient: Recipient? {
        guard recipients.indices.contains(previewIndex) else { return nil }
        return recipients[previewIndex]
    }

    /// プレビュー用に差し込み置換された件名。
    var previewSubject: String {
        guard let r = previewRecipient else { return subject }
        return MergeRenderer.render(subject, with: r)
    }

    /// プレビュー用に差し込み置換された本文。
    var previewBody: String {
        guard let r = previewRecipient else { return body }
        return MergeRenderer.render(body, with: r)
    }

    /// 次の受信者へ。
    func showNextPreview() {
        guard !recipients.isEmpty else { return }
        previewIndex = min(previewIndex + 1, recipients.count - 1)
    }

    /// 前の受信者へ。
    func showPreviousPreview() {
        guard !recipients.isEmpty else { return }
        previewIndex = max(previewIndex - 1, 0)
    }

    // MARK: - 送信可能判定

    /// テスト送信が可能か（送信元選択・宛先アドレス・本文の最低限が揃っているか）。
    var canSendTest: Bool {
        !isSending
            && selectedAccount != nil
            && Recipient.isValidEmail(testAddress)
            && !subject.trimmingCharacters(in: .whitespaces).isEmpty
    }

    /// 本番送信が可能か（テスト成功済み＆送信元選択＆宛先あり＆未送信中）。
    var canSendProduction: Bool {
        testSucceeded && selectedAccount != nil && !recipients.isEmpty && !isSending
    }

    // MARK: - テスト送信

    /// 現在の件名・本文・添付を自分宛てに送信する。成功時のみ本番送信を解放。
    func sendTest() async {
        guard canSendTest else { return }
        isSending = true
        defer { isSending = false }

        do {
            // テスト送信では宛先個別の差し込みが無いため、件名・本文はそのまま送る。
            try mailSender.send(
                subject: subject,
                body: body,
                to: testAddress,
                senderEmail: selectedAccount?.email,
                attachments: attachments
            )
            testSucceeded = true
        } catch {
            testSucceeded = false
            present(error)
        }
    }

    // MARK: - 本番送信（バッチ処理）

    /// 本番一斉送信を開始する。バッチ分割・待機・キャンセルを行う。
    func startProductionSend() {
        guard canSendProduction else { return }

        // 状態初期化。送信対象は全宛先。
        isSending = true
        summary = nil
        sentProgress = 0
        totalToSend = recipients.count
        currentRecipientName = ""
        batchStartedAt = Date() // 送信済みフォルダ仕分けの時間範囲の起点

        // 全宛先のステータスを未送信に戻す（再送対応）。
        for i in recipients.indices {
            recipients[i].status = .pending
            recipients[i].errorMessage = nil
        }

        sendTask = Task { [weak self] in
            await self?.runBatchSend()
        }
    }

    /// バッチ送信本体。`@MainActor` 上で実行されるため UI 更新は安全。
    private func runBatchSend() async {
        let batchSize = settings.batchSize
        let interval = settings.intervalSeconds
        let total = recipients.count

        var index = 0
        while index < total {
            // バッチ境界。1バッチ＝batchSize 通。
            let batchEnd = min(index + batchSize, total)

            for i in index..<batchEnd {
                // キャンセル要求があれば安全に中断。
                if Task.isCancelled { finishSend(cancelled: true); return }

                currentRecipientName = recipients[i].name
                await sendOne(at: i)
                sentProgress = i + 1
            }

            index = batchEnd

            // 最終バッチでなければインターバルを挟む。
            if index < total {
                do {
                    try await Task.sleep(nanoseconds: UInt64(interval * 1_000_000_000))
                } catch {
                    // sleep 中のキャンセル。
                    finishSend(cancelled: true)
                    return
                }
            }
        }

        finishSend(cancelled: false)
    }

    /// 指定インデックスの宛先1件を送信し、結果をステータスへ反映する。
    private func sendOne(at i: Int) async {
        let recipient = recipients[i]

        // メールアドレス不正は送信せず対象外に。
        guard recipient.hasValidEmail else {
            recipients[i].status = .skipped
            recipients[i].errorMessage = "メールアドレスが不正です"
            return
        }

        recipients[i].status = .sending

        // 宛先ごとに差し込み置換。
        let renderedSubject = MergeRenderer.render(subject, with: recipient)
        let renderedBody = MergeRenderer.render(body, with: recipient)

        do {
            try mailSender.send(
                subject: renderedSubject,
                body: renderedBody,
                to: recipient.email,
                senderEmail: selectedAccount?.email,
                attachments: attachments
            )
            recipients[i].status = .sent
            recipients[i].errorMessage = nil
        } catch {
            recipients[i].status = .failed
            recipients[i].errorMessage = error.localizedDescription
        }
    }

    /// 送信終了処理。集計を作って状態を片付け、送信済みフォルダの仕分けを行う。
    private func finishSend(cancelled: Bool) {
        summary = SendSummary(recipients: recipients)
        isSending = false
        currentRecipientName = ""
        sendTask = nil
        // 実際に送れたメールがあれば、専用フォルダへ隔離する。
        organizeSentMessages()
    }

    /// 一斉送信したメールを通常 Sent から専用フォルダへ移動する。
    /// Mail が Sent へ保存し終えるのを少し待ってから実行する。
    private func organizeSentMessages() {
        guard let account = selectedAccount,
              let start = batchStartedAt,
              summary?.successCount ?? 0 > 0 else { return }

        Task { [weak self] in
            // Mail が最後のメールを Sent へ保存し終えるのを待つ。
            try? await Task.sleep(nanoseconds: 5 * 1_000_000_000)
            // バッチ所要時間＋バッファ（3分）を遡って対象にする。
            let seconds = Int(Date().timeIntervalSince(start)) + 180
            do {
                try SentMessageOrganizer.organize(accountName: account.name, sinceSeconds: seconds)
            } catch {
                // 仕分け失敗は送信自体の成否に影響しないため、警告として提示。
                self?.present(error)
            }
        }
    }

    /// 送信全体をキャンセルする。
    func cancelSend() {
        sendTask?.cancel()
    }

    // MARK: - 結果エクスポート

    /// 送信結果を CSV としてエクスポートする。
    func exportResults(to url: URL) {
        guard let summary else { return }
        do {
            try ResultExporter.export(summary, to: url)
        } catch {
            present(error)
        }
    }

    // MARK: - テスト成功状態の無効化

    /// 件名・本文が実際に変化したときだけテスト成功を無効化する。
    private func invalidateTestIfNeeded(_ old: String, _ new: String) {
        if old != new { invalidateTest() }
    }

    /// テスト成功フラグを下ろす（内容が変われば再テストを必須にする）。
    private func invalidateTest() {
        if testSucceeded { testSucceeded = false }
    }

    // MARK: - エラー提示

    /// エラーを localizedDescription でアラート表示用プロパティへ反映。
    private func present(_ error: Error) {
        errorMessage = error.localizedDescription
    }
}
