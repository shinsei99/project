"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { BookOpen, Trash2, Search, Loader2, Upload } from "lucide-react";
import { StorageMeter, formatBytes } from "@/components/StorageMeter";
import { deleteBook, getStatus, listBooks, type BookRecord } from "@/lib/db";
import type { LibraryStatus } from "@/lib/types";

/**
 * 蔵書の一覧と削除。
 * 端末内の容量は有限なのに消す手段が無かったため 2026-08-17 に追加した
 * （`listBooks()` / `deleteBook()` は以前から `db.ts` にあり、画面だけが無かった）。
 */
export default function LibraryPage() {
  const [books, setBooks] = useState<BookRecord[] | null>(null);
  const [status, setStatus] = useState<LibraryStatus | null>(null);
  // 削除の確認は**画面内**で行う（window.confirm は使わない）
  const [confirming, setConfirming] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [list, st] = await Promise.all([listBooks(), getStatus()]);
    setBooks(list);
    setStatus(st);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const remove = useCallback(
    async (id: string) => {
      setBusy(id);
      try {
        await deleteBook(id);
        await refresh();
      } finally {
        setBusy(null);
        setConfirming(null);
      }
    },
    [refresh]
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">蔵書</h1>
        <p className="mt-1 text-sm text-slate-400">
          取り込んだ本の一覧です。使わない本を削除すると端末の容量が空きます。
        </p>
      </div>

      <StorageMeter status={status} />

      {books === null ? (
        <div className="flex justify-center py-10 text-slate-500">
          <Loader2 className="h-6 w-6 animate-spin" />
        </div>
      ) : books.length === 0 ? (
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-8 text-center">
          <p className="text-slate-300">まだ1冊も入っていません。</p>
          <Link
            href="/"
            className="mt-3 inline-flex items-center gap-1 text-sm text-sky-400 underline hover:text-sky-300"
          >
            <Upload className="h-4 w-4" /> PDFを取り込む
          </Link>
        </div>
      ) : (
        <ul className="space-y-3">
          {books.map((b) => (
            <li
              key={b.id}
              className="rounded-xl border border-slate-800 bg-slate-900 p-4 transition hover:border-slate-700"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="flex items-center gap-2 font-semibold">
                    <BookOpen className="h-4 w-4 shrink-0 text-sky-400" />
                    <span className="truncate">{b.title}</span>
                  </p>
                  <p className="mt-1 text-xs text-slate-400">
                    {b.pageCount} ページ ／ {formatBytes(b.imageBytes ?? 0)}
                    {b.imageMime ? `（${b.imageMime.replace("image/", "").toUpperCase()}）` : ""} ／
                    取り込み {new Date(b.uploadedAt).toLocaleString("ja-JP")}
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <Link
                    href={`/search?book=${encodeURIComponent(b.id)}`}
                    className="inline-flex items-center gap-1 rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-800"
                  >
                    <Search className="h-4 w-4" /> この本を検索
                  </Link>
                  {confirming === b.id ? (
                    <>
                      <button
                        onClick={() => remove(b.id)}
                        disabled={busy === b.id}
                        aria-label={`「${b.title}」を削除する（確定）`}
                        className="inline-flex items-center gap-1 rounded-lg bg-rose-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-rose-500 disabled:opacity-60"
                      >
                        {busy === b.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4" />
                        )}
                        本当に削除
                      </button>
                      <button
                        onClick={() => setConfirming(null)}
                        className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
                      >
                        やめる
                      </button>
                    </>
                  ) : (
                    <button
                      onClick={() => setConfirming(b.id)}
                      aria-label={`「${b.title}」を削除`}
                      className="inline-flex items-center gap-1 rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-rose-300 hover:bg-rose-900/30"
                    >
                      <Trash2 className="h-4 w-4" /> 削除
                    </button>
                  )}
                </div>
              </div>
              {confirming === b.id && (
                <p className="mt-3 text-xs text-rose-300">
                  「{b.title}」のページ・画像をすべて削除します。
                  <strong>元に戻せません</strong>（削除されるのは端末内のデータだけです）。
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
