//
//  SendSettings.swift
//  MailMergePro
//
//  バッチ送信の挙動を制御する設定値。
//  仕様により「バッチサイズ50通」「待機30秒」を初期値とし、
//  将来の設定画面から動的変更できるよう独立した型として切り出している。
//

import Foundation

/// 大量送信時の分割・待機に関する設定。
struct SendSettings: Equatable {

    /// 1バッチあたりの最大送信数（初期値 50）。
    var batchSize: Int

    /// バッチ間の待機秒数（初期値 30）。スパム判定・サーバ拒否の回避用。
    var intervalSeconds: Double

    /// 既定設定（50通 / 30秒）。
    static let `default` = SendSettings(batchSize: 50, intervalSeconds: 30)

    init(batchSize: Int = 50, intervalSeconds: Double = 30) {
        // 不正値（0以下）を弾き、最低1通・0秒以上に正規化する。
        self.batchSize = max(1, batchSize)
        self.intervalSeconds = max(0, intervalSeconds)
    }
}
