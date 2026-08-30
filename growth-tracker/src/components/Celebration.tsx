/** 新しいバッジを取ったときの表示。押すか数秒で消える */
import { useEffect } from 'react'
import type { BadgeDef } from '../lib/badges'

export function Celebration({ badges, onClose }: { badges: BadgeDef[]; onClose: () => void }) {
  useEffect(() => {
    const id = setTimeout(onClose, 3500)
    return () => clearTimeout(id)
  }, [onClose])

  if (badges.length === 0) return null
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-900/55 p-6" onClick={onClose}>
      <div className="w-full max-w-sm rounded-2xl bg-white p-7 text-center shadow-xl">
        <div className="mb-1 text-sm font-semibold tracking-widest text-indigo-500">NEW BADGE</div>
        <div className="mb-5 text-2xl font-bold text-slate-800">
          バッジを{badges.length}個 獲得
        </div>
        <div className="space-y-2">
          {badges.map((b) => (
            <div key={b.id} className="flex items-center justify-between rounded-xl border border-slate-200 px-4 py-3 text-left">
              <span className="tnum text-lg font-bold text-slate-800">{b.label}</span>
              <span className="text-sm text-slate-500">{b.description}</span>
            </div>
          ))}
        </div>
        <div className="mt-5 text-sm text-slate-400">タップで閉じる</div>
      </div>
    </div>
  )
}
