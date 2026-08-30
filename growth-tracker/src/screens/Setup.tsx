/** 初回だけ出る設定画面。プロフィールが無いあいだはここしか出さない（設定変更でも再利用する） */
import { useState } from 'react'
import type { Gender, Profile } from '../types'
import { BigButton, Card } from '../components/ui'
import { today } from '../lib/date'

export function Setup({ initial, onDone, onCancel }: {
  initial?: Profile | null
  onDone: (p: Profile) => void
  onCancel?: () => void
}) {
  const [name, setName] = useState(initial?.name ?? '')
  const [birthday, setBirthday] = useState(initial?.birthday ?? '')
  const [gender, setGender] = useState<Gender>(initial?.gender ?? 'boy')
  const [target, setTarget] = useState(initial?.targetHeight ? String(initial.targetHeight) : '')

  const ok = name.trim().length > 0 && birthday.length === 10 && birthday <= today()

  const submit = () => {
    if (!ok) return
    onDone({
      name: name.trim(),
      birthday,
      gender,
      targetHeight: target.trim() === '' ? null : Number(target),
    })
  }

  const field = 'w-full rounded-xl border border-slate-300 bg-white px-4 py-3.5 text-lg outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100'

  return (
    <div className="mx-auto max-w-md px-5 py-8">
      <h1 className="text-2xl font-bold tracking-tight text-slate-800">
        {initial ? 'プロフィールを変更' : 'GrowLog をはじめる'}
      </h1>
      <p className="mb-6 mt-1 text-slate-500">
        {initial ? '内容はあとからいつでも変えられます' : '最初に自分のことを登録してください'}
      </p>

      <Card className="space-y-5">
        <div>
          <label className="mb-2 block text-base font-semibold text-slate-500">名前</label>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="例：みなと" className={field} />
        </div>

        <div>
          <label className="mb-2 block text-base font-semibold text-slate-500">誕生日</label>
          <input type="date" value={birthday} max={today()} onChange={(e) => setBirthday(e.target.value)} className={`tnum ${field}`} />
        </div>

        <div>
          <div className="mb-2 text-base font-semibold text-slate-500">性別</div>
          <div className="flex gap-2">
            {([['boy', '男子'], ['girl', '女子']] as const).map(([g, label]) => (
              <button
                key={g}
                onClick={() => setGender(g)}
                className={`flex-1 rounded-xl border py-3.5 text-lg font-semibold transition ${
                  gender === g
                    ? 'border-indigo-600 bg-indigo-600 text-white'
                    : 'border-slate-300 bg-white text-slate-600'
                }`}
              >{label}</button>
            ))}
          </div>
          <p className="mt-2 text-sm text-slate-400">グラフに重ねる平均身長ラインの判定に使います</p>
        </div>

        <div>
          <label className="mb-2 block text-base font-semibold text-slate-500">
            目標身長 <span className="font-normal text-slate-400">（任意）</span>
          </label>
          <div className="flex items-center gap-2">
            <input type="number" inputMode="decimal" value={target} onChange={(e) => setTarget(e.target.value)}
                   placeholder="150" className={`tnum ${field}`} />
            <span className="text-lg font-semibold text-slate-400">cm</span>
          </div>
        </div>
      </Card>

      <div className="mt-6 space-y-3">
        <BigButton onClick={submit} disabled={!ok}>{initial ? '保存する' : 'はじめる'}</BigButton>
        {onCancel && <BigButton color="ghost" onClick={onCancel}>キャンセル</BigButton>}
      </div>
      {!ok && <p className="mt-3 text-center text-sm text-slate-400">名前と誕生日を入力してください</p>}
    </div>
  )
}
