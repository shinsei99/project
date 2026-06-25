import { useState, useEffect } from 'react';
import type { User, SwimRecord } from '../types';
import { saveRecord, getPools, savePools } from '../db';
import { EVENT_DISTANCES, COURSE_OPTIONS, QUALIF_OPTIONS, getJoTime } from '../joStandards';
import { parseTimeInput, secondsToStr } from '../utils/time';

interface Props {
  user: User;
  records: SwimRecord[];
  joCategory: string;
  onRecordsChange: () => void;
}

function bestTime(records: SwimRecord[], event: string, distance: number, course: string): SwimRecord | null {
  const subset = records.filter(r => r.event === event && r.distance === distance && r.course === course);
  if (!subset.length) return null;
  return subset.reduce((a, b) => a.timeSec < b.timeSec ? a : b);
}

export default function TabInput({ user, records, joCategory, onRecordsChange }: Props) {
  const events = Object.keys(EVENT_DISTANCES);
  const [event, setEvent] = useState(events[0]);
  const [distance, setDistance] = useState(EVENT_DISTANCES[events[0]][0]);
  const [course, setCourse] = useState(COURSE_OPTIONS[0]);
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [splitInputs, setSplitInputs] = useState<string[]>([]);
  const [timeStr, setTimeStr] = useState('');
  const [refTimeStr, setRefTimeStr] = useState('');
  const [reactionTime, setReactionTime] = useState(0.65);
  const [qualifGrade, setQualifGrade] = useState('なし');
  const [meetName, setMeetName] = useState('');
  const [poolSel, setPoolSel] = useState('未入力');
  const [newPoolInput, setNewPoolInput] = useState('');
  const [pools, setPools] = useState<string[]>([]);
  const [savedMsg, setSavedMsg] = useState<{ best: boolean; pbInfo?: string; joInfo?: string } | null>(null);

  useEffect(() => {
    getPools().then(setPools);
  }, []);

  useEffect(() => {
    const numSplits = distance / 50;
    setSplitInputs(Array(numSplits).fill(''));
    setSavedMsg(null);
  }, [event, distance, course]);

  const distances = EVENT_DISTANCES[event];
  const numSplits = distance / 50;

  // Compute passage and lap times
  let passageSecs: (number | null)[] = [];
  let lapSecs: (number | null)[] = [];
  let splitsValid = true;
  let prevSec = 0;
  for (let i = 0; i < splitInputs.length; i++) {
    const s = splitInputs[i];
    if (s.trim()) {
      const sec = parseTimeInput(s);
      if (sec === null) { splitsValid = false; passageSecs.push(null); lapSecs.push(null); }
      else { passageSecs.push(sec); lapSecs.push(sec - prevSec); prevSec = sec; }
    } else { passageSecs.push(null); lapSecs.push(null); }
  }

  const parsedSec = parseTimeInput(timeStr);
  const refParsed = parseTimeInput(refTimeStr);

  async function handleSave() {
    if (parsedSec === null) return;
    const poolName = poolSel === '新しいプールを追加...' ? newPoolInput.trim() : poolSel === '未入力' ? '' : poolSel;
    if (poolSel === '新しいプールを追加...' && newPoolInput.trim() && !pools.includes(newPoolInput.trim())) {
      const newPools = [...pools, newPoolInput.trim()];
      await savePools(newPools);
      setPools(newPools);
    }
    const prev = bestTime(records, event, distance, course);
    const isNewBest = !prev || parsedSec < prev.timeSec;
    const passageStr = splitInputs.map(s => s.trim()).join(';').replace(/;+$/, '');
    const lapStr = lapSecs.map(l => l !== null ? secondsToStr(l) : '').join(';').replace(/;+$/, '');
    const rec: SwimRecord = {
      id: crypto.randomUUID(),
      userId: user.id,
      date,
      event,
      distance,
      course,
      timeSec: parsedSec,
      timeStr: secondsToStr(parsedSec),
      reactionTime,
      qualifGrade,
      meetName,
      poolName,
      splitTimes: passageStr,
      lapTimes: lapStr,
      createdAt: new Date().toISOString(),
    };
    await saveRecord(rec);
    onRecordsChange();
    const joTime = getJoTime(joCategory, user.gender, event, distance, course);
    let joInfo = '';
    if (joTime !== null) {
      const diff = parsedSec - joTime;
      joInfo = diff <= 0
        ? `🏅 JO標準突破！（標準 ${secondsToStr(joTime)} より ${Math.abs(diff).toFixed(2)}秒速い）`
        : `JO標準（${secondsToStr(joTime)}）まであと ${diff.toFixed(2)}秒`;
    }
    setSavedMsg({ best: isNewBest, pbInfo: prev ? `現在のベスト: ${prev.timeStr}（${prev.date}）` : undefined, joInfo });
    setTimeStr(''); setRefTimeStr(''); setSplitInputs(Array(numSplits).fill(''));
  }

  function updateSplit(idx: number, val: string) {
    setSplitInputs(prev => { const n = [...prev]; n[idx] = val; return n; });
  }

  const poolOpts = ['未入力', ...pools, '新しいプールを追加...'];

  return (
    <div>
      <div className="section-title">📝 新しい記録を入力</div>
      <div className="card">
        <div className="form-group">
          <label>種目</label>
          <select value={event} onChange={e => { setEvent(e.target.value); setDistance(EVENT_DISTANCES[e.target.value][0]); setSavedMsg(null); }}>
            {events.map(ev => <option key={ev} value={ev}>{ev}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label>距離</label>
          <select value={distance} onChange={e => setDistance(Number(e.target.value))}>
            {distances.map(d => <option key={d} value={d}>{d}m</option>)}
          </select>
        </div>
        <div className="form-group">
          <label>プールの種類</label>
          <div className="radio-group">
            {COURSE_OPTIONS.map(c => (
              <label key={c}><input type="radio" checked={course === c} onChange={() => setCourse(c)} />{c}</label>
            ))}
          </div>
        </div>
        <div className="form-group">
          <label>日付</label>
          <input type="date" value={date} onChange={e => setDate(e.target.value)} />
        </div>
      </div>

      {numSplits > 0 && (
        <div className="card">
          <div className="section-title" style={{ marginBottom: '10px' }}>通過タイム（50m刻み）</div>
          <div className="splits-grid">
            {Array.from({ length: numSplits }, (_, i) => (
              <div className="form-group" key={i} style={{ marginBottom: '6px' }}>
                <label style={{ fontSize: '0.78rem' }}>{(i + 1) * 50}m</label>
                <input type="text" value={splitInputs[i] ?? ''} onChange={e => updateSplit(i, e.target.value)} placeholder="例: 27.89" style={{ padding: '6px 8px', fontSize: '0.88rem' }} />
              </div>
            ))}
          </div>
          {!splitsValid && <p className="hint hint-error">通過タイムの形式が正しくありません（例: 27.89 または 1:02.34）</p>}
          {splitsValid && passageSecs.some(s => s !== null) && (
            <table className="data-table" style={{ marginTop: '8px' }}>
              <thead><tr><th>距離</th><th>通過タイム</th><th>ラップタイム</th></tr></thead>
              <tbody>
                {passageSecs.map((p, i) => (
                  <tr key={i}>
                    <td>{(i + 1) * 50}m</td>
                    <td>{p !== null ? secondsToStr(p) : '-'}</td>
                    <td>{lapSecs[i] !== null ? secondsToStr(lapSecs[i]!) : '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      <div className="card">
        <div className="form-group">
          <label>タイム（例: 1:23.45 または 27.89）</label>
          <input type="text" value={timeStr} onChange={e => { setTimeStr(e.target.value); setSavedMsg(null); }} placeholder="例: 1:23.45" />
          {timeStr && (parsedSec !== null
            ? <p className="hint hint-success">✅ {secondsToStr(parsedSec)}</p>
            : <p className="hint hint-error">形式が正しくありません（例: 1:23.45 または 27.89）</p>
          )}
        </div>
        <div className="form-group">
          <label>基準タイム（差分計算用・任意）</label>
          <input type="text" value={refTimeStr} onChange={e => setRefTimeStr(e.target.value)} placeholder="例: 1:20.00" />
          {refTimeStr && refParsed !== null && parsedSec !== null && (
            <p className="hint hint-success">
              差分: {parsedSec - refParsed >= 0 ? '+' : '−'}{Math.abs(parsedSec - refParsed).toFixed(2)}秒（基準 {secondsToStr(refParsed)}）
            </p>
          )}
          {refTimeStr && refParsed === null && <p className="hint hint-error">形式が正しくありません</p>}
        </div>
        <div className="form-group">
          <label>リアクションタイム（秒）</label>
          <input type="number" value={reactionTime} min={0} max={2} step={0.01} onChange={e => setReactionTime(Number(e.target.value))} style={{ width: '140px' }} />
        </div>
        <div className="form-group">
          <label>資格級</label>
          <select value={qualifGrade} onChange={e => setQualifGrade(e.target.value)}>
            {QUALIF_OPTIONS.map(q => <option key={q} value={q}>{q}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label>大会名（任意）</label>
          <input type="text" value={meetName} onChange={e => setMeetName(e.target.value)} placeholder="例: ○○水泳大会" />
        </div>
        <div className="form-group">
          <label>プール名</label>
          <select value={poolSel} onChange={e => setPoolSel(e.target.value)}>
            {poolOpts.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
          {poolSel === '新しいプールを追加...' && (
            <input type="text" value={newPoolInput} onChange={e => setNewPoolInput(e.target.value)} placeholder="例: 東京アクアティクスセンター" style={{ marginTop: '6px' }} />
          )}
        </div>
        <button className="btn btn-primary btn-full" onClick={handleSave} disabled={parsedSec === null}>
          💾 記録を保存
        </button>

        {savedMsg && (
          <div style={{ marginTop: '12px' }}>
            {savedMsg.best
              ? <div className="badge-best">🎉 自己ベスト更新！</div>
              : <div className="badge-info">{savedMsg.pbInfo}</div>
            }
            {savedMsg.joInfo && (
              savedMsg.joInfo.startsWith('🏅')
                ? <div className="badge-jo">{savedMsg.joInfo}</div>
                : <div className="badge-info">{savedMsg.joInfo}</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
