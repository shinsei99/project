import React from "react";

export function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** 検索語を空白で分解する（AND検索に合わせて複数語を扱う） */
export function terms(keyword: string): string[] {
  return keyword.trim().split(/\s+/).filter(Boolean);
}

/**
 * text 内の検索語（複数可・大文字小文字無視）を <mark> でハイライトして返す。
 */
export function highlight(text: string, keyword: string): React.ReactNode {
  const ts = terms(keyword);
  if (ts.length === 0) return text;
  const lowered = ts.map((t) => t.toLowerCase());
  const parts = text.split(new RegExp(`(${ts.map(escapeRegExp).join("|")})`, "gi"));
  return parts.map((part, i) =>
    lowered.includes(part.toLowerCase()) ? (
      <mark key={i} className="rounded bg-yellow-300 px-0.5 text-black">
        {part}
      </mark>
    ) : (
      <React.Fragment key={i}>{part}</React.Fragment>
    )
  );
}

/**
 * 検索語の周辺だけを抜き出したプレビュー文字列を返す（前後 radius 文字）。
 * 複数語のときは**最初に見つかった語**の周辺を出す。
 */
export function snippet(text: string, keyword: string, radius = 60): string {
  if (!text) return "";
  const lower = text.toLowerCase();
  let idx = -1;
  let hitLen = 0;
  for (const t of terms(keyword)) {
    const i = lower.indexOf(t.toLowerCase());
    if (i !== -1 && (idx === -1 || i < idx)) {
      idx = i;
      hitLen = t.length;
    }
  }
  if (idx === -1) {
    return text.slice(0, radius * 2) + (text.length > radius * 2 ? "…" : "");
  }
  const start = Math.max(0, idx - radius);
  const end = Math.min(text.length, idx + hitLen + radius);
  return (
    (start > 0 ? "…" : "") + text.slice(start, end).trim() + (end < text.length ? "…" : "")
  );
}
