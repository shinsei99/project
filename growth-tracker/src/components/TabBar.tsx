/** 画面下のタブ。絵文字ではなく線アイコンで、押せる高さは 56px 以上を確保する */
export type Tab = 'home' | 'graph' | 'compare' | 'calendar'

const ICONS: Record<Tab, string> = {
  // 24x24 の線アイコン（stroke で描く）
  home: 'M3 10.5 12 3l9 7.5M5.5 9.5V20h13V9.5',
  graph: 'M4 19V5M4 19h16M7.5 15l3.5-4.5 3 3L20 7',
  compare: 'M6 20V8m12 12V4M6 8l-2.5 2.5M6 8l2.5 2.5M18 4l-2.5 2.5M18 4l2.5 2.5M3 20h18',
  calendar: 'M4 8.5h16M7 4v3m10-3v3M5 20h14a1 1 0 0 0 1-1V7.5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1V19a1 1 0 0 0 1 1Z',
}

const TABS: { id: Tab; label: string }[] = [
  { id: 'home', label: 'ホーム' },
  { id: 'graph', label: 'グラフ' },
  { id: 'compare', label: 'くらべる' },
  { id: 'calendar', label: 'カレンダー' },
]

export function TabBar({ tab, onChange }: { tab: Tab; onChange: (t: Tab) => void }) {
  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-md pb-[env(safe-area-inset-bottom)]">
        {TABS.map((t) => {
          const active = t.id === tab
          return (
            <button
              key={t.id}
              onClick={() => onChange(t.id)}
              className={`flex flex-1 flex-col items-center gap-1 py-3 text-xs font-semibold transition ${
                active ? 'text-indigo-600' : 'text-slate-400'
              }`}
              aria-current={active ? 'page' : undefined}
            >
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none"
                   stroke="currentColor" strokeWidth={active ? 2.2 : 1.8}
                   strokeLinecap="round" strokeLinejoin="round">
                <path d={ICONS[t.id]} />
              </svg>
              {t.label}
            </button>
          )
        })}
      </div>
    </nav>
  )
}
