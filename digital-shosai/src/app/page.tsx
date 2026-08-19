"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { CheckCircle2, AlertCircle, ShieldCheck, Loader2, Search, Library, BookOpen } from "lucide-react";
import { StorageMeter } from "@/components/StorageMeter";
import { UploadArea } from "@/components/UploadArea";
import { extractIndex, renderCover, sourceOf, titleFromFileName } from "@/lib/pdfClient";
import { findBookBySource, getStatus, saveIndex, setCover } from "@/lib/db";
import { remember } from "@/lib/session";
import { MIN_CHARS_PER_PAGE } from "@/lib/constants";
import { BUNDLED_DONE_KEY, bundledAsFile, bundledFileName, listBundled } from "@/lib/bundled";
import type { LibraryStatus } from "@/lib/types";

type Row = {
  name: string;
  state: "待機" | "読み込み中" | "済" | "重複" | "文字なし" | "失敗";
  detail?: string;
  progress?: { done: number; total: number };
};

export default function HomePage() {
  const [status, setStatus] = useState<LibraryStatus | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [running, setRunning] = useState(false);
  const [seeding, setSeeding] = useState(false);
  /** そのファイルが同梱の収録作品なら、その中のファイル名（本に印を付けるため） */
  const bundledOf = useRef<Map<string, string>>(new Map());

  const refresh = useCallback(async () => {
    try {
      setStatus(await getStatus());
    } catch {
      /* 表示だけなので落とさない */
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  /**
   * 複数の本を順に索引化する。**画像は作らない**（見たときに作る）。
   * 1冊ずつ確定させるので、途中でやめても入った本は残る。
   */
  const run = useCallback(
    async (files: File[]) => {
      setRunning(true);
      setRows(files.map((f) => ({ name: f.name, state: "待機" })));
      const patch = (i: number, r: Partial<Row>) =>
        setRows((prev) => prev.map((row, j) => (j === i ? { ...row, ...r } : row)));

      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        patch(i, { state: "読み込み中" });
        try {
          const source = sourceOf(file);
          const dup = await findBookBySource(source);
          if (dup) {
            patch(i, { state: "重複", detail: `すでに入っています（${dup.title}）` });
            remember(dup.id, file); // 原本の参照だけ更新しておく
            continue;
          }
          const { pages, quality, rebuiltRatio } = await extractIndex(file, (done, total) =>
            patch(i, { progress: { done, total } })
          );
          const chars = pages.reduce((n, p) => n + p.text.replace(/\s/g, "").length, 0);
          if (chars < pages.length * MIN_CHARS_PER_PAGE) {
            patch(i, {
              state: "文字なし",
              detail: `${pages.length}ページ・文字がほとんど無い（未OCRのPDF）。索引に入れませんでした`,
            });
            continue;
          }
          const book = await saveIndex(titleFromFileName(file.name), pages, source, {
            quality,
            rebuiltRatio,
            bundled: bundledOf.current.get(file.name),
          });
          remember(book.id, file);
          // **表紙だけはここで作る**（本棚に並べるため。1冊30〜60KB程度）
          const cover = await renderCover(file);
          if (cover) await setCover(book.id, cover.blob, cover);
          const pct = Math.round(quality * 100);
          patch(i, {
            state: "済",
            detail:
              `${book.pageCount}ページ・${(book.textChars / 10000).toFixed(1)}万字` +
              `／読みやすさ ${pct}%` +
              (rebuiltRatio > 0 ? `（${Math.round(rebuiltRatio * 100)}%のページを組み直した）` : ""),
          });
          await refresh();
        } catch (e: any) {
          patch(i, { state: "失敗", detail: e?.message ?? "読み込めませんでした" });
        }
      }
      setRunning(false);
      await refresh();
    },
    [refresh]
  );

  /**
   * 初回だけ、同梱の収録作品（青空文庫・著作権保護期間満了）を書斎に入れる。
   * **蔵書数では判定しない**（自分で消した本が起動のたびに戻ってくるのを防ぐため、
   * 済んだ印を localStorage に置く）。
   */
  const seed = useCallback(async () => {
    const books = await listBundled();
    if (books.length === 0) return;
    setSeeding(true);
    try {
      const files: File[] = [];
      for (const b of books) {
        try {
          files.push(await bundledAsFile(b));
          bundledOf.current.set(bundledFileName(b), b.file);
        } catch {
          /* 1冊開けなくても残りは入れる */
        }
      }
      if (files.length) await run(files);
    } finally {
      setSeeding(false);
    }
  }, [run]);

  useEffect(() => {
    let done = false;
    try { done = localStorage.getItem(BUNDLED_DONE_KEY) === "1"; } catch { /* noop */ }
    if (done) return;
    try { localStorage.setItem(BUNDLED_DONE_KEY, "1"); } catch { /* noop */ }
    (async () => {
      const st = await getStatus().catch(() => null);
      if (st && st.bookCount > 0) return; // 既に本がある書斎には入れない
      await seed();
    })();
  }, [seed]);

  const done = rows.filter((r) => r.state === "済").length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">本を取り込む</h1>
        <p className="mt-1 text-sm text-slate-400">
          PDFを選ぶと<strong className="text-slate-300">本文だけ</strong>を取り込んで検索できるようにします。
          ページの画像は<strong className="text-slate-300">開いたときにその場で作る</strong>ので、取り込みは軽く、容量も使った分だけです。
        </p>
        <p className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-emerald-900/30 px-3 py-1 text-xs text-emerald-300">
          <ShieldCheck className="h-3.5 w-3.5" />
          原本は元の場所（Dropbox等）に置いたまま。データは端末内だけに保存されます
        </p>
      </div>

      <StorageMeter status={status} />

      <UploadArea
        disabled={running}
        multiple
        onFiles={run}
        onReject={(text) => setRows([{ name: "選択したファイル", state: "失敗", detail: text }])}
      />

      {/* 収録作品（同梱）。初回は自動で入る。消した後で入れ直したい人のためにボタンも出す */}
      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
        <BookOpen className="h-3.5 w-3.5" />
        {seeding ? (
          <span className="text-sky-300">収録作品（青空文庫）を書斎に入れています…</span>
        ) : (
          <>
            <span>手持ちのPDFが無くても、収録作品（青空文庫・著作権保護期間が満了した作品）で試せます。</span>
            <button
              onClick={seed}
              disabled={running}
              className="rounded-lg border border-slate-700 px-2 py-1 text-slate-300 hover:bg-slate-800 disabled:opacity-40"
            >
              収録作品を入れる
            </button>
          </>
        )}
      </div>

      {rows.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900">
          <div className="flex items-center justify-between border-b border-slate-800 px-4 py-2.5 text-sm">
            <span className="font-semibold">
              取り込み {done} / {rows.length} 冊
            </span>
            {running && <Loader2 className="h-4 w-4 animate-spin text-sky-400" />}
          </div>
          <ul className="divide-y divide-slate-800">
            {rows.map((r, i) => (
              <li key={i} className="px-4 py-2.5 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={[
                      "rounded-full px-2 py-0.5 text-xs font-semibold",
                      r.state === "済"
                        ? "bg-emerald-900/40 text-emerald-300"
                        : r.state === "失敗" || r.state === "文字なし"
                          ? "bg-rose-900/40 text-rose-300"
                          : r.state === "重複"
                            ? "bg-slate-800 text-slate-400"
                            : "bg-sky-900/40 text-sky-300",
                    ].join(" ")}
                  >
                    {r.state}
                  </span>
                  <span className="min-w-0 flex-1 truncate">{r.name}</span>
                  {r.progress && r.progress.total > 0 && (
                    <span className="text-xs text-slate-400">
                      {r.progress.done} / {r.progress.total} ページ
                    </span>
                  )}
                </div>
                {r.detail && <p className="mt-1 text-xs text-slate-400">{r.detail}</p>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {status && status.bookCount > 0 && (
        <p className="flex flex-wrap gap-4 text-sm">
          <Link href="/search" className="inline-flex items-center gap-1 text-sky-400 underline hover:text-sky-300">
            <Search className="h-4 w-4" /> 検索して読む
          </Link>
          <Link href="/library" className="inline-flex items-center gap-1 text-sky-400 underline hover:text-sky-300">
            <Library className="h-4 w-4" /> 蔵書を管理する
          </Link>
        </p>
      )}

      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 text-xs text-slate-400">
        <p className="mb-1 font-semibold text-slate-300">取り込みで分かること</p>
        <ul className="list-disc space-y-1 pl-4">
          <li>
            <strong className="text-slate-300">読みやすさ</strong>
            … 本文のひらがな率から出した目安。低い本はOCRが崩れているか図表が多く、
            テキストだけでは読みにくい（そのときはページ画像で読む）
          </li>
          <li>
            <strong className="text-slate-300">組み直した割合</strong>
            … 縦書きのページは1文字ずつ拾われることがあるため、座標から列を復元した割合
          </li>
          <li>文字が入っていないPDF（未OCR）は索引に入れません。先にOCRしてください</li>
        </ul>
      </div>
    </div>
  );
}
