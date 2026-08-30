/**
 * localStorage の入り口。キーはすべて `growth-app:` で始める。
 * 壊れた値が入っていてもアプリが落ちないよう、読み出しは必ず try/catch で既定値に落とす。
 */
import type { EarnedBadge, FamilyMember, GrowthRecord, Profile } from '../types'

const PREFIX = 'growth-app:'
export const KEYS = {
  profile: PREFIX + 'profile',
  records: PREFIX + 'records',
  family: PREFIX + 'family',
  badges: PREFIX + 'badges',
} as const

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return fallback
    return JSON.parse(raw) as T
  } catch {
    return fallback
  }
}

function write(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // 容量オーバーなどは握りつぶさず、呼び出し側で気づけるように警告だけ出す
    console.warn('[growth-app] 保存に失敗しました', key)
  }
}

export const store = {
  loadProfile:  () => read<Profile | null>(KEYS.profile, null),
  saveProfile:  (p: Profile) => write(KEYS.profile, p),

  loadRecords:  () => read<GrowthRecord[]>(KEYS.records, []),
  saveRecords:  (r: GrowthRecord[]) => write(KEYS.records, r),

  loadFamily:   () => read<FamilyMember[]>(KEYS.family, []),
  saveFamily:   (f: FamilyMember[]) => write(KEYS.family, f),

  loadBadges:   () => read<EarnedBadge[]>(KEYS.badges, []),
  saveBadges:   (b: EarnedBadge[]) => write(KEYS.badges, b),

  /** 設定画面の「データを全部消す」 */
  clearAll: () => {
    for (const key of Object.values(KEYS)) localStorage.removeItem(key)
  },
}

/** 1日1件。同じ日付があれば上書きし、日付順に並べて返す */
export function upsertRecord(records: GrowthRecord[], next: GrowthRecord): GrowthRecord[] {
  const others = records.filter((r) => r.date !== next.date)
  return [...others, next].sort((a, b) => a.date.localeCompare(b.date))
}
