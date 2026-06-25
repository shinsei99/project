import { useState } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import * as XLSX from 'xlsx';
import type { User, SwimRecord } from '../types';
import { saveRecord, deleteRecord, updateRecord } from '../db';
import { EVENT_DISTANCES, COURSE_OPTIONS, QUALIF_OPTIONS } from '../joStandards';
import { parseTimeInput, secondsToStr } from '../utils/time';

interface Props {
  user: User;
  records: SwimRecord[];
  onRecordsChange: () => void;
}

export default function TabHistory({ user, records, onRecordsChange }: Props) {
  const events = Object.keys(EVENT_DISTANCES);
  const [fEvent, setFEvent] = useState('すべて');
  const [fDistance, setFDistance] = useState('すべて');
  const [fCourse, setFCourse] = useState('すべて');
  const [editId, setEditId] = useState<string | null>(null);
  const [editOpen, setEditOpen] = useState(false);

  // edit state
  const [eDate, setEDate] = useState('');
  const [eEvent, setEEvent] = useState(events[0]);
  const [eDistance, setEDistance] = useState(50);
  const [eCourse, setECourse] = useState(COURSE_OPTIONS[0]);
  const [eTimeStr, setETimeStr] = useState('');
  const [eRt, setERt] = useState(0.65);
  const [eQualif, setEQualif] = useState('なし');
  const [eMeet, setEMeet] = useState('');
  const [ePool, setEPool] = useState('');

  const allDistances = Array.from(new Set(records.map(r => r.distance))).sort((a, b) => a - b);
  const distOpts = fEvent !== 'すべて' ? EVENT_DISTANCES[fEvent] : allDistances;

  let filtered = records.filter(r => {
    if (fEvent !== 'すべて' && r.event !== fEvent) return false;
    if (fDistance !== 'すべて' && r.distance !== Number(fDistance)) return false;
    if (fCourse !== 'すべて' && r.course !== fCourse) return false;
    return true;
  }).sort((a, b) => a.date.localeCompare(b.date));

  const combos = new Set(filtered.map(r => `${r.event}|${r.distance}|${r.course}`));
  const singleCombo = combos.size === 1;

  const chartData = singleCombo ? filtered.map(r => ({
    date: r.date,
    sec: r.timeSec,
    label: r.timeStr,
  })) : [];

  function openEdit(rec: SwimRecord) {
    setEditId(rec.id);
    setEDate(rec.date);
    setEEvent(rec.event);
    setEDistance(rec.distance);
    setECourse(rec.course);
    setETimeStr(rec.timeStr);
    setERt(rec.reactionTime);
    setEQualif(rec.qualifGrade);
    setEMeet(rec.meetName);
    setEPool(rec.poolName);
    setEditOpen(true);
  }

  async function handleDelete(id: string) {
    if (!confirm('この記録を削除しますか？')) return;
    await deleteRecord(id);
    setEditId(null); setEditOpen(false);
    onRecordsChange();
  }

  async function handleUpdate() {
    if (!editId) return;
    const parsed = parseTimeInput(eTimeStr);
    if (parsed === null) { alert('タイムの形式が正しくありません'); return; }
    const orig = records.find(r => r.id === editId);
    if (!orig) return;
    await updateRecord({ ...orig, date: eDate, event: eEvent, distance: eDistance, course: eCourse, timeSec: parsed, timeStr: secondsToStr(parsed), reactionTime: eRt, qualifGrade: eQualif, meetName: eMeet, poolName: ePool });
    onRecordsChange();
    setEditOpen(false);
  }

  function exportCSV() {
    const cols = ['日付', '種目', '距離', 'コース', 'タイム表示', 'タイム秒', 'リアクションタイム', '資格級', '大会名', 'プール名', '通過タイム', 'ラップタイム'];
    const rows = records.map(r => [r.date, r.event, r.distance, r.course, r.timeStr, r.timeSec, r.reactionTime, r.qualifGrade, r.meetName, r.poolName, r.splitTimes, r.lapTimes]);
    const csv = [cols, ...rows].map(row => row.map(v => `"${String(v ?? '').replace(/"/g, '""')}"`).join(',')).join('\n');
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    a.download = `${user.name}_swim_records.csv`; a.click();
  }

  function exportXLSX() {
    const cols = ['日付', '種目', '距離', 'コース', 'タイム表示', 'タイム秒', 'リアクションタイム', '資格級', '大会名', 'プール名', '通過タイム', 'ラップタイム'];
    const rows = records.map(r => [r.date, r.event, r.distance, r.course, r.timeStr, r.timeSec, r.reactionTime, r.qualifGrade, r.meetName, r.poolName, r.splitTimes, r.lapTimes]);
    const ws = XLSX.utils.aoa_to_sheet([cols, ...rows]);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, '記録');
    XLSX.writeFile(wb, `${user.name}_swim_records.xlsx`);
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; if (!file) return;
    try {
      const buf = await file.arrayBuffer();
      const wb = XLSX.read(buf);
      const ws = wb.Sheets[wb.SheetNames[0]];
      const rows = XLSX.utils.sheet_to_json<Record<string, unknown>>(ws);
      let added = 0;
      for (const row of rows) {
        const timeSec = Number(row['タイム秒']);
        if (!timeSec) continue;
        const exists = records.some(r => r.date === String(row['日付']) && r.event === String(row['種目']) && r.distance === Number(row['距離']) && r.course === String(row['コース']) && r.timeSec === timeSec);
        if (exists) continue;
        await saveRecord({
          id: crypto.randomUUID(), userId: user.id,
          date: String(row['日付'] ?? ''), event: String(row['種目'] ?? ''), distance: Number(row['距離'] ?? 0),
          course: String(row['コース'] ?? ''), timeSec, timeStr: String(row['タイム表示'] ?? secondsToStr(timeSec)),
          reactionTime: Number(row['リアクションタイム'] ?? 0.65), qualifGrade: String(row['資格級'] ?? 'なし'),
          meetName: String(row['大会名'] ?? ''), poolName: String(row['プール名'] ?? ''),
          splitTimes: String(row['通過タイム'] ?? ''), lapTimes: String(row['ラップタイム'] ?? ''),
          createdAt: new Date().toISOString(),
        });
        added++;
      }
      onRecordsChange();
      alert(`${added} 件の新規記録をインポートしました`);
    } catch {
      alert('ファイルの読み込みに失敗しました');
    }
    e.target.value = '';
  }

  const customTooltip = ({ active, payload }: { active?: boolean; payload?: { payload: { label: string; date: string } }[] }) => {
    if (active && payload?.length) {
      return <div className="card" style={{ padding: '8px 12px', fontSize: '0.85rem' }}>{payload[0].payload.date}<br />{payload[0].payload.label}</div>;
    }
    return null;
  };

  return (
    <div>
      <div className="section-title">📊 {user.name}さんの記録履歴</div>

      {records.length === 0 ? (
        <div className="empty-state"><div className="empty-icon">🏊</div><p>まだ記録がありません</p></div>
      ) : (
        <>
          <div className="card">
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginBottom: '12px' }}>
              <label className="select-label">種目
                <select value={fEvent} onChange={e => { setFEvent(e.target.value); setFDistance('すべて'); }}>
                  <option value="すべて">すべて</option>
                  {events.map(ev => <option key={ev} value={ev}>{ev}</option>)}
                </select>
              </label>
              <label className="select-label">距離
                <select value={fDistance} onChange={e => setFDistance(e.target.value)}>
                  <option value="すべて">すべて</option>
                  {distOpts.map(d => <option key={d} value={d}>{d}m</option>)}
                </select>
              </label>
              <label className="select-label">コース
                <select value={fCourse} onChange={e => setFCourse(e.target.value)}>
                  <option value="すべて">すべて</option>
                  {COURSE_OPTIONS.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </label>
            </div>

            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr><th>日付</th><th>種目</th><th>距離</th><th>コース</th><th>タイム</th><th>RT</th><th>資格級</th><th>大会名</th><th>プール名</th><th></th></tr>
                </thead>
                <tbody>
                  {filtered.map(r => (
                    <tr key={r.id}>
                      <td>{r.date}</td><td>{r.event}</td><td>{r.distance}m</td><td>{r.course}</td>
                      <td><strong>{r.timeStr}</strong></td><td>{r.reactionTime}</td><td>{r.qualifGrade}</td>
                      <td>{r.meetName}</td><td>{r.poolName}</td>
                      <td>
                        <button className="btn btn-secondary btn-sm" onClick={() => openEdit(r)}>編集</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {singleCombo && chartData.length > 1 && (
              <div className="chart-wrap">
                <p className="hint" style={{ marginBottom: '6px' }}>タイム推移（数値が小さいほど速い）</p>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={chartData}>
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                    <YAxis reversed tick={{ fontSize: 11 }} tickFormatter={v => secondsToStr(v)} width={60} />
                    <Tooltip content={customTooltip as (props: unknown) => React.ReactElement | null} />
                    <Line type="monotone" dataKey="sec" stroke="#3b82f6" dot={{ r: 4 }} strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          {editId && (
            <div className="expander">
              <button className="expander-header" onClick={() => setEditOpen(v => !v)}>
                ✏️ 記録を編集・削除 <span>{editOpen ? '▲' : '▼'}</span>
              </button>
              {editOpen && (
                <div className="expander-body">
                  <div className="form-group"><label>日付</label><input type="date" value={eDate} onChange={e => setEDate(e.target.value)} /></div>
                  <div className="form-group">
                    <label>種目</label>
                    <select value={eEvent} onChange={e => { setEEvent(e.target.value); setEDistance(EVENT_DISTANCES[e.target.value][0]); }}>
                      {events.map(ev => <option key={ev} value={ev}>{ev}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label>距離</label>
                    <select value={eDistance} onChange={e => setEDistance(Number(e.target.value))}>
                      {EVENT_DISTANCES[eEvent].map(d => <option key={d} value={d}>{d}m</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label>コース</label>
                    <div className="radio-group">{COURSE_OPTIONS.map(c => <label key={c}><input type="radio" checked={eCourse === c} onChange={() => setECourse(c)} />{c}</label>)}</div>
                  </div>
                  <div className="form-group">
                    <label>タイム</label>
                    <input type="text" value={eTimeStr} onChange={e => setETimeStr(e.target.value)} />
                    {eTimeStr && parseTimeInput(eTimeStr) === null && <p className="hint hint-error">形式が正しくありません</p>}
                  </div>
                  <div className="form-group"><label>リアクションタイム</label><input type="number" value={eRt} min={0} max={2} step={0.01} onChange={e => setERt(Number(e.target.value))} style={{ width: '130px' }} /></div>
                  <div className="form-group"><label>資格級</label><select value={eQualif} onChange={e => setEQualif(e.target.value)}>{QUALIF_OPTIONS.map(q => <option key={q} value={q}>{q}</option>)}</select></div>
                  <div className="form-group"><label>大会名</label><input type="text" value={eMeet} onChange={e => setEMeet(e.target.value)} /></div>
                  <div className="form-group"><label>プール名</label><input type="text" value={ePool} onChange={e => setEPool(e.target.value)} /></div>
                  <div className="btn-row">
                    <button className="btn btn-primary" onClick={handleUpdate}>💾 変更を保存</button>
                    <button className="btn btn-danger" onClick={() => handleDelete(editId)}>🗑️ 削除</button>
                    <button className="btn btn-secondary" onClick={() => setEditOpen(false)}>キャンセル</button>
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}

      <div className="divider" />
      <div className="section-title">データ管理</div>
      <div className="btn-row">
        <button className="btn btn-secondary" onClick={exportCSV}>📥 CSVで保存</button>
        <button className="btn btn-secondary" onClick={exportXLSX}>📥 Excelで保存</button>
      </div>
      <div className="form-group">
        <label>CSVまたはExcelから読み込む</label>
        <input type="file" accept=".csv,.xlsx" onChange={handleImport} />
      </div>
    </div>
  );
}
