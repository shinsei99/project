/** カレンダー。記録のある日に色を付け、タップで内容の確認・修正・削除ができる */
import { useMemo, useState } from 'react'
import type { GrowthRecord } from '../types'
import { BigButton, Card, NumberField, Sheet } from '../components/ui'
import { formatJP, pad, parseKey, today } from '../lib/date'

const WEEK = ['日', '月', '火', '水', '木', '金', '土']

export function CalendarScreen({ records, onSave, onDelete }: {
  records: GrowthRecord[]
  onSave: (r: GrowthRecord) => void
  onDelete: (date: string) => void
}) {
  const now = parseKey(today())
  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth())   // 0-11
  const [picked, setPicked] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [height, setHeight] = useState(130)
  const [weight, setWeight] = useState(28)
  const [memo, setMemo] = useState('')

  const byDate = useMemo(() => new Map(records.map((r) => [r.date, r])), [records])

  // 日曜はじまりのマス目を作る（前月ぶんは空マス）
  const cells = useMemo(() => {
    const first = new Date(year, month, 1)
    const daysInMonth = new Date(year, month + 1, 0).getDate()
    const out: (string | null)[] = Array(first.getDay()).fill(null)
    for (let d = 1; d <= daysInMonth; d++) out.push(`${year}-${pad(month + 1)}-${pad(d)}`)
    return out
  }, [year, month])

  const monthCount = cells.filter((c) => c && byDate.has(c)).length

  const move = (delta: number) => {
    const m = month + delta
    setYear(year + Math.floor(m / 12))
    setMonth(((m % 12) + 12) % 12)
  }

  const open = (date: string) => {
    const r = byDate.get(date)
    setPicked(date)
    setEditing(!r)                       // 記録が無い日はいきなり入力できるようにする
    setHeight(r?.height ?? 130)
    setWeight(r?.weight ?? 28)
    setMemo(r?.memo ?? '')
  }

  const current = picked ? byDate.get(picked) ?? null : null

  return (
    <div className="mx-auto max-w-md px-5 pt-6">
      <h1 className="mb-4 text-2xl font-bold tracking-tight text-slate-800">カレンダー</h1>

      <Card className="mb-4">
        <div className="mb-4 flex items-center justify-between">
          <button onClick={() => move(-1)} aria-label="前の月"
                  className="rounded-lg border border-slate-200 px-3 py-2 font-semibold text-slate-600 active:bg-slate-100">‹</button>
          <div className="tnum text-lg font-bold text-slate-800">{year}年 {month + 1}月</div>
          <button onClick={() => move(1)} aria-label="次の月"
                  className="rounded-lg border border-slate-200 px-3 py-2 font-semibold text-slate-600 active:bg-slate-100">›</button>
        </div>

        <div className="mb-1 grid grid-cols-7 text-center text-xs font-semibold text-slate-400">
          {WEEK.map((w, i) => (
            <div key={w} className={i === 0 ? 'text-rose-400' : i === 6 ? 'text-sky-400' : ''}>{w}</div>
          ))}
        </div>

        <div className="grid grid-cols-7 gap-1">
          {cells.map((date, i) => {
            if (!date) return <div key={`empty-${i}`} />
            const has = byDate.has(date)
            const isToday = date === today()
            return (
              <button
                key={date}
                onClick={() => open(date)}
                className={`tnum flex aspect-square flex-col items-center justify-center rounded-lg text-base font-semibold transition ${
                  has ? 'bg-indigo-600 text-white' : 'bg-slate-50 text-slate-500 active:bg-slate-100'
                } ${isToday && !has ? 'ring-2 ring-indigo-400' : ''}`}
              >
                {Number(date.slice(-2))}
              </button>
            )
          })}
        </div>

        <div className="tnum mt-4 text-center text-sm text-slate-400">この月の記録：{monthCount}日</div>
      </Card>

      <Sheet open={picked !== null} title={picked ? formatJP(picked) : ''} onClose={() => { setPicked(null); setEditing(false) }}>
        {picked && !editing && current && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-xl bg-slate-50 p-4">
                <div className="text-sm font-semibold text-slate-400">身長</div>
                <div className="tnum text-3xl font-bold text-indigo-600">
                  {current.height.toFixed(1)}<span className="ml-0.5 text-base text-slate-400">cm</span>
                </div>
              </div>
              <div className="rounded-xl bg-slate-50 p-4">
                <div className="text-sm font-semibold text-slate-400">体重</div>
                <div className="tnum text-3xl font-bold text-teal-600">
                  {current.weight.toFixed(1)}<span className="ml-0.5 text-base text-slate-400">kg</span>
                </div>
              </div>
            </div>
            <div className="rounded-xl bg-slate-50 p-4 text-slate-600">{current.memo || 'メモなし'}</div>
            <BigButton onClick={() => setEditing(true)}>修正する</BigButton>
            <BigButton color="danger" onClick={() => { onDelete(picked); setPicked(null) }}>この日の記録を削除</BigButton>
          </div>
        )}

        {picked && editing && (
          <div className="space-y-5">
            <NumberField label="身長" unit="cm" value={height} onChange={setHeight} min={30} max={250} />
            <NumberField label="体重" unit="kg" value={weight} onChange={setWeight} min={2} max={150} />
            <div>
              <div className="mb-2 text-base font-semibold text-slate-500">ひとことメモ</div>
              <input value={memo} onChange={(e) => setMemo(e.target.value)}
                     className="w-full rounded-xl border border-slate-300 px-4 py-3.5 text-lg outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100" />
            </div>
            <BigButton onClick={() => {
              onSave({ date: picked, height, weight, memo: memo.trim() })
              setPicked(null); setEditing(false)
            }}>保存する</BigButton>
            <BigButton color="ghost" onClick={() => (current ? setEditing(false) : setPicked(null))}>キャンセル</BigButton>
          </div>
        )}
      </Sheet>
    </div>
  )
}
