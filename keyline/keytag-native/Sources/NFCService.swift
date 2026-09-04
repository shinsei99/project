import Foundation
#if canImport(CoreNFC)
import CoreNFC
#endif

enum NFCError: LocalizedError {
    case unavailable          // シミュレータ・NFC非搭載の端末
    case canceled             // 利用者がシートを閉じた
    case connectFailed(String)
    case notWritable
    case tooLarge(Int, Int)
    case writeFailed(String)
    case readFailed(String)

    var errorDescription: String? {
        switch self {
        case .unavailable:
            return "この端末ではNFCを使えません（実機のiPhoneが必要です）"
        case .canceled:
            return "読み取りを中止しました"
        case .connectFailed(let m):
            return "タグに接続できませんでした（\(m)）"
        case .notWritable:
            return "このタグは書き込みできません（ロックされている可能性があります）"
        case .tooLarge(let need, let cap):
            return "このタグには収まりません（\(need) バイト / 容量 \(cap) バイト）"
        case .writeFailed(let m):
            return "書き込めませんでした（\(m)）"
        case .readFailed(let m):
            return "読み取れませんでした（\(m)）"
        }
    }
}

/// Core NFC の読み書き。
///
/// ★TAG セッションで開く（NDEFセッションではない）。
///   まっさらな（NDEF未フォーマットの）タグは NDEF セッションだと掴んだ瞬間に
///   「NDEFメッセージが無い」でシートが赤くなる。旧版(Capacitor)で実機で踏んだ不具合と同じ。
///   TAG セッションなら UID だけ拾って続けられ、書き込みでフォーマットもできる。
///
/// ★書き込みは**1つのセッションの中で**行う。検出後にセッションを閉じるとタグとの接続ごと
///   失われて必ず失敗する（これも旧版で踏んだ）。
final class NFCService: NSObject {

    static var isAvailable: Bool {
        #if canImport(CoreNFC)
        return NFCTagReaderSession.readingAvailable
        #else
        return false
        #endif
    }

    #if canImport(CoreNFC)
    private var session: NFCTagReaderSession?
    private var continuation: CheckedContinuation<TagRead, Error>?
    private var recordsToWrite: [NDEF.Record]?
    private var capacityHint: Int = 0
    private let queue = DispatchQueue(label: "keytag.nfc")
    private let lock = NSLock()
    #endif

    /// タグを1枚読む。
    func read(alert: String = "鍵のタグに近づけてください") async throws -> TagRead {
        try await run(alert: alert, write: nil, capacity: 0)
    }

    /// タグへ書く。返り値は書いたタグの UID。
    func write(_ records: [NDEF.Record], capacity: Int,
               alert: String = "書き込むタグに近づけてください") async throws -> TagRead {
        try await run(alert: alert, write: records, capacity: capacity)
    }

    private func run(alert: String, write: [NDEF.Record]?, capacity: Int) async throws -> TagRead {
        #if canImport(CoreNFC)
        guard NFCTagReaderSession.readingAvailable else { throw NFCError.unavailable }
        return try await withCheckedThrowingContinuation { cont in
            lock.lock()
            self.continuation = cont
            self.recordsToWrite = write
            self.capacityHint = capacity
            lock.unlock()
            let s = NFCTagReaderSession(pollingOption: [.iso14443], delegate: self, queue: queue)
            s?.alertMessage = alert
            self.session = s
            s?.begin()
        }
        #else
        throw NFCError.unavailable
        #endif
    }

    #if canImport(CoreNFC)
    /// 結果を1度だけ返す。セッションの後始末もここでまとめる。
    private func finish(_ result: Result<TagRead, Error>, message: String?) {
        lock.lock()
        let cont = continuation
        continuation = nil
        recordsToWrite = nil
        lock.unlock()
        guard let cont else { return }

        switch result {
        case .success:
            if let message { session?.alertMessage = message }
            session?.invalidate()
        case .failure(let e):
            if let n = e as? NFCError, case .canceled = n {
                // 利用者が閉じた場合はシステム側で閉じ終わっている
            } else {
                session?.invalidate(errorMessage: (e.localizedDescription as String))
            }
        }
        session = nil
        cont.resume(with: result)
    }
    #endif
}

#if canImport(CoreNFC)
extension NFCService: NFCTagReaderSessionDelegate {

    func tagReaderSessionDidBecomeActive(_ session: NFCTagReaderSession) {}

