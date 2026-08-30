/**
 * 平均身長ライン用の年齢別 目安値（cm）。
 * ★ここは「目安」であって公表値そのままではない。5〜17歳は学校保健統計調査、
 *   1〜4歳は乳幼児身体発育調査の値を丸めた概数として持っている（出典の厳密な照合は未実施）。
 *   正確な値に差し替えるときは、この表だけを直せばグラフ側は触らなくてよい。
 */
import type { Gender } from '../types'

type Table = Record<number, number>

const BOY: Table = {
  1: 78.1, 2: 88.0, 3: 95.1, 4: 102.0,
  5: 110.3, 6: 117.5, 7: 123.5, 8: 129.1, 9: 134.5, 10: 140.1,
  11: 146.6, 12: 154.3, 13: 161.4, 14: 166.1, 15: 168.8, 16: 170.2, 17: 170.7,
}

const GIRL: Table = {
  1: 76.7, 2: 86.9, 3: 93.9, 4: 100.9,
  5: 109.4, 6: 116.7, 7: 122.6, 8: 128.5, 9: 134.8, 10: 141.5,
  11: 148.0, 12: 152.6, 13: 155.2, 14: 156.7, 15: 157.3, 16: 157.7, 17: 158.0,
}

/** 小数の年齢を渡すと、前後の年齢の間を直線で結んだ値を返す */
export function averageHeight(gender: Gender, age: number): number | null {
  const table = gender === 'boy' ? BOY : GIRL
  const ages = Object.keys(table).map(Number)
  const min = Math.min(...ages)
  const max = Math.max(...ages)
  if (age < min || age > max) return null      // 表の外は線を引かない（作り話をしない）
  const lo = Math.floor(age)
  const hi = Math.min(max, lo + 1)
  if (lo === hi) return table[lo]
  const t = age - lo
  return Math.round((table[lo] + (table[hi] - table[lo]) * t) * 10) / 10
}
