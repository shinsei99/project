import Link from "next/link";
import { Library, HardDrive } from "lucide-react";
import type { LibraryStatus } from "@/lib/types";

export function formatBytes(n: number): string {
  if (!n) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(units.length - 1, Math.floor(Math.log(n) / Math.log(1024)));
  return `${(n / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

/**
 * 蔵書と端末容量の状況。
 * 以前は「無料枠 ○/○冊」のメーター（広告で枠を増やす導線）だったが、
 * 2026-08-17 に広告と冊数制限をやめたので、**実際に使っている容量**を出す形に変えた。
 */
export function StorageMeter({ status }: { status: LibraryStatus | null }) {
  const books = status?.bookCount ?? 0;
  const pages = status?.pageCount ?? 0;
  const used = status?.usageBytes ?? status?.imageBytes ?? 0;
  const quota = status?.quotaBytes ?? null;
  const ratio = quota && quota > 0 ? Math.min(100, (used / quota) * 100) : null;

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-sm">
        <span className="flex items-center gap-2 text-slate-300">
          <Library className="h-4 w-4 text-sky-400" />
          蔵書 <span className="font-bold text-slate-100">{books}</span> 冊 ／{" "}
          <span className="font-bold text-slate-100">{pages}</span> ページ
        </span>
        <span className="flex items-center gap-2 text-slate-400">
          <HardDrive className="h-4 w-4" />
          端末内 {formatBytes(used)}
          {quota ? ` / ${formatBytes(quota)}` : ""}
        </span>
      </div>

      {ratio !== null && (
        <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-700">
          <div
            className={`h-full transition-[width] ${ratio > 85 ? "bg-amber-400" : "bg-sky-400"}`}
            style={{ width: `${Math.max(1, ratio)}%` }}
          />
        </div>
      )}

      <p className="mt-2 text-xs text-slate-500">
        {ratio !== null
          ? "ブラウザが許可している保存領域に対する使用量です。"
          : "この環境では上限を取得できないため、使用量だけを表示しています。"}{" "}
        いっぱいになってきたら{" "}
        <Link href="/library" className="text-sky-400 underline hover:text-sky-300">
          蔵書
        </Link>{" "}
        から不要な本を削除してください。
      </p>
    </div>
  );
}
