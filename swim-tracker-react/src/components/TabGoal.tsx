import { useState } from 'react';
import type { User, SwimRecord, Goal } from '../types';
import { saveGoal, deleteGoal } from '../db';
import { EVENT_DISTANCES, COURSE_OPTIONS } from '../joStandards';
import { parseTimeInput, secondsToStr } from '../utils/time';

interface Props {
  user: User;
  records: SwimRecord[];
  goals: Goal[];
  onGoalsChange: () => void;
}

function bestTime(records: SwimRecord[], event: string, distance: number, course: string): SwimRecord | null {
  const s = records.filter(r => r.event === event && r.distance === distance && r.course === course);
  if (!s.length) return null;
  return s.reduce((a, b) => a.timeSec < b.timeSec ? a : b);
}

export default function TabGoal({ user, records, goals, onGoalsChange }: Props) {
  const events = Object.keys(EVENT_DISTANCES);
  const today = new Date().toISOString().slice(0, 10);
  const [gEvent, setGEvent] = useState(events[0]);
  const [gDistance, setGDistance] = useState(EVENT_DISTANCES[events[0]][0]);
  const [gCourse, setGCourse] = useState(COURSE_OPTIONS[0]);
  const [gTimeStr, setGTimeStr] = useState('');
  const [gDeadline, setGDeadline] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() + 90);
    return d.toISOString().slice(0, 10);
  });
  const [gMemo, setGMemo] = useState('');
  const [error, setError] = useState('');

  async function handleSave() {
    const parsed = parseTimeInput(gTimeStr);
    if (parsed === null) { setError('目標タイムを正しく入力してください（例: 1:23.45 または 27.89）'); return; }
    const goal: Goal = {
      id: crypto.randomUUID().slice(0, 8),
      userId: user.id, event: gEvent, distance: gDistance, course: gCourse,
      targetSec: parsed, targetStr: secondsToStr(parsed),
      deadline: gDeadline, memo: gMemo.trim(),
      createdAt: new Date().toISOString(),
    };
    await saveGoal(goal);
    onGoalsChange();
    setGTimeStr(''); setGMemo(''); setError('');
  }

  async function handleDelete(id: string) {
    await deleteGoal(id);
    onGoalsChange();
  }

  const gParsed = parseTimeInput(gTimeStr);

  return (
    <div>
      <div className="section-title">🎯 目標管理</div>

      {goals.length === 0 ? (
        <div className="empty-state"><div className="empty-icon">🎯</div><p>目標が設定されていません</p></div>
      ) : (
        <div>
          {goals.map(g => {
            const daysLeft = Math.floor((Date.parse(g.deadline) - Date.parse(today)) / 86400000);
            const current = bestTime(records, g.event, g.distance, g.course);
            const achieved = current !== null && current.timeSec <= g.targetSec;
            const expired = daysLeft < 0 && !achieved;
            const cardClass = `goal-card ${achieved ? 'done' : expired ? 'expired' : 'active'}`;
            const diff = current ? current.timeSec - g.targetSec : null;
            let statusText = '';
            if (achieved) statusText = `✅ 達成済み（現在 ${current!.timeStr}）`;
            else if (expired) statusText = `⏰ 期限切れ（${Math.abs(daysLeft)}日超過）`;
            else if (diff !== null) statusText = `🎯 あと ${diff.toFixed(2)}秒　残り ${daysLeft}日`;
            else statusText = `🎯 記録なし　残り ${daysLeft}日`;
            return (
              <div key={g.id} className={cardClass}>
                <div className="goal-card-content">
                  <strong>{g.event} {g.distance}m {g.course}</strong><br />
                  目標: <strong>{g.targetStr}</strong>　期限: {g.deadline}
                  <div className="goal-status">{statusText}</div>
                  {g.memo && <div className="goal-memo">📝 {g.memo}</div>}
                </div>
                <button className="btn btn-danger btn-sm" onClick={() => handleDelete(g.id)}>削除</button>
              </div>
            );
          })}
        </div>
      )}

      <div className="divider" />
      <div className="section-title">新しい目標を追加</div>
      <div className="card">
        <div className="form-group">
          <label>種目</label>
          <select value={gEvent} onChange={e => { setGEvent(e.target.value); setGDistance(EVENT_DISTANCES[e.target.value][0]); }}>
            {events.map(ev => <option key={ev} value={ev}>{ev}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label>距離</label>
          <select value={gDistance} onChange={e => setGDistance(Number(e.target.value))}>
            {EVENT_DISTANCES[gEvent].map(d => <option key={d} value={d}>{d}m</option>)}
          </select>
        </div>
        <div className="form-group">
          <label>コース</label>
          <div className="radio-group">{COURSE_OPTIONS.map(c => <label key={c}><input type="radio" checked={gCourse === c} onChange={() => setGCourse(c)} />{c}</label>)}</div>
        </div>
        <div className="form-group">
          <label>目標タイム（例: 1:23.45 または 27.89）</label>
          <input type="text" value={gTimeStr} onChange={e => setGTimeStr(e.target.value)} placeholder="例: 1:23.45" />
          {gTimeStr && (gParsed !== null
            ? <p className="hint hint-success">✅ {secondsToStr(gParsed)}</p>
            : <p className="hint hint-error">形式が正しくありません</p>
          )}
        </div>
        <div className="form-group">
          <label>達成期限</label>
          <input type="date" value={gDeadline} onChange={e => setGDeadline(e.target.value)} min={today} />
        </div>
        <div className="form-group">
          <label>メモ（任意）</label>
          <input type="text" value={gMemo} onChange={e => setGMemo(e.target.value)} placeholder="例: ○○大会で達成する" />
        </div>
        {error && <p className="hint hint-error">{error}</p>}
        <button className="btn btn-primary btn-full" onClick={handleSave} disabled={gParsed === null}>
          🎯 目標を保存
        </button>
      </div>
    </div>
  );
}
