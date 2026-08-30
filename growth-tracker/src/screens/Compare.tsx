/** くらべる。1年前の自分との差と、登録した家族との身長比べ */
import { useMemo, useState } from 'react'
import type { FamilyMember, GrowthRecord, Profile } from '../types'
import { BigButton, Card } from '../components/ui'
import { addDays, formatJP, parseKey, today } from '../lib/date'

/** 目的の日にいちばん近い記録を返す（離れすぎているものは返さない） */
function nearestRecord(records: GrowthRecord[], target: string, toleranceDays = 60): GrowthRecord | null {
  let best: GrowthRecord | null = null
  let bestDiff = Infinity
  const t = parseKey(target).getTime()
  for (const r of records) {
    const diff = Math.abs(parseKey(r.date).getTime() - t) / (24 * 3600 * 1000)
    if (diff < bestDiff) { bestDiff = diff; best = r }
  }
  return best && bestDiff <= toleranceDays ? best : null
}

export function Compare({ profile, records, family, onSaveFamily }: {
  profile: Profile
  records: GrowthRecord[]
  family: FamilyMember[]
  onSaveFamily: (f: FamilyMember[]) => void
}) {
  const sorted = useMemo(() => [...records].sort((a, b) => a.date.localeCompare(b.date)), [records])
  const latest = sorted[sorted.length - 1] ?? null
  const yearAgo = useMemo(() => nearestRecord(sorted, addDays(today(), -365)), [sorted])
  const grown = latest && yearAgo ? Math.round((latest.height - yearAgo.height) * 10) / 10 : null

  const [name, setName] = useState('')
  const [height, setHeight] = useState('')

  const add = () => {
    const h = Number(height)
    if (name.trim() === '' || !Number.isFinite(h) || h <= 0) return
    onSaveFamily([...family, { id: `${Date.now()}`, name: name.trim(), height: Math.round(h * 10) / 10 }])
    setName(''); setHeight('')
  }

  const remove = (id: string) => onSaveFamily(family.filter((f) => f.id !== id))

  // 棒の高さは「いちばん背の高い人」を基準に決める
  const bars = latest
    ? [{ id: 'me', name: profile.name, height: latest.height, me: true }, ...family.map((f) => ({ ...f, me: false }))]
    : family.map((f) => ({ ...f, me: false }))
  const maxHeight = bars.length > 0 ? Math.max(...bars.map((b) => b.height)) : 1

  return (
    <div className="mx-auto max-w-md px-5 pt-6">
      <h1 className="mb-4 text-2xl font-bold tracking-tight text-slate-800">くらべる</h1>

      <Card className="mb-4">
        <div className="mb-3 text-base font-semibold text-slate-600">1年前の自分と</div>
        {!latest ? (
          <p className="py-6 text-center text-slate-400">記録がまだありません</p>
        ) : !yearAgo || yearAgo.date === latest.date ? (
          <p className="py-6 text-center text-slate-400">
            1年前の記録がまだありません。<br />続けているとここに差が出ます。
          </p>
        ) : (
          <>
            <div className="flex items-end justify-between gap-3">
              <div className="flex-1 text-center">
                <div className="tnum text-xs text-slate-400">{formatJP(yearAgo.date)}</div>
                <div className="tnum mt-1 text-2xl font-bold text-slate-500">{yearAgo.height.toFixed(1)}<span className="text-sm">cm</span></div>
              </div>
              <div className="pb-2 text-slate-300">→</div>
              <div className="flex-1 text-center">
                <div className="tnum text-xs text-slate-400">{formatJP(latest.date)}</div>
                <div className="tnum mt-1 text-2xl font-bold text-indigo-600">{latest.height.toFixed(1)}<span className="text-sm">cm</span></div>
              </div>
            </div>
            <div className="mt-4 rounded-xl bg-indigo-50 py-5 text-center">
              <div className="text-sm font-semibold text-indigo-500">1年で伸びた長さ</div>
              <div className="tnum text-5xl font-bold text-indigo-600">
                {grown !== null && grown >= 0 ? '+' : '−'}{Math.abs(grown ?? 0).toFixed(1)}
                <span className="ml-1 text-xl">cm</span>
              </div>
            </div>
          </>
        )}
      </Card>

      <Card className="mb-4">
        <div className="mb-3 text-base font-semibold text-slate-600">家族とくらべる</div>

        {bars.length === 0 ? (
          <p className="py-6 text-center text-slate-400">下から家族を登録すると比べられます</p>
        ) : (
          <div className="flex h-56 items-end justify-around gap-2">
            {bars.map((b) => (
              <div key={b.id} className="flex flex-1 flex-col items-center justify-end">
                <div className={`tnum mb-1 text-sm font-bold ${b.me ? 'text-indigo-600' : 'text-slate-500'}`}>
                  {b.height.toFixed(1)}
                </div>
                <div
                  className={`w-full max-w-16 rounded-t-lg ${b.me ? 'bg-indigo-600' : 'bg-slate-300'}`}
                  style={{ height: `${Math.max(8, (b.height / maxHeight) * 170)}px` }}
                />
                <div className={`mt-2 w-full truncate text-center text-sm font-semibold ${b.me ? 'text-indigo-600' : 'text-slate-500'}`}>
                  {b.name}
                </div>
              </div>
            ))}
          </div>
        )}

        {family.length > 0 && (
          <div className="mt-4 space-y-2">
            {family.map((f) => (
              <div key={f.id} className="flex items-center justify-between rounded-xl border border-slate-200 px-4 py-2.5">
                <span className="font-semibold text-slate-700">{f.name}</span>
                <div className="flex items-center gap-3">
                  <span className="tnum text-slate-500">{f.height.toFixed(1)} cm</span>
                  <button onClick={() => remove(f.id)} className="rounded-lg px-2 py-1 text-sm font-semibold text-rose-600 active:bg-rose-50">
                    削除
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card className="mb-4">
        <div className="mb-3 text-base font-semibold text-slate-600">家族を登録</div>
        <div className="flex gap-2">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="名前"
            className="w-1/2 rounded-xl border border-slate-300 px-4 py-3 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
          />
          <input
            type="number"
            inputMode="decimal"
            value={height}
            onChange={(e) => setHeight(e.target.value)}
            placeholder="身長(cm)"
            className="tnum w-1/2 rounded-xl border border-slate-300 px-4 py-3 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
          />
        </div>
        <div className="mt-3">
          <BigButton onClick={add} disabled={name.trim() === '' || height.trim() === ''}>追加する</BigButton>
        </div>
      </Card>
    </div>
  )
}
