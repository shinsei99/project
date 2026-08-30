/** 設定（ホームの歯車から開く）。プロフィール変更・開発用のサンプル投入・全消去 */
import { useState } from 'react'
import type { Profile } from '../types'
import { BigButton, Card } from '../components/ui'
import { Setup } from './Setup'

export function Settings({
  profile, recordCount, onSaveProfile, onLoadSample, onClearAll, onClose,
}: {
  profile: Profile
  recordCount: number
  onSaveProfile: (p: Profile) => void
  onLoadSample: () => void
  onClearAll: () => void
  onClose: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [confirming, setConfirming] = useState(false)

  if (editing) {
    return (
      <Setup
        initial={profile}
        onDone={(p) => { onSaveProfile(p); setEditing(false) }}
        onCancel={() => setEditing(false)}
      />
    )
  }

  return (
    <div className="mx-auto max-w-md px-5 py-6">
      <header className="mb-5 flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight text-slate-800">設定</h1>
        <button onClick={onClose} className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 font-semibold text-slate-600 active:bg-slate-100">
          閉じる
        </button>
      </header>

      <Card className="mb-4">
        <div className="mb-3 space-y-1">
          <Row label="名前" value={profile.name} />
          <Row label="誕生日" value={profile.birthday} />
          <Row label="性別" value={profile.gender === 'boy' ? '男子' : '女子'} />
          <Row label="目標身長" value={profile.targetHeight ? `${profile.targetHeight} cm` : '未設定'} />
          <Row label="記録の数" value={`${recordCount} 件`} />
        </div>
        <BigButton onClick={() => setEditing(true)}>プロフィールを変更</BigButton>
      </Card>

      <Card className="mb-4">
        <div className="mb-1 text-base font-semibold text-slate-600">開発用</div>
        <p className="mb-3 text-sm text-slate-400">
          過去3か月ぶん（＋「1年前の自分」を確認するための1年前の数日）のサンプルを入れます。
          いまの記録は<b className="text-slate-600">置き換わります</b>。
        </p>
        <BigButton color="ghost" onClick={onLoadSample}>サンプルデータを入れる</BigButton>
      </Card>

      <Card>
        <div className="mb-1 text-base font-semibold text-rose-600">データを全部消す</div>
        <p className="mb-3 text-sm text-slate-400">
          記録・プロフィール・家族・バッジをすべて削除します。元には戻せません。
        </p>
        {confirming ? (
          <div className="space-y-3">
            <p className="text-center font-semibold text-rose-600">本当に消しますか？</p>
            <BigButton color="danger" onClick={onClearAll}>はい、削除します</BigButton>
            <BigButton color="ghost" onClick={() => setConfirming(false)}>キャンセル</BigButton>
          </div>
        ) : (
          <BigButton color="danger" onClick={() => setConfirming(true)}>データを全部消す</BigButton>
        )}
      </Card>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between border-b border-slate-100 py-2 last:border-0">
      <span className="text-sm font-semibold text-slate-400">{label}</span>
      <span className="tnum font-semibold text-slate-700">{value}</span>
    </div>
  )
}
