//
//  SendSettings.swift
//  MailMergePro
//
//  バッチ送信の挙動を制御する設定値。
//  仕様により「1通ごと1秒」「バッチサイズ50通」「バッチ間60秒（1分）」を初期値とし、
//  将来の設定画面から動的変更できるよう独立した型として切り出している。
//

import Foundation

/// 大量送信時の分割・待機に関する設定。
struct SendSettings: Equatable {

    /// 1バッチあたりの最大送信数（初期値 50）。
    var batchSize: Int

    /// バッチ間の待機秒数（初期値 60＝1分）。スパム判定・サーバ拒否の回避用。
    var intervalSeconds: Double

    /// 1通ごとの待機秒数（初期値 1）。バッチ内でも連続送信せず1通ずつ間隔をあける。
    var perMessageDelaySeconds: Double

    /// 既定設定（1通ごと1秒 / 50通 / バッチ間60秒）。
    static let `default` = SendSettings(batchSize: 50, intervalSeconds: 60,
                                        perMessageDelaySeconds: 1)

    init(batchSize: Int = 50, intervalSeconds: Double = 60,
         perMessageDelaySeconds: Double = 1) {
        // 不正値（0以下）を弾き、最低1通・0秒以上に正規化する。
        self.batchSize = max(1, batchSize)
        self.intervalSeconds = max(0, intervalSeconds)
        self.perMessageDelaySeconds = max(0, perMessageDelaySeconds)
    }
}
