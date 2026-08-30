/**
 * 画面の出し分けと、localStorage への保存をまとめて持つ場所。
 * 各画面は「もらった値を出す」「変更を関数で返す」だけにして、保存の責任をここに一本化している。
 */
import { useEffect, useMemo, useState } from 'react'
import type { EarnedBadge, FamilyMember, GrowthRecord, Profile } from './types'
import { store, upsertRecord } from './lib/storage'
import { computeBadges, findNewBadges, type BadgeDef } from './lib/badges'
import { makeSampleRecords } from './lib/sample'
import { today } from './lib/date'
import { TabBar, type Tab } from './components/TabBar'
import { Celebration } from './components/Celebration'
import { BadgeList } from './components/BadgeList'
import { Setup } from './screens/Setup'
import { Home } from './screens/Home'
import { Settings } from './screens/Settings'
import { Graph } from './screens/Graph'
import { Compare } from './screens/Compare'
import { CalendarScreen } from './screens/CalendarScreen'

export default function App() {
  const [profile, setProfile] = useState<Profile | null>(() => store.loadProfile())
  const [records, setRecords] = useState<GrowthRecord[]>(() => store.loadRecords())
  const [family, setFamily] = useState<FamilyMember[]>(() => store.loadFamily())
  const [earned, setEarned] = useState<EarnedBadge[]>(() => store.loadBadges())

  const [tab, setTab] = useState<Tab>('home')
  const [showSettings, setShowSettings] = useState(false)
  const [showBadges, setShowBadges] = useState(false)
  const [celebrate, setCelebrate] = useState<BadgeDef[]>([])

  // 記録から毎回まるごと計算し直す（状態を二重に持たない）
  const badges = useMemo(() => computeBadges(records), [records])

  // 新しく取ったバッジがあれば、獲得日を保存してお祝いを出す
  useEffect(() => {
    const fresh = findNewBadges(badges, earned)
    if (fresh.length === 0) return
    const next = [...earned, ...fresh.map((b) => ({ id: b.id, date: today() }))]
    setEarned(next)
    store.saveBadges(next)
    setCelebrate(fresh)
  }, [badges, earned])

  const saveProfile = (p: Profile) => { setProfile(p); store.saveProfile(p) }

  const saveRecord = (r: GrowthRecord) => {
    const next = upsertRecord(records, r)
    setRecords(next); store.saveRecords(next)
  }

  const deleteRecord = (date: string) => {
    const next = records.filter((r) => r.date !== date)
    setRecords(next); store.saveRecords(next)
  }

  const saveFamily = (f: FamilyMember[]) => { setFamily(f); store.saveFamily(f) }

  const loadSample = () => {
    const next = makeSampleRecords()
    setRecords(next); store.saveRecords(next)
    setShowSettings(false)
    setTab('home')
  }

  const clearAll = () => {
    store.clearAll()
    setProfile(null); setRecords([]); setFamily([]); setEarned([])
    setShowSettings(false); setTab('home')
  }

  // プロフィールが無いあいだは初回設定だけを出す
  if (!profile) return <Setup onDone={saveProfile} />

  if (showSettings) {
    return (
      <Settings
        profile={profile}
        recordCount={records.length}
        onSaveProfile={saveProfile}
        onLoadSample={loadSample}
        onClearAll={clearAll}
        onClose={() => setShowSettings(false)}
      />
    )
  }

  return (
    <div className="min-h-dvh pb-24">
      {tab === 'home' && (
        <Home
          profile={profile}
          records={records}
          badges={badges}
          onSave={saveRecord}
          onOpenSettings={() => setShowSettings(true)}
          onOpenBadges={() => setShowBadges(true)}
        />
      )}
      {tab === 'graph' && <Graph profile={profile} records={records} />}
      {tab === 'compare' && <Compare profile={profile} records={records} family={family} onSaveFamily={saveFamily} />}
      {tab === 'calendar' && <CalendarScreen records={records} onSave={saveRecord} onDelete={deleteRecord} />}

      <BadgeList open={showBadges} badges={badges} earned={earned} onClose={() => setShowBadges(false)} />
      <Celebration badges={celebrate} onClose={() => setCelebrate([])} />
      <TabBar tab={tab} onChange={setTab} />
    </div>
  )
}
