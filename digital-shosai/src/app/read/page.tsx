"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  ChevronLeft, ChevronRight, Loader2, Image as ImageIcon, FileText,
  Type, Minus, Plus, ArrowLeft, FolderOpen,
} from "lucide-react";
import { highlight } from "@/lib/highlight";
import { PAGE_GARBLED_HIRAGANA, READABLE_QUALITY, READER_DEFAULTS } from "@/lib/constants";
import { cacheImage, getBookPages, getCachedImageUrl, getBook, relinkSource, setLastRead, type BookRecord, type ReadPage } from "@/lib/db";
import { recall, remember } from "@/lib/session";
import { bundledUrl } from "@/lib/bundled";
import { renderPage, sourceOf } from "@/lib/pdfClient";

type View = "text" | "image";

/**
 * 読書画面。**本文（テキスト）で読むのが主**で、図解を見たいときだけ紙面に切り替える。
 *
 * スマホで読むための調整を持たせている（文字の大きさ・行間・書体・幅）。
 * 設定は localStorage に置く（端末ごとの好み）。
 */
export default function ReadPage() {
  const [book, setBook] = useState<BookRecord | null>(null);
  const [pages, setPages] = useState<ReadPage[] | null>(null);
  const [current, setCurrent] = useState(1);
  const [keyword, setKeyword] = useState("");
  const [view, setView] = useState<View>("text");
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [imageState, setImageState] = useState<"idle" | "loading" | "need-file" | "error">("idle");
  const [font, setFont] = useState(READER_DEFAULTS);
  const fileInput = useRef<HTMLInputElement>(null);
  const bookIdRef = useRef<string>("");
  const shellRef = useRef<HTMLDivElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const [shellHeight, setShellHeight] = useState<number>();

  // 起動時: クエリから本とページを決める（静的書き出しなので window から読む）
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const id = q.get("book") ?? "";
    bookIdRef.current = id;
    setKeyword(q.get("q") ?? "");
    const page = Number(q.get("page") ?? "1");
    (async () => {
      const [b, ps] = await Promise.all([getBook(id), getBookPages(id)]);
      setBook(b ?? null);
      setPages(ps);
      setCurrent(Math.min(Math.max(1, page || 1), ps.length || 1));
    })();
    try {
      const saved = localStorage.getItem("shosai-reader");
      if (saved) setFont({ ...READER_DEFAULTS, ...JSON.parse(saved) });
    } catch {
      /* 好みが読めなくても既定で動かす */
    }
  }, []);

  useEffect(() => {
    try { localStorage.setItem("shosai-reader", JSON.stringify(font)); } catch { /* noop */ }
  }, [font]);

  // しおり
  useEffect(() => {
    if (book && current) setLastRead(book.id, current);
  }, [book, current]);

  /**
   * 読む枠の高さを画面いっぱいに固定する。
   *
   * ページごとに文章量が違うので、枠が中身に合わせて伸び縮みすると
   * 「前のページ／次のページ」のボタンが毎回動いて押しづらい。
   * → 枠は画面の残り全部で固定し、長い文章は**枠の中でスクロール**させる。
   * 端末や向きで余白が変わるので、実際の位置を測って決める（env() の計算に依存しない）。
   */
  useEffect(() => {
    const typing = () => {
      const el = document.activeElement;
      return !!el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA");
    };
    /**
     * 入力欄を触るとキーボードが出て、iOSが**ページごと上へずらす**。
     * 閉じても戻らないので、見出しが時計の下に潜ったままになる（実機で確認）。
     * → 入力していないときは必ず先頭へ戻してから測り直す。
     */
    const fit = () => {
      const el = shellRef.current;
      if (!el || typing()) return;
      // 横にもずれる（変換候補バーが出たとき）。縦だけ見ていると直らない
      if (window.scrollX !== 0 || window.scrollY !== 0) window.scrollTo(0, 0);
      const top = el.getBoundingClientRect().top;
      const safeBottom = parseFloat(getComputedStyle(document.body).paddingBottom) || 0;
      const mainBottom = 24; // <main> の py-6
      setShellHeight(Math.max(320, window.innerHeight - top - safeBottom - mainBottom));
    };
    fit();
    window.addEventListener("resize", fit);
    window.addEventListener("orientationchange", fit);
    window.addEventListener("scroll", fit, { passive: true });
    window.visualViewport?.addEventListener("resize", fit);
    // 入力欄から離れた直後にも戻す（キーボードが閉じても resize が来ない端末がある）
    const onOut = () => setTimeout(fit, 50);
    window.addEventListener("focusout", onOut);
    return () => {
      window.removeEventListener("focusout", onOut);
      window.removeEventListener("resize", fit);
      window.removeEventListener("orientationchange", fit);
      window.removeEventListener("scroll", fit);
      window.visualViewport?.removeEventListener("resize", fit);
    };
  }, [pages]);

  // ページを移ったら枠の中身は先頭から読む（前のページの読み位置が残らないように）
  useEffect(() => {
    bodyRef.current?.scrollTo({ top: 0 });
  }, [current, view]);

  const page = useMemo(() => pages?.find((p) => p.pageNumber === current) ?? null, [pages, current]);

  // このページの文字が崩れていないか（ひらがな率で見る）。
  // OCRが弱いページは組み直しても読めないので、**紙面へ逃げる導線をその場で出す**
  const garbled = useMemo(() => {
    const t = (page?.text ?? "").replace(/\s/g, "");
    if (t.length < 40) return false;
    const hira = (t.match(/[ぁ-ん]/g)?.length ?? 0) / t.length;
    return hira < PAGE_GARBLED_HIRAGANA;
  }, [page]);
  const total = pages?.length ?? 0;

  const move = useCallback(
    (delta: number) => {
      setCurrent((c) => Math.min(Math.max(1, c + delta), total || 1));
      setImageUrl(null);
      setImageState("idle");
    },
    [total]
  );

  // ← → で移動
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") move(1);
      if (e.key === "ArrowLeft") move(-1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [move]);

  /** 紙面を出す。キャッシュ → その場で描画 → 原本を選んでもらう の順に試す */
  const showImage = useCallback(
    async (file?: File) => {
      if (!book || !page) return;
      setView("image");
      setImageState("loading");
      try {
        const cached = await getCachedImageUrl(page.id);
        if (cached && !file) {
          setImageUrl(cached);
          setImageState("idle");
          return;
        }
        // 同梱の収録作品は原本がアプリの中にあるので、選び直してもらわずに自分で開く
        let src = file ?? recall(book.id);
        if (!src && book.bundled) {
          const res = await fetch(bundledUrl(book.bundled));
          if (res.ok) {
            src = new File([await res.blob()], book.source?.fileName ?? book.bundled, {
              type: "application/pdf",
            });
            remember(book.id, src);
          }
        }
        if (!src) {
          setImageState("need-file");
          return;
        }
        const { blob, width, height } = await renderPage(src, page.pageNumber, book.id);
        await cacheImage(page.id, book.id, page.pageNumber, blob, { width, height });
        setImageUrl(URL.createObjectURL(blob));
        setImageState("idle");
      } catch (e) {
        setImageState("error");
      }
    },
    [book, page]
  );

  const pickOriginal = useCallback(
    async (file: File) => {
      if (!book) return;
      remember(book.id, file);
      // 名前やサイズが変わっていたら目印を更新しておく（別の場所へ移した場合）
      const s = sourceOf(file);
      if (!book.source || book.source.fileName !== s.fileName || book.source.fileSize !== s.fileSize) {
        await relinkSource(book.id, s);
      }
      showImage(file);
    },
    [book, showImage]
  );

  if (!pages) {
    return (
      <div className="flex justify-center py-16 text-slate-500">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }

  if (!book) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900 p-8 text-center">
        <p className="text-slate-300">この本が見つかりませんでした。</p>
        <Link href="/library" className="mt-3 inline-block text-sm text-sky-400 underline">
          本棚へ戻る
        </Link>
      </div>
    );
  }

  return (
    // 枠とボタンの位置を固定する（高さは実測。JSが動く前は自然な高さで出す）
    <div ref={shellRef} className="flex flex-col gap-3" style={{ height: shellHeight }}>
      {/* 見出しと操作 */}
      <div className="flex flex-none flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <Link href="/library" className="rounded-lg p-1.5 hover:bg-slate-800" aria-label="本棚へ戻る">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div className="min-w-0">
            <p className="truncate font-semibold" title={book.title}>{book.title}</p>
            <p className="text-xs text-slate-400">
              {current} / {total} ページ
              {(book.quality ?? 0) < READABLE_QUALITY && "（図解多めの本です。読みにくい所は紙面で）"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1">
          {/* 文字の調整 */}
          <button
            onClick={() => setFont((f) => ({ ...f, fontSize: Math.max(14, f.fontSize - 1) }))}
            className="rounded-lg border border-slate-700 p-1.5 hover:bg-slate-800"
            aria-label="文字を小さく"
          >
            <Minus className="h-4 w-4" />
          </button>
          <span className="w-10 text-center text-xs text-slate-400">{font.fontSize}px</span>
          <button
            onClick={() => setFont((f) => ({ ...f, fontSize: Math.min(26, f.fontSize + 1) }))}
            className="rounded-lg border border-slate-700 p-1.5 hover:bg-slate-800"
            aria-label="文字を大きく"
          >
            <Plus className="h-4 w-4" />
          </button>
          <button
            onClick={() => setFont((f) => ({ ...f, serif: !f.serif }))}
            className="rounded-lg border border-slate-700 p-1.5 hover:bg-slate-800"
            aria-label={font.serif ? "ゴシック体にする" : "明朝体にする"}
            title={font.serif ? "明朝体（タップでゴシック体）" : "ゴシック体（タップで明朝体）"}
          >
            <Type className="h-4 w-4" />
          </button>
          {/* 表示の切替 */}
          <button
            onClick={() => (view === "text" ? showImage() : (setView("text"), setImageState("idle")))}
            className="ml-1 inline-flex items-center gap-1 rounded-lg border border-slate-700 px-2.5 py-1.5 text-sm hover:bg-slate-800"
          >
            {view === "text" ? (
              <>
                <ImageIcon className="h-4 w-4" /> 紙面を見る
              </>
            ) : (
              <>
                <FileText className="h-4 w-4" /> 本文に戻る
              </>
            )}
          </button>
        </div>
      </div>

      {/* 読む枠（高さ固定・中身だけスクロール）。本文と紙面はこの中で切り替える */}
      <div
        ref={bodyRef}
        className="thin-scroll min-h-0 flex-1 overflow-y-auto overscroll-contain rounded-xl border border-slate-800 bg-slate-900/60"
      >
      {/* 本文 */}
      {view === "text" && (
        <article
          className="mx-auto px-5 py-6"
          style={{
            maxWidth: "38em",
            fontSize: `${font.fontSize}px`,
            lineHeight: font.lineHeight,
            fontFamily: font.serif
              ? '"Hiragino Mincho ProN", "Yu Mincho", serif'
              : '"Hiragino Sans", "Hiragino Kaku Gothic ProN", system-ui, sans-serif',
          }}
        >
          {page && page.text.trim() ? (
            <>
              {garbled && (
                <p className="mb-4 rounded-lg border border-amber-700 bg-amber-950/30 px-3 py-2 text-[13px] leading-normal text-amber-200">
                  このページは文字の読み取りが崩れています（図表のページか、OCRが弱い所です）。
                  <button onClick={() => showImage()} className="ml-1 underline">紙面を見る</button>
                </p>
              )}
              <p className="whitespace-pre-wrap break-words text-slate-100">
                {highlight(page.text, keyword)}
              </p>
            </>
          ) : (
            <p className="text-slate-400">
              このページには文字がありません（図表だけのページかもしれません）。
              <button onClick={() => showImage()} className="ml-1 text-sky-400 underline">
                紙面を見る
              </button>
            </p>
          )}
        </article>
      )}

      {/* 紙面（原本から都度描画してキャッシュ） */}
      {view === "image" && (
        <div className="p-4">
          {imageState === "loading" && (
            <div className="flex h-64 items-center justify-center gap-2 text-slate-400">
              <Loader2 className="h-5 w-5 animate-spin" /> ページを描いています…
            </div>
          )}
          {imageState === "need-file" && (
            <div className="space-y-3 text-center">
              <p className="text-sm text-slate-300">
                このページの紙面を出すには原本のPDFが必要です。
                <br />
                <span className="text-slate-400">
                  原本: {book.source?.fileName ?? "不明"}（Dropbox等から選んでください。端末には保存しません）
                </span>
              </p>
              <button
                onClick={() => fileInput.current?.click()}
                className="inline-flex items-center gap-1.5 rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-500"
              >
                <FolderOpen className="h-4 w-4" /> 原本のPDFを選ぶ
              </button>
              <input
                ref={fileInput}
                type="file"
                accept="application/pdf,.pdf"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) pickOriginal(f);
                  e.target.value = "";
                }}
              />
            </div>
          )}
          {imageState === "error" && (
            <p className="text-center text-sm text-rose-300">
              このページを描けませんでした。別のPDFを選んだか、ページ数が合っていない可能性があります。
            </p>
          )}
          {imageUrl && imageState === "idle" && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={imageUrl}
              alt={`${book.title} ${current}ページ`}
              className="mx-auto h-auto w-full max-w-3xl rounded-lg border border-slate-800"
            />
          )}
        </div>
      )}
      </div>

      {/* ページ送り（枠の下に固定。ページを移っても動かない） */}
      <div className="flex flex-none items-center justify-between gap-2">
        <button
          onClick={() => move(-1)}
          disabled={current <= 1}
          className="inline-flex items-center gap-1 rounded-lg border border-slate-700 px-3 py-2 text-sm hover:bg-slate-800 disabled:opacity-40"
        >
          <ChevronLeft className="h-4 w-4" /> 前のページ
        </button>

        <label className="flex items-center gap-2 text-xs text-slate-400">
          ページ
          <input
            type="number"
            min={1}
            max={total}
            value={current}
            onChange={(e) => {
              const n = Number(e.target.value);
              if (n >= 1 && n <= total) {
                setCurrent(n);
                setImageUrl(null);
                setImageState("idle");
              }
            }}
            /* 16px未満だと iOS が触った瞬間に画面を拡大し、枠がずれて見える。text-base のままにする */
            className="w-20 rounded-lg border border-slate-700 bg-slate-900 px-2 py-1 text-center text-base text-slate-100"
          />
          / {total}
        </label>

        <button
          onClick={() => move(1)}
          disabled={current >= total}
          className="inline-flex items-center gap-1 rounded-lg border border-slate-700 px-3 py-2 text-sm hover:bg-slate-800 disabled:opacity-40"
        >
          次のページ <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
