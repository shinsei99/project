/** ホーム。年齢・最新の記録・記録ボタン・連続日数・誕生日まで・バッジ */
import { useMemo, useState } from 'react'
import type { BadgeDef } from '../lib/badges'
import type { GrowthRecord, Profile } from '../types'
import { BadgeChip, BigButton, Card, Diff, NumberField, Sheet } from '../components/ui'
import { ageParts, currentStreak, daysUntilBirthday, formatJP, today } from '../lib/date'

export function Home({
  profile, records, badges, onSave, onOpenSettings, onOpenBadges,
}: {
  profile: Profile
  records: GrowthRecord[]
  badges: BadgeDef[]
  onSave: (r: GrowthRecord) => void
  onOpenSettings: () => void
  onOpenBadges: () => void
}) {
  const t = today()
  const sorted = useMemo(() => [...records].sort((a, b) => a.date.localeCompare(b.date)), [records])
  const latest = sorted[sorted.length - 1] ?? null
  const todays = sorted.find((r) => r.date === t) ?? null

  // 表示する記録と、その1つ前（＝前回との差の基準）
  const shown = todays ?? latest
  const base = shown ? sorted[sorted.indexOf(shown) - 1] ?? null : null

  const age = ageParts(profile.birthday, t)
  const streak = currentStreak(sorted.map((r) => r.date), t)
  const untilBirthday = daysUntilBirthday(profile.birthday, t)

  const [open, setOpen] = useState(false)
  const [height, setHeight] = useState(latest?.height ?? 130)
  const [weight, setWeight] = useState(latest?.weight ?? 28)
  const [memo, setMemo] = useState('')

  const openSheet = () => {
    const cur = sorted.find((r) => r.date === t)
    setHeight(cur?.height ?? latest?.height ?? 130)
    setWeight(cur?.weight ?? latest?.weight ?? 28)
    setMemo(cur?.memo ?? '')
    setOpen(true)
  }

  const save = () => {
    onSave({ date: t, height, weight, memo: memo.trim() })
    setOpen(false)
  }

  return (
    <div className="mx-auto max-w-md px-5 pt-6">
      <header className="mb-4 flex items-start justify-between">
        <div>
          <div className="tnum text-sm font-semibold text-slate-400">{formatJP(t)}</div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-800">{profile.name}</h1>
          <div className="tnum text-base text-slate-500">
            {age.years}歳 {age.months}か月 {age.days}日
          </div>
        </div>
        <button
          onClick={onOpenSettings}
          aria-label="設定"
          className="flex h-11 w-11 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-500 active:bg-slate-100"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="3.2" />
            <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1 1.56V21a2 2 0 1 1-4 0v-.11a1.7 1.7 0 0 0-1.11-1.56 1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.7 1.7 0 0 0 .34-1.87 1.7 1.7 0 0 0-1.56-1H3a2 2 0 1 1 0-4h.11a1.7 1.7 0 0 0 1.56-1.11 1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.56V3a2 2 0 1 1 4 0v.11a1.7 1.7 0 0 0 1 1.56 1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.87V9a1.7 1.7 0 0 0 1.56 1H21a2 2 0 1 1 0 4h-.11a1.7 1.7 0 0 0-1.49 1Z" />
          </svg>
        </button>
      </header>

      <div className="mb-3 grid grid-cols-2 gap-3">
        <Card>
          <div className="text-sm font-semibold text-slate-400">身長</div>
          <div className="tnum text-4xl font-bold text-indigo-600">
            {shown ? shown.height.toFixed(1) : '--'}<span className="ml-0.5 text-base font-semibold text-slate-400">cm</span>
          </div>
          <Diff value={shown && base ? Math.round((shown.height - base.height) * 10) / 10 : null} unit="cm" />
        </Card>
        <Card>
          <div className="text-sm font-semibold text-slate-400">体重</div>
          <div className="tnum text-4xl font-bold text-teal-600">
            {shown ? shown.weight.toFixed(1) : '--'}<span className="ml-0.5 text-base font-semibold text-slate-400">kg</span>
          </div>
          <Diff value={shown && base ? Math.round((shown.weight - base.weight) * 10) / 10 : null} unit="kg" />
        </Card>
      </div>

      <div className="mb-3">
        <BigButton onClick={openSheet} color={todays ? 'ghost' : 'primary'}>
          {todays ? '今日の記録を修正' : '今日の記録をつける'}
        </BigButton>
      </div>

      <div className="mb-3 grid grid-cols-2 gap-3">
        <Card>
          <div className="text-sm font-semibold text-slate-400">連続記録</div>
          <div className="tnum text-3xl font-bold text-slate-800">{streak}<span className="ml-0.5 text-base font-semibold text-slate-400">日</span></div>
        </Card>
        <Card>
          <div className="text-sm font-semibold text-slate-400">誕生日まで</div>
          <div className="tnum whitespace-nowrap text-3xl font-bold text-slate-800">
            {untilBirthday === 0 ? '今日' : <>{untilBirthday}<span className="ml-0.5 text-base font-semibold text-slate-400">日</span></>}
          </div>
        </Card>
      </div>

      <Card className="mb-4">
        <button onClick={onOpenBadges} className="flex w-full items-center justify-between">
          <span className="text-base font-semibold text-slate-600">バッジ</span>
          <span className="tnum text-base font-semibold text-indigo-600">{badges.length}個 ›</span>
        </button>
        {badges.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {badges.slice(-8).map((b) => <BadgeChip key={b.id} label={b.label} tone={b.tone} />)}
          </div>
        )}
      </Card>

      <Sheet open={open} title={todays ? '今日の記録を修正' : '今日の記録'} onClose={() => setOpen(false)}>
        <div className="space-y-5">
          <NumberField label="身長" unit="cm" value={height} onChange={setHeight} min={30} max={250} />
          <NumberField label="体重" unit="kg" value={weight} onChange={setWeight} min={2} max={150} />
          <div>
            <div className="mb-2 text-base font-semibold text-slate-500">ひとことメモ</div>
            <input
              value={memo}
              onChange={(e) => setMemo(e.target.value)}
              placeholder="例：部活で走り込み"
              className="w-full rounded-xl border border-slate-300 px-4 py-3.5 text-lg outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
            />
          </div>
          <BigButton onClick={save}>保存する</BigButton>
        </div>
      </Sheet>
    </div>
  )
}
