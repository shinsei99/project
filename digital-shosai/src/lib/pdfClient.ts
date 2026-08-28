"use client";

// pdf.js（legacy build）でブラウザ内のみ PDF を処理する。サーバーには送らない。
//
// v3（2026-08-17）の役割分担:
//   extractIndex() … 取り込み時。**テキストだけ**を抜いて索引にする（1ページ1ms程度）
//   renderPage()   … 見たいページだけ、その場で画像にする（60〜110ms程度）
import * as pdfjsLib from "pdfjs-dist/legacy/build/pdf";
import { COVER_CANDIDATES, COVER_TARGET_WIDTH, IMAGE_CANDIDATES, OCR_RENDER_SCALE, RENDER_SCALE } from "@/lib/constants";
import type { BookSource } from "@/lib/types";

// ワーカーは public/ に同梱した自前ホストのものを使う（オフライン動作）
pdfjsLib.GlobalWorkerOptions.workerSrc = "./pdf.worker.min.mjs";

export type ProgressFn = (done: number, total: number) => void;

export function titleFromFileName(name: string): string {
  return name.replace(/\.pdf$/i, "");
}

export function sourceOf(file: File): BookSource {
  return { fileName: file.name, fileSize: file.size, lastModified: file.lastModified };
}

function open(file: File | ArrayBuffer) {
  return pdfjsLib.getDocument({
    data: file instanceof ArrayBuffer ? file : undefined,
    url: undefined,
    // 日本語など CID フォントのテキスト抽出・描画に必須（public/ に同梱）
    cMapUrl: "./cmaps/",
    cMapPacked: true,
    standardFontDataUrl: "./standard_fonts/",
  } as any).promise;
}

// ============================================================================
// 本文の組み直し
//
// **スキャン本のOCRテキストは、そのまま読める形では出てこない。**
// 縦書きのページでは1文字ずつ別の行として拾われ、1行=1文字になる（実機の本で実測）。
// 座標を見て「列（縦書き）／行（横書き）」にまとめ直すと、崩れたページの
// 88%が読める形になった（3/25 → 22/25）。**文字そのものの誤認は直せない。**
// ============================================================================

interface Glyph { c: string; x: number; y: number; size: number }

function groupBy(glyphs: Glyph[], axis: "x" | "y", tol: number): Glyph[][] {
  const groups: { k: number; items: Glyph[] }[] = [];
  for (const g of [...glyphs].sort((a, b) => a[axis] - b[axis])) {
    const last = groups[groups.length - 1];
    if (last && Math.abs(g[axis] - last.k) <= tol) {
      last.items.push(g);
      last.k = (last.k * (last.items.length - 1) + g[axis]) / last.items.length;
    } else {
      groups.push({ k: g[axis], items: [g] });
    }
  }
  return groups.map((x) => x.items);
}

/** 行末が句読点で終わっていない行を次の行とつなげて、段落にする（スマホで読みやすくするため） */
function joinParagraphs(lines: string[]): string {
  const out: string[] = [];
  for (const raw of lines) {
    const line = raw.trim();
    if (!line) continue;
    const prev = out[out.length - 1];
    const endsSentence = /[。．！？!?」』）\)]$/.test(prev ?? "");
    // ページ先頭の短い1行は**見出し（柱）**として独立させる。
    // 本文とつなげると「企業レベルの戦略策定魔されないようにしていた。」のようになる（実際に踏んだ）
    const prevIsHeading = out.length === 1 && (prev?.length ?? 0) <= 22 && !/[。．、]/.test(prev ?? "");
    // 「1」だけの行は、次の行の頭（例:「1泊2食付」）から切り離された数字なので必ずつなげる
    const prevIsLoneNumber = !!prev && /^\d{1,2}$/.test(prev) && !/^\d/.test(line);
    // 直前が文の途中で終わっていて、どちらも短すぎなければ連結する
    if (prev && (prevIsLoneNumber || (!endsSentence && !prevIsHeading && prev.length > 1 && line.length > 1))) {
      out[out.length - 1] = prev + line;
    } else {
      out.push(line);
    }
  }
  return out.join("\n");
}

