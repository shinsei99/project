"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { CheckCircle2, AlertCircle, ShieldCheck, Loader2, Search, Library } from "lucide-react";
import { StorageMeter } from "@/components/StorageMeter";
import { UploadArea } from "@/components/UploadArea";
import { extractIndex, renderCover, sourceOf, titleFromFileName } from "@/lib/pdfClient";
import { findBookBySource, getStatus, saveIndex, setCover } from "@/lib/db";
import { remember } from "@/lib/session";
import { MIN_CHARS_PER_PAGE } from "@/lib/constants";
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
