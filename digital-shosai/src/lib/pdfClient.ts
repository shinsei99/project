"use client";

// pdf.js（legacy build）でブラウザ内のみで PDF を処理する。
// テキスト抽出とページ画像化の両方をクライアントで行い、サーバーには送らない。
import * as pdfjsLib from "pdfjs-dist/legacy/build/pdf";
import { IMAGE_CANDIDATES, RENDER_SCALE } from "@/lib/constants";
import type { NewPage } from "@/lib/db";

// ワーカーは public/ に同梱した自前ホストのものを使う（オフライン動作）
pdfjsLib.GlobalWorkerOptions.workerSrc = "./pdf.worker.min.mjs";

export type ProgressFn = (done: number, total: number) => void;

/** canvas.toBlob を Promise で扱う（対応していない形式では type が変わって返る） */
function toBlob(canvas: HTMLCanvasElement, mime: string, quality?: number): Promise<Blob | null> {
  return new Promise((resolve) => canvas.toBlob((b) => resolve(b), mime, quality));
}

// 1枚目で「このブラウザが実際に書き出せた形式」を確定させ、以降のページはそれを使う。
// **要求した形式が無視されて別形式で返ることがある**（Safari の WebP 未対応など）ので、
// 返ってきた Blob の type を必ず確認する。黙って劣化・肥大させない。
let decidedFormat: { mime: string; quality?: number } | null = null;

async function encodePage(canvas: HTMLCanvasElement): Promise<Blob> {
  if (decidedFormat) {
    const blob = await toBlob(canvas, decidedFormat.mime, decidedFormat.quality);
    if (blob) return blob;
  }
  for (const cand of IMAGE_CANDIDATES) {
    const blob = await toBlob(canvas, cand.mime, cand.quality);
    if (blob && blob.type === cand.mime) {
      decidedFormat = cand;
      return blob;
    }
  }
  // どれも型が一致しなかった場合は、ブラウザが返したものをそのまま使う（PNGになる）
  const fallback = await toBlob(canvas, "image/png");
  if (!fallback) throw new Error("画像化に失敗しました");
  decidedFormat = { mime: fallback.type };
  return fallback;
}

/** 実際に使われた画像形式（"image/webp" など）。取り込み後の表示用 */
export function imageFormatInUse(): string | null {
  return decidedFormat?.mime ?? null;
}

/**
 * PDF をページごとに「テキスト」＋「ページ画像」に変換して返す。
 * すべて端末内で完結する。画像は WebP を優先し、対応していなければ PNG に落とす。
 */
export async function processPdf(file: File, onProgress?: ProgressFn): Promise<NewPage[]> {
  const data = await file.arrayBuffer();
  const pdf = await pdfjsLib.getDocument({
    data,
    // 日本語など CID フォントのテキスト抽出・描画に必須（public/ に同梱）
    cMapUrl: "./cmaps/",
    cMapPacked: true,
    standardFontDataUrl: "./standard_fonts/",
  }).promise;
  const total = pdf.numPages;
  const pages: NewPage[] = [];

  for (let i = 1; i <= total; i++) {
    const page = await pdf.getPage(i);

    // --- テキスト抽出（行の折り返しを推定） ---
    const textContent = await page.getTextContent();
    let lastY: number | undefined;
    let text = "";
    for (const item of textContent.items as any[]) {
      if (typeof item.str !== "string") continue;
      if (lastY === undefined || lastY === item.transform[5]) {
        text += item.str;
      } else {
        text += "\n" + item.str;
      }
      lastY = item.transform[5];
    }

    // --- ページ画像化（canvas → WebP または PNG Blob） ---
    const viewport = page.getViewport({ scale: RENDER_SCALE });
    const canvas = document.createElement("canvas");
    canvas.width = Math.ceil(viewport.width);
    canvas.height = Math.ceil(viewport.height);
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Canvas 2D コンテキストを取得できませんでした");

    await page.render({ canvasContext: ctx, viewport }).promise;
    const image = await encodePage(canvas);

    pages.push({ pageNumber: i, content: text, image });
    page.cleanup();
    onProgress?.(i, total);
  }

  await pdf.destroy();
  return pages;
}

export function titleFromFileName(name: string): string {
  return name.replace(/\.pdf$/i, "");
}
