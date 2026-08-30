/** 日付まわり。ズレの元になるので、日付は必ず YYYY-MM-DD の文字列で持ち回す */

export const pad = (n: number) => String(n).padStart(2, '0')

export function toKey(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function today(): string {
  return toKey(new Date())
}

export function parseKey(key: string): Date {
  const [y, m, d] = key.split('-').map(Number)
  return new Date(y, m - 1, d)   // ローカル時刻で作る（UTCだと日付が1日ずれる）
}

/** 誕生日から「○歳○ヶ月○日」を出す */
export function ageParts(birthday: string, at: string = today()) {
  const b = parseKey(birthday)
  const now = parseKey(at)
  let years = now.getFullYear() - b.getFullYear()
  let months = now.getMonth() - b.getMonth()
  let days = now.getDate() - b.getDate()
  if (days < 0) {
    months -= 1
    const prevMonthEnd = new Date(now.getFullYear(), now.getMonth(), 0).getDate()
    days += prevMonthEnd
  }
  if (months < 0) {
    years -= 1
    months += 12
  }
  return { years: Math.max(0, years), months: Math.max(0, months), days: Math.max(0, days) }
}

/** グラフの平均線に使う「小数の年齢」 */
export function ageInYears(birthday: string, at: string): number {
  const b = parseKey(birthday).getTime()
  const n = parseKey(at).getTime()
  return (n - b) / (365.2425 * 24 * 3600 * 1000)
}

/** 次の誕生日まであと何日 */
export function daysUntilBirthday(birthday: string, at: string = today()): number {
  const b = parseKey(birthday)
  const now = parseKey(at)
  let next = new Date(now.getFullYear(), b.getMonth(), b.getDate())
  if (next.getTime() < now.getTime()) next = new Date(now.getFullYear() + 1, b.getMonth(), b.getDate())
  return Math.round((next.getTime() - now.getTime()) / (24 * 3600 * 1000))
}

export function addDays(key: string, delta: number): string {
  const d = parseKey(key)
  d.setDate(d.getDate() + delta)
  return toKey(d)
}

export function formatJP(key: string): string {
  const d = parseKey(key)
  const w = ['日', '月', '火', '水', '木', '金', '土'][d.getDay()]
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日（${w}）`
}

export function formatShort(key: string): string {
  const d = parseKey(key)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

/** 連続記録日数。今日（まだなら昨日）から1日ずつさかのぼって数える */
export function currentStreak(dates: string[], at: string = today()): number {
  const set = new Set(dates)
  let cursor = set.has(at) ? at : addDays(at, -1)
  if (!set.has(cursor)) return 0
  let count = 0
  while (set.has(cursor)) {
    count += 1
    cursor = addDays(cursor, -1)
  }
  return count
}
