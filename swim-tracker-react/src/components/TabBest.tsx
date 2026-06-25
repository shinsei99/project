import type { User, SwimRecord } from '../types';
import { getJoTime } from '../joStandards';
import { secondsToStr } from '../utils/time';

interface Props {
  user: User;
  records: SwimRecord[];
  joCategory: string;
}

export default function TabBest({ user, records, joCategory }: Props) {
  if (records.length === 0) {
    return <div className="empty-state"><div className="empty-icon">🏆</div><p>まだ記録がありません</p></div>;
  }

  const combos = Array.from(
    new Map(records.map(r => [`${r.event}|${r.distance}|${r.course}`, { event: r.event, distance: r.distance, course: r.course }])).values()
  );

  const rows = combos.map(({ event, distance, course }) => {
    const subset = records.filter(r => r.event === event && r.distance === distance && r.course === course);
    const best = subset.reduce((a, b) => a.timeSec < b.timeSec ? a : b);
    const joTime = getJoTime(joCategory, user.gender, event, distance, course);
    const today = new Date().toISOString().slice(0, 10);
    const daysSince = Math.floor((Date.parse(today) - Date.parse(best.date)) / 86400000);
    let joStatus = '標準データなし';
    let joBase = '-';
    if (joTime !== null) {
      joBase = secondsToStr(joTime);
      const diff = best.timeSec - joTime;
      joStatus = diff <= 0 ? `突破（${Math.abs(diff).toFixed(2)}秒速い）` : `あと${diff.toFixed(2)}秒`;
    }
    return { event, distance: `${distance}m`, course, best: best.timeStr, date: best.date, daysSince, joBase, joStatus };
  });

  return (
    <div>
      <div className="section-title">🏆 ベストタイム一覧 &amp; JO標準比較</div>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr><th>種目</th><th>距離</th><th>コース</th><th>ベストタイム</th><th>記録日</th><th>経過日数</th><th>JO標準</th><th>JO判定</th></tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td>{r.event}</td><td>{r.distance}</td><td>{r.course}</td>
                <td><strong>{r.best}</strong></td><td>{r.date}</td><td>{r.daysSince}日</td>
                <td>{r.joBase}</td>
                <td style={{ color: r.joStatus.startsWith('突破') ? '#16a34a' : r.joStatus === '標準データなし' ? '#94a3b8' : '#0f172a' }}>
                  {r.joStatus.startsWith('突破') ? `✅ ${r.joStatus}` : r.joStatus}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="hint" style={{ marginTop: '10px' }}>※ JO標準は第49回全国JOCジュニアオリンピックカップ夏季の参加標準記録。JO区分: {joCategory}・{user.gender}</p>
    </div>
  );
}