/**
 * ノンブル（ページ番号）と柱（ページ上部の章題）を落とす。
 *
 * **ページの先頭と末尾だけを見る。** 途中の数字だけの行を消すと、
 * 「1泊2食付」の「1」のように**本文の一部を削ってしまう**（実際に踏んだ）。
 */
function dropRunningHeads(lines: string[]): string[] {
  const out = [...lines].map((l) => l.trim()).filter((l) => l.length > 0);
  const looksHead = (l: string) =>
    /^[\s\-–—‐]*\d{1,4}[\s\-–—‐]*$/.test(l) ||                       // 数字だけ
    (/^\d{1,4}[\s　]/.test(l) && l.length <= 22 && !/[。．]/.test(l)) || // 数字＋短い見出し
    (/[\s　]\d{1,4}$/.test(l) && l.length <= 22 && !/[。．]/.test(l));   // 短い見出し＋数字
  while (out.length && looksHead(out[0])) out.shift();
  while (out.length && looksHead(out[out.length - 1])) out.pop();
  return out;
}

function rebuild(items: any[]): string {
  const glyphs: Glyph[] = [];
  for (const it of items) {
    const s: string = it.str ?? "";
    if (!s.trim()) continue;
    const t = it.transform as number[];        // [a,b,c,d,e,f] — e,f が位置
    const size = Math.max(Math.abs(t[0]), Math.abs(t[3])) || it.height || 10;
    // 1つの item に複数文字が入っている場合は、横に等間隔で並んでいるものとして分ける
    const w = it.width || size * s.length;
    const step = s.length > 1 ? w / s.length : 0;
    [...s].forEach((c, i) => {
      if (c.trim()) glyphs.push({ c, x: t[4] + step * i, y: t[5], size });
    });
  }
  if (glyphs.length === 0) return "";

  const sizes = glyphs.map((g) => g.size).sort((a, b) => a - b);
  const size = sizes[Math.floor(sizes.length / 2)] || 10;
  const cols = groupBy(glyphs, "x", size * 0.6);
  const rows = groupBy(glyphs, "y", size * 0.6);
  const per = (gs: Glyph[][]) => gs.reduce((n, g) => n + g.length, 0) / gs.length;

  // 縦書きなら「1列に多くの文字」が並ぶ。列あたりと行あたりの文字数で判定する
  if (per(cols) > per(rows)) {
    // 縦書き: 列は右から左、列の中は上から下（PDFのyは上が大きい）
    const sorted = cols
      .map((items) => ({ x: items[0].x, items }))
      .sort((a, b) => b.x - a.x)
      .map((c) => c.items.sort((a, b) => b.y - a.y).map((g) => g.c).join(""));
    return joinParagraphs(dropRunningHeads(sorted));
  }
  const sorted = rows
    .map((items) => ({ y: items[0].y, items }))
    .sort((a, b) => b.y - a.y)
    .map((r) => r.items.sort((a, b) => a.x - b.x).map((g) => g.c).join(""));
  return joinParagraphs(dropRunningHeads(sorted));
}

// ============================================================================
// 取り込み（索引づくり）
// ============================================================================

/**
 * 読み順に並んだ「行の列」を、本文として読める形に組み立てる。
 *
 * 端末内OCR（`nativeOcr.ts`）の結果を、取り込み時とまったく同じ規則で通すために外へ出している。
 * **柱とノンブルを落としてから段落にまとめる**（順序が逆だと本文の数字を削る）。
 */
export function assembleLines(lines: string[]): string {
  return joinParagraphs(dropRunningHeads(lines));
}

/**
 * 本文の読みやすさ（0〜1）。ひらがな率 35% を満点として頭打ちにする。
 * **`extractIndex` と同じ式**。読み取り直したあとの本を同じ物差しで測るために切り出した。
 */
