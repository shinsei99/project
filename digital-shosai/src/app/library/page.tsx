"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { BookOpen, Trash2, Loader2, Upload, ImageOff, Eraser, Download, FileUp, ScanText } from "lucide-react";
import { StorageMeter, formatBytes } from "@/components/StorageMeter";
import {
  clearImageCache,
  deleteBook,
  exportPayload,
  getBookPages,
  getCoverUrl,
  getStatus,
  importPayload,
  listBooks,
  replaceIndex,
  type BookRecord,
} from "@/lib/db";
import type { LibraryStatus } from "@/lib/types";
import { READABLE_QUALITY, REBUILT_HEAVY } from "@/lib/constants";
import { available as ocrAvailable, reocrBook } from "@/lib/nativeOcr";
import { forgetDoc, qualityOf } from "@/lib/pdfClient";
import { bundledUrl } from "@/lib/bundled";

/**
 * 本棚。**表紙を並べて、開くと本文（テキスト）を読む**。
 * 表紙は取り込み時に作った1枚だけ（1冊30〜60KB）。本文ページの画像は読んだときに作る。
 */
export default function LibraryPage() {
  const [books, setBooks] = useState<BookRecord[] | null>(null);
  const [covers, setCovers] = useState<Record<string, string | null>>({});
  const [status, setStatus] = useState<LibraryStatus | null>(null);
  const [menu, setMenu] = useState<string | null>(null);      // 管理メニューを開いている本
  const [confirming, setConfirming] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  // 端末内OCRが使えるか（iOS 26以降のアプリ版だけ true）。使えないならボタンごと出さない
  const [ocrOk, setOcrOk] = useState(false);
  const [reocr, setReocr] = useState<{ bookId: string; done: number; total: number } | null>(null);
  // 原本PDFを選び直してもらうための入力（本文だけ持っていて原本は保存していないため）
  const pickPdf = useRef<HTMLInputElement>(null);
  const pickFor = useRef<BookRecord | null>(null);

  const refresh = useCallback(async () => {
    const [list, st] = await Promise.all([listBooks(), getStatus()]);
    setBooks(list);
    setStatus(st);
    const urls: Record<string, string | null> = {};
    for (const b of list) urls[b.id] = await getCoverUrl(b.id);
    setCovers(urls);
  }, []);

  useEffect(() => {
    refresh();
    ocrAvailable().then((r) => setOcrOk(r.available));
    return () => {
      // objectURL を解放する
      setCovers((c) => {
        Object.values(c).forEach((u) => u && URL.revokeObjectURL(u));
        return {};
      });
    };
  }, [refresh]);

  /**
   * 原本PDFを端末内OCRで読み直して、本文を入れ替える。
   *
   * **原本は保存していない**ので、同梱本なら自前で開き、それ以外はその場で選んでもらう。
   * 読み取りは端末の中だけで動く（通信しない）。
   */
  const runReocr = useCallback(
    async (book: BookRecord, file: File) => {
      setMenu(null);
      setNotice(null);
      setReocr({ bookId: book.id, done: 0, total: book.pageCount });
      try {
        const before = await getBookPages(book.id);
        const { pages, failed } = await reocrBook(
          file,
          book.pageCount,
          before.map((p) => ({ pageNumber: p.pageNumber, text: p.text })),
          (done, total) => setReocr({ bookId: book.id, done, total })
        );
        const quality = qualityOf(pages);
        await replaceIndex(book.id, pages, { quality });
        await refresh();
        const pct = Math.round(quality * 35);
        setNotice(
          `「${book.title}」を読み取り直しました（ひらがな率 ${pct}%）` +
            (failed.length ? `。${failed.length}ページは読み取れず、元の本文を残しました` : "")
        );
      } catch (e) {
        setNotice(`読み取り直しに失敗しました: ${e instanceof Error ? e.message : String(e)}`);
      } finally {
        forgetDoc(`reocr|${file.name}|${file.size}`);
        setReocr(null);
      }
    },
    [refresh]
  );

  /** 「読み取り直す」を押したとき。同梱本は自前で開き、それ以外はファイルを選んでもらう */
  const startReocr = useCallback(
    async (book: BookRecord) => {
      if (book.bundled) {
        try {
          const res = await fetch(bundledUrl(book.bundled));
          if (res.ok) {
            const name = book.source?.fileName ?? book.bundled;
            await runReocr(book, new File([await res.blob()], name, { type: "application/pdf" }));
            return;
          }
        } catch {
          // 開けなければ、下と同じくファイルを選んでもらう
        }
      }
      pickFor.current = book;
      pickPdf.current?.click();
    },
    [runReocr]
  );

  const remove = useCallback(
    async (id: string) => {
      setBusy(id);
      try {
        await deleteBook(id);
        await refresh();
      } finally {
        setBusy(null);
        setConfirming(null);
        setMenu(null);
      }
    },
    [refresh]
  );

  const exportAll = useCallback(async () => {
    setNotice(null);
    const payload = await exportPayload();
    const blob = new Blob([JSON.stringify(payload)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `書斎の索引-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
    setNotice(
      `${payload.books.length}冊・${payload.pageText.length}ページ分の索引を書き出しました（${formatBytes(blob.size)}）。` +
        "これがバックアップ兼、他の端末への持ち出しファイルです。"
    );
  }, []);

  const importFile = useCallback(
    async (file: File) => {
      setNotice(null);
      try {
        const r = await importPayload(JSON.parse(await file.text()));
        await refresh();
        setNotice(`読み込み完了: ${r.added}冊を追加（${r.pages}ページ）／${r.skipped}冊は既にあったので飛ばしました`);
      } catch (e: any) {
        setNotice(e?.message ?? "読み込めませんでした");
      }
    },
    [refresh]
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">本棚</h1>
        <p className="mt-1 text-sm text-slate-400">
          表紙をタップすると本文を読めます。原本のPDFはDropbox等に置いたままで構いません。
        </p>
      </div>

      <StorageMeter status={status} />

      <div className="flex flex-wrap gap-2">
        <button
          onClick={exportAll}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 px-3 py-2 text-sm hover:bg-slate-800"
        >
          <Download className="h-4 w-4" /> 索引を書き出す（バックアップ）
        </button>
        <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-slate-700 px-3 py-2 text-sm hover:bg-slate-800">
          <FileUp className="h-4 w-4" /> 索引を読み込む
          <input
            type="file"
            accept="application/json,.json"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) importFile(f);
              e.target.value = "";
            }}
          />
        </label>
      </div>

      {notice && (
        <p className="rounded-xl border border-sky-800 bg-sky-950/40 px-4 py-3 text-sm text-sky-200">{notice}</p>
      )}

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
        <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {books.map((b) => {
            const cover = covers[b.id];
            const readable = (b.quality ?? 0) >= READABLE_QUALITY;
            // 読み取り直しを勧めるか。**ひらがな率だけでは足りない**（constants の REBUILT_HEAVY 参照）
            const worthReocr = !readable || (b.rebuiltRatio ?? 0) >= REBUILT_HEAVY;
            return (
              <li key={b.id} className="flex flex-col gap-2">
                <Link
                  href={`/read?book=${encodeURIComponent(b.id)}&page=${b.lastReadPage ?? 1}`}
                  className="group relative block overflow-hidden rounded-lg border border-slate-800 bg-slate-900 shadow-lg transition hover:border-sky-600"
                  style={{ aspectRatio: "1 / 1.414" }}
                >
                  {cover ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={cover}
                      alt={`${b.title} の表紙`}
                      className="h-full w-full object-cover transition group-hover:opacity-90"
                    />
                  ) : (
                    <span className="flex h-full w-full flex-col items-center justify-center gap-2 p-3 text-center text-xs text-slate-400">
                      <ImageOff className="h-6 w-6" />
                      表紙なし
                    </span>
                  )}
                  <span className="absolute inset-x-0 bottom-0 bg-slate-950/80 px-2 py-1 text-[11px] text-slate-200 backdrop-blur">
                    {b.pageCount}ページ
                    {b.lastReadPage && b.lastReadPage > 1 ? ` ／ ${b.lastReadPage}p まで読んだ` : ""}
                  </span>
                </Link>

                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold" title={b.title}>
                    {b.title}
                  </p>
                  <p className="mt-0.5 flex flex-wrap items-center gap-1 text-[11px] text-slate-400">
                    <span
                      className={[
                        "rounded-full px-1.5 py-0.5",
                        readable ? "bg-emerald-900/40 text-emerald-300" : "bg-amber-900/40 text-amber-300",
                      ].join(" ")}
                      title="本文のひらがな率から出した目安。低い本はOCRが崩れているか図表が多い"
                    >
                      {readable ? "文字で読める" : "図解多め"}
                    </span>
                    {b.quality != null && (
                      // 取り込み画面の「読みやすさ」は 0〜100% に正規化した値。
                      // ここは素のひらがな率なので、同じ言葉を使うと数字が食い違って見える
                      <span title="本文のひらがな率（散文なら30〜45%）。読みやすさの根拠にしている値">
                        ひらがな率 {Math.round(b.quality * 35)}%
                      </span>
                    )}
                    <span>{(b.textChars / 10000).toFixed(1)}万字</span>
                    {(b.cachedPages ?? 0) > 0 && <span>／画像 {b.cachedPages}枚 {formatBytes(b.cachedBytes ?? 0)}</span>}
                  </p>
                  <button
                    onClick={() => setMenu(menu === b.id ? null : b.id)}
                    className="mt-1 text-[11px] text-slate-400 underline hover:text-slate-200"
                  >
                    {menu === b.id ? "閉じる" : "管理"}
                  </button>

                  {menu === b.id && (
                    <div className="mt-2 space-y-2 rounded-lg border border-slate-800 bg-slate-900/80 p-2 text-xs">
                      <p className="text-slate-400">
                        原本: {b.source?.fileName ?? "不明"}（{formatBytes(b.source?.fileSize ?? 0)}）
                      </p>
                      {ocrOk && worthReocr && (
                        <div className="space-y-1 rounded border border-amber-900/60 bg-amber-950/20 p-2">
                          <p className="text-amber-200">
                            {(b.rebuiltRatio ?? 0) >= REBUILT_HEAVY
                              ? "縦書きページが1文字ずつ拾われている本です。"
                              : "文字の読み取りが崩れている本です。"}
                            <strong>端末の中だけで</strong>読み取り直せます
                            （通信しません。{b.pageCount}ページで数分かかります）。
                          </p>
                          <button
                            onClick={() => startReocr(b)}
                            disabled={reocr !== null}
                            className="inline-flex items-center gap-1 rounded border border-amber-700 px-2 py-1 text-amber-200 hover:bg-amber-900/30 disabled:opacity-50"
                          >
                            {reocr?.bookId === b.id ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <ScanText className="h-3.5 w-3.5" />
                            )}
                            {reocr?.bookId === b.id
                              ? `読み取り中 ${reocr.done}/${reocr.total}ページ`
                              : "文字を読み取り直す"}
                          </button>
                        </div>
                      )}
                      <button
                        onClick={async () => {
                          setBusy(b.id);
                          await clearImageCache(b.id);
                          await refresh();
                          setBusy(null);
                        }}
                        disabled={busy === b.id || (b.cachedPages ?? 0) === 0}
                        className="inline-flex items-center gap-1 rounded border border-slate-700 px-2 py-1 hover:bg-slate-800 disabled:opacity-50"
                      >
                        <Eraser className="h-3.5 w-3.5" /> ページ画像を消す（本文は残る）
                      </button>
                      {confirming === b.id ? (
                        <div className="space-y-1">
                          <p className="text-rose-300">
                            この本の索引・画像をすべて削除します。<strong>元に戻せません</strong>
                          </p>
                          <div className="flex gap-1">
                            <button
                              onClick={() => remove(b.id)}
                              disabled={busy === b.id}
                              aria-label={`「${b.title}」を削除する（確定）`}
                              className="inline-flex items-center gap-1 rounded bg-rose-600 px-2 py-1 font-semibold text-white hover:bg-rose-500"
                            >
                              {busy === b.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                              本当に削除
                            </button>
                            <button
                              onClick={() => setConfirming(null)}
                              className="rounded border border-slate-700 px-2 py-1 hover:bg-slate-800"
                            >
                              やめる
                            </button>
                          </div>
                        </div>
                      ) : (
                        <button
                          onClick={() => setConfirming(b.id)}
                          aria-label={`「${b.title}」を削除`}
                          className="inline-flex items-center gap-1 rounded border border-slate-700 px-2 py-1 text-rose-300 hover:bg-rose-900/30"
                        >
                          <Trash2 className="h-3.5 w-3.5" /> この本を削除
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {/* 読み取り直しのときに原本PDFを選んでもらう（本文だけ持っていて原本は保存していない） */}
      <input
        ref={pickPdf}
        type="file"
        accept="application/pdf,.pdf"
        className="hidden"
        onChange={async (e) => {
          const file = e.target.files?.[0];
          const book = pickFor.current;
          e.target.value = "";       // 同じファイルを続けて選べるようにする
          pickFor.current = null;
          if (file && book) await runReocr(book, file);
        }}
      />

      {books && books.length > 0 && (
        <p className="text-xs text-slate-500">
          <BookOpen className="mr-1 inline h-3.5 w-3.5" />
          「文字で読める」は本文のひらがな率から出した目安です。「図解多め」の本は、
          読書画面で<strong className="text-slate-400">紙面を見る</strong>に切り替えると原本のページを表示できます
          （原本のPDFをその場で選びます）。
        </p>
      )}
    </div>
  );
}
