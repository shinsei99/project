/** バッジ一覧（ホームから開く） */
import type { BadgeDef } from '../lib/badges'
import type { EarnedBadge } from '../types'
import { Sheet } from './ui'

export function BadgeList({
  open, badges, earned, onClose,
}: { open: boolean; badges: BadgeDef[]; earned: EarnedBadge[]; onClose: () => void }) {
  const dateOf = (id: string) => earned.find((e) => e.id === id)?.date ?? ''
  return (
    <Sheet open={open} title="獲得したバッジ" onClose={onClose}>
      {badges.length === 0 ? (
        <p className="py-10 text-center text-slate-400">
          まだありません。記録をつけると増えていきます。
        </p>
      ) : (
        <div className="space-y-2">
          {badges.map((b) => (
            <div key={b.id} className="flex items-center justify-between rounded-xl border border-slate-200 px-4 py-3">
              <div>
                <div className="tnum text-lg font-bold text-slate-800">{b.label}</div>
                <div className="text-sm text-slate-500">{b.description}</div>
              </div>
              {dateOf(b.id) && <div className="tnum text-xs text-slate-400">{dateOf(b.id)}</div>}
            </div>
          ))}
        </div>
      )}
    </Sheet>
  )
}