    func tagReaderSession(_ session: NFCTagReaderSession, didInvalidateWithError error: Error) {
        let ne = error as? NFCReaderError
        if ne?.code == .readerSessionInvalidationErrorUserCanceled {
            finish(.failure(NFCError.canceled), message: nil)
        } else if ne?.code == .readerSessionInvalidationErrorFirstNDEFTagRead {
            // 正常終了。すでに finish 済みのはずなので何もしない
            finish(.failure(NFCError.canceled), message: nil)
        } else {
            finish(.failure(NFCError.readFailed(error.localizedDescription)), message: nil)
        }
    }

    func tagReaderSession(_ session: NFCTagReaderSession, didDetect tags: [NFCTag]) {
        guard let tag = tags.first else { return }

        session.connect(to: tag) { [weak self] error in
            guard let self else { return }
            if let error {
                self.finish(.failure(NFCError.connectFailed(error.localizedDescription)), message: nil)
                return
            }

            let uid = Self.identifier(of: tag)
            guard let ndefTag = Self.ndefTag(from: tag) else {
                self.finish(.failure(NFCError.readFailed("このタグはNDEFに対応していません")), message: nil)
                return
            }

            ndefTag.queryNDEFStatus { status, capacity, _ in
                self.lock.lock()
                let toWrite = self.recordsToWrite
                self.lock.unlock()

                if let toWrite {
                    self.performWrite(toWrite, on: ndefTag, uid: uid, status: status, capacity: capacity)
                } else {
                    self.performRead(on: ndefTag, uid: uid, status: status)
                }
            }
        }
    }

    // MARK: - 読み

    private func performRead(on tag: NFCNDEFTag, uid: String, status: NFCNDEFStatus) {
        // 未フォーマットのタグは NDEF メッセージを持たない。**それでも UID は返す**
        // （台帳と突き合わせて「この鍵だ」と分かるのは UID なので、空タグでも意味がある）。
        guard status != .notSupported else {
            finish(.success(TagRead(uid: uid)), message: "読み取りました")
            return
        }
        tag.readNDEF { message, _ in
            var out = TagRead(uid: uid)
            if let message {
                for r in message.records {
                    let p = NDEF.parseRecord(type: r.type, payload: r.payload)
                    out.records.append(p)
                    if p.kind == .url, out.url == nil { out.url = p.value }
                    if p.kind == .text, out.text == nil { out.text = p.value }
                }
            }
            self.finish(.success(out), message: "読み取りました")
        }
    }

    // MARK: - 書き

    private func performWrite(_ records: [NDEF.Record], on tag: NFCNDEFTag, uid: String,
                              status: NFCNDEFStatus, capacity: Int) {
        switch status {
        case .readOnly, .notSupported:
            // notSupported でも書ける個体があるため、まず試してから諦める
            if status == .readOnly {
                finish(.failure(NFCError.notWritable), message: nil)
                return
            }
        default: break
        }

        let payloads = records.map {
            NFCNDEFPayload(format: .nfcWellKnown,
                           type: Data($0.type),
                           identifier: Data($0.id),
                           payload: Data($0.payload))
        }
        let message = NFCNDEFMessage(records: payloads)

        // タグが申告する容量で先に弾く（書いてから失敗するより分かりやすい）
        let need = NDEF.messageSize(records)
        if capacity > 0 && need > capacity {
            finish(.failure(NFCError.tooLarge(need, capacity)), message: nil)
            return
        }

        tag.writeNDEF(message) { error in
            if let error {
                self.finish(.failure(NFCError.writeFailed(error.localizedDescription)), message: nil)
            } else {
                self.finish(.success(TagRead(uid: uid)), message: "書き込みました")
            }
        }
    }

    // MARK: - タグの取り出し

    private static func ndefTag(from tag: NFCTag) -> NFCNDEFTag? {
        switch tag {
        case .miFare(let t): return t
        case .iso7816(let t): return t
        case .iso15693(let t): return t
        case .feliCa(let t): return t
        @unknown default: return nil
        }
    }

    private static func identifier(of tag: NFCTag) -> String {
        switch tag {
        case .miFare(let t): return NDEF.uidString(t.identifier)
        case .iso7816(let t): return NDEF.uidString(t.identifier)
        case .iso15693(let t): return NDEF.uidString(t.identifier)
        case .feliCa(let t): return NDEF.uidString(t.currentIDm)
        @unknown default: return ""
        }
    }
}
#endif
