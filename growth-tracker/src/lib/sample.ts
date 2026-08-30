/**
 * 動作確認用のサンプルデータ（設定画面の開発用ボタンから使う）。
 * 過去3ヶ月ぶん。毎日ではなく所々抜けるようにして、実際の使われ方に近づけている。
 */
import type { GrowthRecord } from '../types'
import { addDays, today } from './date'

const MEMOS = ['体調よし', '部活で走り込み', '牛乳を飲んだ', '早めに寝た', '休み時間にバスケ', '']

export function makeSampleRecords(startHeight = 118.2, startWeight = 21.4): GrowthRecord[] {
  const out: GrowthRecord[] = []

  // 「1年前の自分」と 1年グラフを確認できるよう、1年前あたりの数日も入れておく
  for (let i = 0; i < 4; i++) {
    const date = addDays(today(), -368 + i * 2)
    out.push({
      date,
      height: Math.round((startHeight - 5.4 + i * 0.1) * 10) / 10,
      weight: Math.round((startWeight - 2.6 + i * 0.1) * 10) / 10,
      memo: i === 0 ? '1年前' : '',
    })
  }

  const days = 92   // 直近3か月ぶん
  for (let i = days; i >= 0; i--) {
    const date = addDays(today(), -i)
    // 直近7日は必ず入れて連続記録バッジを確認できるようにする。それ以外は 3日に2日くらい
    const keep = i < 7 || (i * 7) % 3 !== 1
    if (!keep) continue
    const t = (days - i) / days
    const height = startHeight + t * 2.6 + Math.sin(i / 9) * 0.15
    const weight = startWeight + t * 1.3 + Math.sin(i / 5) * 0.25
    out.push({
      date,
      height: Math.round(height * 10) / 10,
      weight: Math.round(weight * 10) / 10,
      memo: MEMOS[(days - i) % MEMOS.length],
    })
  }
  return out
}