export function qualityOf(pages: { text: string }[]): number {
  let chars = 0;
  let hira = 0;
  for (const p of pages) {
    const t = p.text.replace(/\s/g, "");
    chars += t.length;
    hira += t.match(/[ぁ-ん]/g)?.length ?? 0;
  }
  return chars ? Math.min(1, hira / chars / 0.35) : 0;
}

export interface ExtractedPage { pageNumber: number; text: string }
export interface ExtractResult {
  pages: ExtractedPage[];
  /** 本文の読みやすさの目安（0〜1）。ひらがな率と1行の長さから出す */
  quality: number;
  /** どれくらい組み直したか（崩れていたページの割合） */
  rebuiltRatio: number;
}

function hiraganaRatio(text: string): number {
  const t = text.replace(/\s/g, "");
  if (!t) return 0;
  return (t.match(/[ぁ-ん]/g)?.length ?? 0) / t.length;
}

function medianLineLength(text: string): number {
  const lens = text.split("\n").map((l) => l.trim().length).filter(Boolean).sort((a, b) => a - b);
  return lens.length ? lens[Math.floor(lens.length / 2)] : 0;
}

/**
 * PDF から**テキストだけ**を抜き出して索引の材料にする。画像は作らない。
 * 崩れているページは座標から組み直す。
 */
export async function extractIndex(file: File, onProgress?: ProgressFn): Promise<ExtractResult> {
  const data = await file.arrayBuffer();
  const pdf = await open(data);
  const total = pdf.numPages;
  const pages: ExtractedPage[] = [];
  let rebuilt = 0;

  for (let i = 1; i <= total; i++) {
    const page = await pdf.getPage(i);
    const content = await page.getTextContent();

    // まず素直につなげ、崩れていたら座標から組み直す。
    // **柱とノンブルを落としてから段落にまとめる**（順序が逆だと本文の数字を削ってしまう）
    const plain = joinParagraphs(
      dropRunningHeads(
        (content.items as any[]).map((it) => (typeof it.str === "string" ? it.str : "")).filter(Boolean)
      )
    );
    let text = plain;
    if (medianLineLength(plain) <= 2) {
      const fixed = rebuild(content.items as any[]);
      if (medianLineLength(fixed) > medianLineLength(plain)) {
        text = fixed;
        rebuilt++;
      }
    }
    pages.push({ pageNumber: i, text });
    page.cleanup();
    onProgress?.(i, total);
  }
  await pdf.destroy();

  // 読みやすさの式は qualityOf() に置いてある（読み取り直したあとも同じ物差しで測るため）
  return { pages, quality: qualityOf(pages), rebuiltRatio: total ? rebuilt / total : 0 };
}

// ============================================================================
// ページ画像（見たいページだけ・その場で作る）
// ============================================================================

// 同じ本を続けて読むときに毎回開き直さないための、その場かぎりの保持
const openDocs = new Map<string, any>();

function toBlob(canvas: HTMLCanvasElement, mime: string, quality?: number): Promise<Blob | null> {
  return new Promise((res) => canvas.toBlob((b) => res(b), mime, quality));
}

// 1枚目で「このブラウザが実際に書き出せた形式」を確定させ、以降はそれを使う。
// **要求した形式が無視されて別形式で返ることがある**（iPhoneはWebPを書き出せない＝実機で確認）。
let decided: { mime: string; quality?: number } | null = null;

export function imageFormatInUse(): string | null {
  return decided?.mime ?? null;
}

export interface RenderedPage { blob: Blob; width: number; height: number }

