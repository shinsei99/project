/** 画面共通の部品。余白・角丸・文字サイズの決まりはここに集約する */
import type { ReactNode } from 'react'

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_1px_3px_rgba(15,23,42,0.06)] ${className}`}>
      {children}
    </div>
  )
}

export function BigButton({
  children, onClick, color = 'primary', disabled = false, type = 'button',
}: {
  children: ReactNode
  onClick?: () => void
  color?: 'primary' | 'teal' | 'ghost' | 'danger'
  disabled?: boolean
  type?: 'button' | 'submit'
}) {
  const colors = {
    primary: 'bg-indigo-600 text-white active:bg-indigo-700',
    teal: 'bg-teal-600 text-white active:bg-teal-700',
    ghost: 'border border-slate-300 bg-white text-slate-700 active:bg-slate-100',
    danger: 'bg-rose-600 text-white active:bg-rose-700',
  }
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`w-full rounded-xl px-6 py-4 text-lg font-semibold transition active:scale-[0.99] disabled:opacity-40 ${colors[color]}`}
    >
      {children}
    </button>
  )
}

/** 数値入力。0.1 きざみの増減ボタンを付けて、スマホでも指で合わせられるようにする */
export function NumberField({
  label, unit, value, onChange, step = 0.1, min = 0, max = 300,
}: {
  label: string
  unit: string
  value: number
  onChange: (v: number) => void
  step?: number
  min?: number
  max?: number
}) {
  const clamp = (v: number) => Math.min(max, Math.max(min, Math.round(v * 10) / 10))
  return (
    <div>
      <div className="mb-2 text-base font-semibold text-slate-500">{label}</div>
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => onChange(clamp(value - step))}
          className="h-13 w-13 shrink-0 rounded-xl border border-slate-300 bg-white text-2xl font-semibold text-slate-600 active:bg-slate-100"
          style={{ height: 52, width: 52 }}
          aria-label={`${label}を減らす`}
        >−</button>
        <div className="flex flex-1 items-baseline justify-center rounded-xl bg-slate-100 px-3 py-2">
          <input
            type="number"
            inputMode="decimal"
            step={step}
            value={Number.isFinite(value) ? value : ''}
            onChange={(e) => onChange(clamp(Number(e.target.value)))}
            className="tnum w-full bg-transparent text-center text-4xl font-bold text-slate-800 outline-none"
          />
          <span className="ml-1 text-lg font-semibold text-slate-400">{unit}</span>
        </div>
        <button
          type="button"
          onClick={() => onChange(clamp(value + step))}
          className="shrink-0 rounded-xl border border-slate-300 bg-white text-2xl font-semibold text-slate-600 active:bg-slate-100"
          style={{ height: 52, width: 52 }}
          aria-label={`${label}を増やす`}
        >＋</button>
      </div>
    </div>
  )
}

/** 下から出るシート。スマホで親指の届く位置に操作を置く */
export function Sheet({
  open, title, onClose, children,
}: { open: boolean; title: string; onClose: () => void; children: ReactNode }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/45" onClick={onClose}>
      <div
        className="max-h-[92dvh] w-full max-w-md overflow-y-auto rounded-t-2xl bg-white p-6 pb-[calc(1.5rem+env(safe-area-inset-bottom))]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mx-auto mb-4 h-1 w-10 rounded-full bg-slate-200" />
        <h2 className="mb-5 text-xl font-bold text-slate-800">{title}</h2>
        {children}
      </div>
    </div>
  )
}

/** 前回との差 */
export function Diff({ value, unit }: { value: number | null; unit: string }) {
  if (value === null) return <span className="text-sm text-slate-400">最初の記録</span>
  const same = Math.abs(value) < 0.05
  const up = value > 0
  const color = same ? 'text-slate-400' : up ? 'text-emerald-600' : 'text-sky-600'
  const sign = same ? '±' : up ? '+' : '−'
  return (
    <span className={`tnum text-sm font-semibold ${color}`}>
      前回比 {sign}{Math.abs(value).toFixed(1)}{unit}
    </span>
  )
}

/** バッジのチップ表示 */
export function BadgeChip({ label, tone = 'indigo' }: { label: string; tone?: string }) {
  const tones: Record<string, string> = {
    indigo: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    amber: 'bg-amber-50 text-amber-700 border-amber-200',
    teal: 'bg-teal-50 text-teal-700 border-teal-200',
  }
  return (
    <span className={`tnum rounded-lg border px-2.5 py-1 text-sm font-semibold ${tones[tone] ?? tones.indigo}`}>
      {label}
    </span>
  )
}
