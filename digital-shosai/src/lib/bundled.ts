"use client";

/**
 * 最初から入っている本（収録作品）。
 *
 * 空の書斎だと何もできないので、**著作権保護期間が満了した青空文庫の作品**を
 * アプリに同梱し、初回起動時に取り込む。取り込み後は自分で入れた本と同じ扱いで、
 * 蔵書画面から削除できる（消したものは復活させない）。
 *
 * 同梱PDFは `public/books/` に置く。原本がアプリの中にあるので、
 * **紙面表示のときにファイルを選び直してもらう必要が無い**（bundled を見て自前で開く）。
 */

export interface BundledBook {
  /** public/books/ の中のファイル名 */
  file: string;
  title: string;
  author: string;
}

/** 初回の取り込みを済ませた印（消した本を復活させないため、蔵書数では判定しない） */
export const BUNDLED_DONE_KEY = "shosai-bundled-loaded";

/**
 * 同梱ファイルのURL。
 * ページによって相対パスの基準が変わる（`/` と `/read`）ので、必ずルートから組み立てる。
 */
export function bundledUrl(name: string): string {
  return `${window.location.origin}/books/${encodeURIComponent(name)}`;
}

/** 表示名つきのファイル名。取り込み側はこの名前から題名を作る */
export function bundledFileName(b: BundledBook): string {
  return `${b.title}（${b.author}）.pdf`;
}

export async function listBundled(): Promise<BundledBook[]> {
  try {
    const res = await fetch(bundledUrl("index.json"));
    if (!res.ok) return [];
    const list = await res.json();
    return Array.isArray(list) ? list : [];
  } catch {
    return []; // 同梱を外した版でも動くようにする
  }
}

export async function bundledAsFile(b: BundledBook): Promise<File> {
  const res = await fetch(bundledUrl(b.file));
  if (!res.ok) throw new Error(`収録作品を開けませんでした（${b.file}）`);
  const blob = await res.blob();
  return new File([blob], bundledFileName(b), { type: "application/pdf", lastModified: 0 });
}