export async function renderPage(
  file: File,
  pageNumber: number,
  key = file.name + "|" + file.size
): Promise<RenderedPage> {
  let pdf = openDocs.get(key);
  if (!pdf) {
    pdf = await open(await file.arrayBuffer());
    openDocs.set(key, pdf);
  }
  const page = await pdf.getPage(pageNumber);
  const viewport = page.getViewport({ scale: RENDER_SCALE });
  const canvas = document.createElement("canvas");
  canvas.width = Math.ceil(viewport.width);
  canvas.height = Math.ceil(viewport.height);
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas 2D コンテキストを取得できませんでした");
  await page.render({ canvasContext: ctx, viewport }).promise;

  let blob: Blob | null = null;
  if (decided) blob = await toBlob(canvas, decided.mime, decided.quality);
  if (!blob) {
    for (const cand of IMAGE_CANDIDATES) {
      const b = await toBlob(canvas, cand.mime, cand.quality);
      if (b && b.type === cand.mime) {
        decided = cand;
        blob = b;
        break;
      }
    }
  }
  if (!blob) {
    blob = await toBlob(canvas, "image/png");
    if (blob) decided = { mime: blob.type };
  }
  page.cleanup();
  if (!blob) throw new Error("画像化に失敗しました");
  return { blob, width: canvas.width, height: canvas.height };
}

/**
 * 端末内OCRに渡すためのページ画像を作る（base64のJPEG）。
 *
 * **読書用の画像とは別に作る。** 読書用は `RENDER_SCALE`（2.0）だが、OCRは細部を見るので
 * `OCR_RENDER_SCALE`（3.0）で描く。形式は JPEG に固定する（iPhone は WebP を書き出せない
 * ＝実機で確認済みで、ここで形式を探る意味がない）。画像はプラグインへ渡すだけで保存しない。
 */
export async function renderPageForOcr(file: File, pageNumber: number,
                                       key = file.name + "|" + file.size): Promise<string> {
  let pdf = openDocs.get(key);
  if (!pdf) {
    pdf = await open(await file.arrayBuffer());
    openDocs.set(key, pdf);
  }
  const page = await pdf.getPage(pageNumber);
  const viewport = page.getViewport({ scale: OCR_RENDER_SCALE });
  const canvas = document.createElement("canvas");
  canvas.width = Math.ceil(viewport.width);
  canvas.height = Math.ceil(viewport.height);
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas 2D コンテキストを取得できませんでした");
  await page.render({ canvasContext: ctx, viewport }).promise;
  page.cleanup();
  // data URL の前置き（"data:image/jpeg;base64,"）は付けたまま渡す。プラグイン側で落とす
  return canvas.toDataURL("image/jpeg", 0.92);
}

/**
 * 表紙（1ページ目）のサムネイルを作る。**取り込み時にこれだけは作る**（本棚に並べるため）。
 * 幅を COVER_TARGET_WIDTH に合わせるので、本文ページの画像よりずっと軽い。
 */
export async function renderCover(file: File): Promise<RenderedPage | null> {
  try {
    const pdf = await open(await file.arrayBuffer());
    const page = await pdf.getPage(1);
    const base = page.getViewport({ scale: 1 });
    const scale = Math.min(2, COVER_TARGET_WIDTH / base.width);
    const viewport = page.getViewport({ scale });
    const canvas = document.createElement("canvas");
    canvas.width = Math.ceil(viewport.width);
    canvas.height = Math.ceil(viewport.height);
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    await page.render({ canvasContext: ctx, viewport }).promise;
    let blob: Blob | null = null;
    for (const cand of COVER_CANDIDATES) {
      const b = await toBlob(canvas, cand.mime, cand.quality);
      if (b && b.type === cand.mime) { blob = b; break; }
    }
    if (!blob) blob = await toBlob(canvas, "image/png");
    page.cleanup();
    await pdf.destroy();
    return blob ? { blob, width: canvas.width, height: canvas.height } : null;
  } catch {
    return null;   // 表紙が作れなくても取り込みは続ける
  }
}

/** そのセッションで開いている原本を手放す（メモリを戻す） */
export function forgetDoc(key: string) {
  const pdf = openDocs.get(key);
  if (pdf) {
    try { pdf.destroy(); } catch { /* noop */ }
    openDocs.delete(key);
  }
}
