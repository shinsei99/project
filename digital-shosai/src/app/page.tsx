"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { CheckCircle2, AlertCircle, ShieldCheck, Loader2, Search } from "lucide-react";
import { StorageMeter, formatBytes } from "@/components/StorageMeter";
import { UploadArea } from "@/components/UploadArea";
import { processPdf, titleFromFileName, imageFormatInUse } from "@/lib/pdfClient";
import { getStatus, saveBook } from "@/lib/db";
import type { LibraryStatus } from "@/lib/types";

type Notice = { type: "success" | "error"; text: string } | null;

export default function HomePage() {
  const [status, setStatus] = useState<LibraryStatus | null>(null);
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [notice, setNotice] = useState<Notice>(null);
  // 文字層の無いPDFを検知したときの確認。**window.confirm は使わない**
  // （ブラウザのダイアログは操作を全部止めてしまうし、唐突なので）
  const [askImageOnly, setAskImageOnly] = useState<{ file: File; chars: number } | null>(null);

  const refreshStatus = useCallback(async () => {
    try {
      setStatus(await getStatus());
    } catch {
      /* 表示だけなので落とさない */
    }
  }, []);

  useEffect(() => {
    refreshStatus();
  }, [refreshStatus]);

  // 端末内での取り込み処理（pdf.js → IndexedDB）
  const runImport = useCallback(
    async (file: File, opts: { allowImageOnly?: boolean } = {}) => {
      setNotice(null);
      setAskImageOnly(null);
      setProcessing(true);
      setProgress({ done: 0, total: 0 });

      try {
        const pages = await processPdf(file, (done, total) => setProgress({ done, total }));

        // 文字層チェック：スキャンしただけ（OCR未処理）のPDFを検知して確認する
        const totalChars = pages.reduce(
          (sum, p) => sum + (p.content ? p.content.replace(/\s/g, "").length : 0),
          0
        );
        const looksUnsearchable = totalChars < pages.length * 3;
        if (looksUnsearchable && !opts.allowImageOnly) {
          setAskImageOnly({ file, chars: totalChars });
          return; // 画面内の確認パネルで選んでもらう
        }

        const book = await saveBook(titleFromFileName(file.name), pages);
        const fmt = imageFormatInUse()?.replace("image/", "").toUpperCase() ?? "?";
        setNotice({
          type: looksUnsearchable ? "error" : "success",
          text: looksUnsearchable
            ? `「${book.title}」を画像として保存しました（${book.pageCount}ページ・検索不可）`
            : `「${book.title}」を端末内に保存しました（${book.pageCount}ページ・` +
              `${formatBytes(book.imageBytes ?? 0)}・画像は ${fmt}）`,
        });
        await refreshStatus();
      } catch (e: any) {
        setNotice({ type: "error", text: e?.message ?? "取り込みに失敗しました" });
      } finally {
        setProcessing(false);
        setProgress(null);
      }
    },
    [refreshStatus]
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">PDFを取り込む</h1>
        <p className="mt-1 text-sm text-slate-400">
          OCR済みPDFを選ぶと、ページごとにテキスト抽出＆画像化して保存します。
        </p>
        <p className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-emerald-900/30 px-3 py-1 text-xs text-emerald-300">
          <ShieldCheck className="h-3.5 w-3.5" />
          データはこの端末内だけに保存され、外部に送信されません
        </p>
      </div>

      <StorageMeter status={status} />

      <UploadArea
        disabled={processing}
        onFile={(f) => runImport(f)}
        onReject={(text) => setNotice({ type: "error", text })}
      />

      {/* 取り込み中の進捗（以前はここに全画面広告を出していた） */}
      {processing && (
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
          <div className="mb-2 flex items-center gap-2 text-sm text-slate-300">
            <Loader2 className="h-4 w-4 animate-spin text-sky-400" />
            取り込み中
            {progress && progress.total > 0
              ? ` — ${progress.done} / ${progress.total} ページ`
              : " — PDFを読み込んでいます"}
          </div>
          <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-700">
            <div
              className="h-full bg-sky-400 transition-[width]"
              style={{
                width:
                  progress && progress.total > 0
                    ? `${Math.max(2, (progress.done / progress.total) * 100)}%`
                    : "6%",
              }}
            />
          </div>
          <p className="mt-2 text-xs text-slate-500">
            テキスト抽出とページ画像化を端末内で行っています。ページ数が多いと時間がかかります。
          </p>
        </div>
      )}

      {/* 文字層が無いPDFの確認（画面内で完結させる） */}
      {askImageOnly && (
        <div className="rounded-xl border border-amber-700 bg-amber-900/20 p-4">
          <p className="flex items-center gap-2 font-semibold text-amber-300">
            <AlertCircle className="h-4 w-4" />
            このPDFには文字データがほとんど見つかりませんでした
          </p>
          <p className="mt-2 text-sm text-amber-200/90">
            スキャンしただけ（OCR未処理）の画像PDFのようです（検出できた文字数:{" "}
            {askImageOnly.chars}）。このまま取り込んでも
            <strong>検索はできません</strong>。画像として保存だけしますか？
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              onClick={() => runImport(askImageOnly.file, { allowImageOnly: true })}
              className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-500"
            >
              画像として保存する
            </button>
            <button
              onClick={() => {
                setAskImageOnly(null);
                setNotice({
                  type: "error",
                  text: "取り込みを中止しました。Acrobat / ScanSnap / Googleドライブ等でOCRしてから取り込んでください。",
                });
              }}
              className="rounded-lg border border-slate-600 px-4 py-2 text-sm text-slate-200 hover:bg-slate-800"
            >
              やめる（先にOCRする）
            </button>
          </div>
        </div>
      )}

      {notice && (
        <div
          className={[
            "flex items-start gap-2 rounded-xl border px-4 py-3 text-sm",
            notice.type === "success"
              ? "border-emerald-700 bg-emerald-900/30 text-emerald-300"
              : "border-rose-700 bg-rose-900/30 text-rose-300",
          ].join(" ")}
        >
          {notice.type === "success" ? (
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
          ) : (
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          )}
          <span>{notice.text}</span>
        </div>
      )}

      {status && status.bookCount > 0 && (
        <p className="text-sm text-slate-400">
          <Link
            href="/search"
            className="inline-flex items-center gap-1 text-sky-400 underline hover:text-sky-300"
          >
            <Search className="h-4 w-4" /> 検索して読む
          </Link>
          {" ／ "}
          <Link href="/library" className="text-sky-400 underline hover:text-sky-300">
            蔵書を管理する
          </Link>
        </p>
      )}
    </div>
  );
}
