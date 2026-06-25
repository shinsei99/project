export function parseTimeInput(s: string): number | null {
  const t = s.trim();
  if (!t) return null;
  try {
    if (t.includes(':')) {
      const [mStr, secStr] = t.split(':', 2);
      const m = parseInt(mStr, 10);
      const sec = parseFloat(secStr);
      if (isNaN(m) || isNaN(sec) || sec >= 60 || sec < 0 || m < 0) return null;
      return Math.round((m * 60 + sec) * 100) / 100;
    }
    const val = parseFloat(t);
    if (isNaN(val) || val <= 0) return null;
    return Math.round(val * 100) / 100;
  } catch {
    return null;
  }
}

export function secondsToStr(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const rem = Math.round((totalSeconds - minutes * 60) * 100) / 100;
  let seconds = Math.floor(rem);
  let centiseconds = Math.round((rem - seconds) * 100);
  if (centiseconds >= 100) { centiseconds -= 100; seconds += 1; }
  if (seconds >= 60) { seconds -= 60; }
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}.${String(centiseconds).padStart(2, '0')}`;
}
