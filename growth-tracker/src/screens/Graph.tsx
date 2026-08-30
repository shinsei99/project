/** グラフ画面。身長/体重の切り替え・期間の切り替え・平均身長ライン・目標ライン・点タップ */
import { useMemo, useState } from 'react'
import {
  CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import type { GrowthRecord, Profile } from '../types'
import { Card } from '../components/ui'
import { addDays, ageInYears, formatJP, formatShort, today } from '../lib/date'
import { averageHeight } from '../lib/average'

type Metric = 'height' | 'weight'
type Range = '1m' | '1y' | 'all'

interface Point {
  date: string
  label: string
  value: number
  avg: number | null
  memo: string
}

export function Graph({ profile, records }: { profile: Profile; records: GrowthRecord[] }) {
  const [metric, setMetric] = useState<Metric>('height')
  const [range, setRange] = useState<Range>('1m')
  const [picked, setPicked] = useState<Point | null>(null)

  const data = useMemo<Point[]>(() => {
    const from = range === 'all' ? '0000-01-01' : addDays(today(), range === '1m' ? -31 : -366)
    return [...records]
      .filter((r) => r.date >= from)
      .sort((a, b) => a.date.localeCompare(b.date))
      .map((r) => ({
        date: r.date,
        label: formatShort(r.date),
        value: metric === 'height' ? r.height : r.weight,
        avg: metric === 'height' ? averageHeight(profile.gender, ageInYears(profile.birthday, r.date)) : null,
        memo: r.memo,
      }))
  }, [records, range, metric, profile.gender, profile.birthday])

  const unit = metric === 'height' ? 'cm' : 'kg'
  const color = metric === 'height' ? '#4f46e5' : '#0d9488'
  const target = metric === 'height' ? profile.targetHeight : null

  // 目盛りの範囲。平均線と目標線も入るように、線が画面外へ出ないよう広げる
  const domain = useMemo<[number, number]>(() => {
    const values = data.flatMap((d) => [d.value, ...(d.avg !== null ? [d.avg] : [])])
    if (values.length === 0) return [0, 1]
    const min = Math.min(...values)
    const max = Math.max(...values)
    const pad = Math.max(1, (max - min) * 0.15)
    return [Math.floor(min - pad), Math.ceil(max + pad)]
  }, [data])

  // 目標が今の身長よりずっと上だと、線を入れた瞬間にグラフが潰れて変化が見えなくなる。
  // 目盛りの中に入るときだけ線を引き、遠いときは「あと何cm」を文字で出す。
  const latest = data.length > 0 ? data[data.length - 1].value : null
  const targetInView = target !== null && target <= domain[1] + 1
  const targetRemain = target !== null && latest !== null ? Math.round((target - latest) * 10) / 10 : null

  return (
    <div className="mx-auto max-w-md px-5 pt-6">
      <h1 className="mb-4 text-2xl font-bold tracking-tight text-slate-800">グラフ</h1>

      <div className="mb-3 flex gap-2">
        {([['height', '身長'], ['weight', '体重']] as const).map(([m, label]) => (
          <button
            key={m}
            onClick={() => { setMetric(m); setPicked(null) }}
            className={`flex-1 rounded-xl border py-3 text-lg font-semibold transition ${
              metric === m
                ? 'border-indigo-600 bg-indigo-600 text-white'
                : 'border-slate-200 bg-white text-slate-500'
            }`}
          >{label}</button>
        ))}
      </div>

      <div className="mb-4 flex gap-2">
        {([['1m', '1か月'], ['1y', '1年'], ['all', 'すべて']] as const).map(([r, label]) => (
          <button
            key={r}
            onClick={() => { setRange(r); setPicked(null) }}
            className={`flex-1 rounded-lg border py-2 text-sm font-semibold transition ${
              range === r
                ? 'border-slate-800 bg-slate-800 text-white'
                : 'border-slate-200 bg-white text-slate-500'
            }`}
          >{label}</button>
        ))}
      </div>

      <Card className="mb-4 px-2 py-4">
        {data.length === 0 ? (
          <p className="py-16 text-center text-slate-400">まだ記録がありません</p>
        ) : (
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={data}
                margin={{ top: 8, right: 12, bottom: 4, left: -12 }}
                onClick={(state: unknown) => {
                  // recharts のクリックは活性中の点を activePayload で渡してくる
                  const p = (state as { activePayload?: { payload: Point }[] } | null)?.activePayload?.[0]?.payload
                  if (p) setPicked(p)
                }}
              >
                <CartesianGrid stroke="#eef2f7" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 12, fill: '#94a3b8' }} interval="preserveStartEnd" minTickGap={24} />
                <YAxis domain={domain} tick={{ fontSize: 12, fill: '#94a3b8' }} width={52}
                       tickFormatter={(v: number) => String(Math.round(v))} />
                <Tooltip
                  contentStyle={{ borderRadius: 12, border: '1px solid #e2e8f0', boxShadow: '0 6px 20px rgba(15,23,42,.10)', fontWeight: 600 }}
                />
                {metric === 'height' && (
                  <Line type="monotone" dataKey="avg" name="平均" stroke="#94a3b8" strokeWidth={2}
                        strokeDasharray="2 4" dot={false} connectNulls isAnimationActive={false} />
                )}
                <Line type="monotone" dataKey="value" name={metric === 'height' ? '身長' : '体重'}
                      stroke={color} strokeWidth={4} isAnimationActive={false}
                      dot={{ r: 4, fill: color }} activeDot={{ r: 8 }} />
                {target && targetInView && (
                  <ReferenceLine y={target} stroke="#e11d48" strokeDasharray="6 6" strokeWidth={2}
                                 label={{ value: `目標 ${target}cm`, position: 'insideTopRight', fill: '#e11d48', fontSize: 12, fontWeight: 700 }} />
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>

      <div className="mb-4 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-sm text-slate-400">
        {metric === 'height' && <span>灰色の点線＝同学年の平均身長（目安）</span>}
        {metric === 'height' && target !== null && !targetInView && targetRemain !== null && (
          <span className="tnum font-semibold text-rose-600">目標 {target}cm まであと {targetRemain.toFixed(1)}cm</span>
        )}
      </div>

      {picked && (
        <Card className="mb-4">
          <div className="tnum text-sm font-semibold text-slate-400">{formatJP(picked.date)}</div>
          <div className="tnum text-3xl font-bold" style={{ color }}>
            {picked.value.toFixed(1)}<span className="ml-0.5 text-base font-semibold text-slate-400">{unit}</span>
          </div>
          {picked.avg !== null && (
            <div className="tnum text-sm text-slate-500">
              平均 {picked.avg.toFixed(1)}cm（{picked.value >= picked.avg ? '+' : '−'}{Math.abs(picked.value - picked.avg).toFixed(1)}cm）
            </div>
          )}
          <div className="mt-2 text-slate-600">{picked.memo || 'メモなし'}</div>
        </Card>
      )}
      {!picked && data.length > 0 && (
        <p className="mb-4 text-center text-sm text-slate-400">グラフの点をタップすると、その日の記録が見られます</p>
      )}
    </div>
  )
}
