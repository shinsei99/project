/**
 * ごほうびバッジ。「記録から計算できるもの」だけを扱い、状態は持たない。
 * 保存しているのは “いつ取ったか” だけ（EarnedBadge）。
 */
import type { EarnedBadge, GrowthRecord } from '../types'
import { currentStreak } from './date'

export interface BadgeDef {
  id: string
  label: string
  description: string
  tone: 'indigo' | 'amber' | 'teal'
}

/** いま満たしているバッジを、記録から丸ごと計算し直す */
export function computeBadges(records: GrowthRecord[]): BadgeDef[] {
  const sorted = [...records].sort((a, b) => a.date.localeCompare(b.date))
  const list: BadgeDef[] = []
  if (sorted.length === 0) return list

  list.push({ id: 'first', label: 'はじめの1件', description: '最初の記録をつけた', tone: 'teal' })

  // 最初の記録の身長から 1cm 伸びるごと
  const start = sorted[0].height
  const best = Math.max(...sorted.map((r) => r.height))
  const grown = Math.floor(best - start)
  for (let cm = 1; cm <= grown; cm++) {
    list.push({ id: `grow-${cm}`, label: `+${cm}cm`, description: `最初より ${cm}cm 伸びた`, tone: 'indigo' })
  }

  // 連続記録（今日から数えた連続日数で判定）
  const streak = currentStreak(sorted.map((r) => r.date))
  if (streak >= 7) list.push({ id: 'streak-7', label: '7日連続', description: '7日続けて記録した', tone: 'amber' })
  if (streak >= 30) list.push({ id: 'streak-30', label: '30日連続', description: '30日続けて記録した', tone: 'amber' })

  return list
}

/** 保存済みと突き合わせて「今回あたらしく取ったバッジ」を返す */
export function findNewBadges(current: BadgeDef[], earned: EarnedBadge[]): BadgeDef[] {
  const known = new Set(earned.map((e) => e.id))
  return current.filter((b) => !known.has(b.id))
}
