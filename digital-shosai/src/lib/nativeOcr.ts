"use client";

// 端末の中だけで完結する文書OCR（Apple Vision）。
//
// **通信はしない。** 画像も読み取った文字も端末の外へ出ない。生成AIも使っていない。
//
// 使えるのは **iOS 26 以降のアプリ版だけ**。理由:
//   - ブラウザからは Vision を呼べない（Web版では常に使えない）
//   - 縦書きの日本語を読めるのは `RecognizeDocumentsRequest`（iOS 26〜）だけで、
//     従来の `VNRecognizeTextRequest` は縦書きページからほとんど文字を取れない
//     （2026-08-28 に実測。114ページの本の縦書きページで15文字）
//
// 使えない環境では `available()` が false を返す。**画面はそれを見てボタンごと出さない。**

import { registerPlugin } from "@capacitor/core";
import { assembleLines, renderPageForOcr } from "@/lib/pdfClient";
import type { ProgressFn } from "@/lib/pdfClient";

/** OCRが返す1行。位置は左下原点の正規化座標（Vision の流儀のまま） */
export interface OcrLine {
  text: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

interface DocumentOCRPlugin {
  isAvailable(): Promise<{ available: boolean; reason: string }>;
  recognize(options: { image: string }): Promise<{ lines: OcrLine[]; width: number; height: number }>;
}

const DocumentOCR = registerPlugin<DocumentOCRPlugin>("DocumentOCR");

let cached: { available: boolean; reason: string } | null = null;

/**
 * この端末で読み取り直しができるか。**一度だけ聞いて覚える。**
 * プラグインが入っていない環境（Web版）では例外になるので、それも「使えない」として扱う。
 */
export async function available(): Promise<{ available: boolean; reason: string }> {
  if (cached) return cached;
  try {
    cached = await DocumentOCR.isAvailable();
  } catch {
    cached = { available: false, reason: "この環境では端末内OCRを使えません（アプリ版のみ）" };
  }
  return cached;
}

/** 1ページ読む。行は読み順で返るので、取り込み時と同じ規則で本文に組み立てる */
export async function recognizePage(file: File, pageNumber: number, key?: string): Promise<string> {
  const image = await renderPageForOcr(file, pageNumber, key);
  const { lines } = await DocumentOCR.recognize({ image });
  return assembleLines(lines.map((l) => l.text));
}

export interface ReocrResult {
  pages: { pageNumber: number; text: string }[];
  /** 読み取れなかったページ番号（画像化やOCRで失敗したもの） */
  failed: number[];
}

/**
 * 1冊まるごと読み取り直す。
 *
 * **途中で失敗したページは飛ばして続ける。** 500ページの本で1ページこけたら
 * 全部やり直し、では使い物にならない。落ちたページは元の本文をそのまま残す
 * （呼ぶ側が `previous` に渡す）。
 */
export async function reocrBook(
  file: File,
  pageCount: number,
  previous: { pageNumber: number; text: string }[],
  onProgress?: ProgressFn
): Promise<ReocrResult> {
  const before = new Map(previous.map((p) => [p.pageNumber, p.text]));
  const pages: { pageNumber: number; text: string }[] = [];
  const failed: number[] = [];
  const key = `reocr|${file.name}|${file.size}`;
  for (let i = 1; i <= pageCount; i++) {
    try {
      const text = await recognizePage(file, i, key);
      // **空だったら元の本文を残す。** 白紙ページを「読み取れた」ことにすると索引が痩せる
      pages.push({ pageNumber: i, text: text.trim() ? text : (before.get(i) ?? "") });
    } catch {
      failed.push(i);
      pages.push({ pageNumber: i, text: before.get(i) ?? "" });
    }
    onProgress?.(i, pageCount);
  }
  return { pages, failed };
}
