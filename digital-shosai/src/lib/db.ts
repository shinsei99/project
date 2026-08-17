"use client";

import { openDB, type DBSchema, type IDBPDatabase } from "idb";
import { SEARCH_LIMIT } from "@/lib/constants";
import type { LibraryStatus, SearchResult } from "@/lib/types";

// ============================================================
// 端末内データベース（IndexedDB）
// すべてのデータ（本・ページ・画像）はこの端末のブラウザ/WebView 内にのみ保存され、
// 外部サーバーには一切送信されない。
//
// v2（2026-08-17）で構造を変えた理由 ─ **検索を軽くするため**。
//   v1 は `pages`（テキスト＋画像Blobが同居）を検索のたびにカーソルで全件走査していた。
//   1レコードごとに画像を抱えたレコードを読み出すので、蔵書が増えるほど重くなる。
//   → テキストだけの軽いストア `pageText` を分け、検索はそこだけを見る。
//     画像は詳細を開いたときに `pages` から1件だけ取る。
// ============================================================

export interface BookRecord {
  id: string;
  title: string;
  uploadedAt: number;
  pageCount: number;
  /** ページ画像の合計バイト数（容量表示・削除の判断材料。v1のデータは移行時に集計する） */
  imageBytes?: number;
  /** 画像の形式（"image/webp" など。どの形式で保存されたかを後から確認できるように） */
  imageMime?: string;
}

export interface PageRecord {
  id: string;
  bookId: string;
  pageNumber: number;
  image: Blob;
  /** v1 で書かれた本文。v2 以降は `pageText` 側に持つので新規保存では書かない */
  content?: string;
}

/** 検索専用の軽いレコード（画像を含まない） */
export interface PageTextRecord {
  id: string; // pages と同じ id
  bookId: string;
  pageNumber: number;
  text: string;
  /** 小文字化済みの本文。検索のたびに toLowerCase() をやり直さないために持っておく */
  lower: string;
}

interface ShosaiDB extends DBSchema {
  books: { key: string; value: BookRecord };
  pages: {
    key: string;
    value: PageRecord;
    indexes: { byBook: string };
  };
  pageText: {
    key: string;
    value: PageTextRecord;
    indexes: { byBook: string };
  };
}

const DB_NAME = "digital-shosai";
const DB_VERSION = 2;

let dbPromise: Promise<IDBPDatabase<ShosaiDB>> | null = null;

function getDB() {
  if (!dbPromise) {
    dbPromise = openDB<ShosaiDB>(DB_NAME, DB_VERSION, {
      async upgrade(db, oldVersion, _newVersion, tx) {
        // --- v1 の器（初回起動もここを通る） ---
        if (!db.objectStoreNames.contains("books")) {
          db.createObjectStore("books", { keyPath: "id" });
        }
        if (!db.objectStoreNames.contains("pages")) {
          const store = db.createObjectStore("pages", { keyPath: "id" });
          store.createIndex("byBook", "bookId");
        }

        // --- v2: 検索用のテキストストアを作る ---
        if (!db.objectStoreNames.contains("pageText")) {
          const store = db.createObjectStore("pageText", { keyPath: "id" });
          store.createIndex("byBook", "bookId");
        }

        // 広告（動画リワードで本棚スロット+1）をやめたので、その保存先も捨てる。
        // `profile` は v2 のスキーマ定義から消したため、型の上では存在しない名前になる。
        // 既存の端末には実体が残っているので、名前で消すために型を外す
        const names: DOMStringList = db.objectStoreNames;
        if (names.contains("profile")) {
          (db as unknown as IDBDatabase).deleteObjectStore("profile");
        }

        // --- v1 で入っていたデータの移行 ---
        // すでに取り込んだ本のテキストを pageText へ写し、同時に本ごとの容量を集計する。
        // 画像Blobは触らない（参照をそのまま残す）ので、ここでの負荷は小さい。
        if (oldVersion >= 1) {
          const textStore = tx.objectStore("pageText");
          const stats = new Map<string, { bytes: number; mime: string }>();
          let cursor = await tx.objectStore("pages").openCursor();
          while (cursor) {
            const p = cursor.value;
            const text = p.content ?? "";
            await textStore.put({
              id: p.id,
              bookId: p.bookId,
              pageNumber: p.pageNumber,
              text,
              lower: text.toLowerCase(),
            });
            const s = stats.get(p.bookId) ?? { bytes: 0, mime: p.image?.type || "" };
            s.bytes += p.image?.size ?? 0;
            stats.set(p.bookId, s);
            cursor = await cursor.continue();
          }
          const bookStore = tx.objectStore("books");
          for (const [bookId, s] of stats) {
            const book = await bookStore.get(bookId);
            if (book) {
              await bookStore.put({ ...book, imageBytes: s.bytes, imageMime: s.mime });
            }
          }
        }
      },
    });
  }
  return dbPromise;
}

function uuid(): string {
  // ブラウザ / iOS WebView (Safari) で利用可能
  return crypto.randomUUID();
}

// --- 状態（蔵書と端末容量） ------------------------------------

export async function getStatus(): Promise<LibraryStatus> {
  const db = await getDB();
  const books = await db.getAll("books");
  const pageCount = books.reduce((n, b) => n + (b.pageCount ?? 0), 0);
  const imageBytes = books.reduce((n, b) => n + (b.imageBytes ?? 0), 0);

  // ブラウザが対応していれば実際の使用量・上限を聞く（Safari など未対応環境では null）
  let usageBytes: number | null = null;
  let quotaBytes: number | null = null;
  try {
    if (typeof navigator !== "undefined" && navigator.storage?.estimate) {
      const est = await navigator.storage.estimate();
      usageBytes = est.usage ?? null;
      quotaBytes = est.quota ?? null;
    }
  } catch {
    /* 取れなくても表示を落とさない */
  }
  return { bookCount: books.length, pageCount, imageBytes, usageBytes, quotaBytes };
}

// --- 本の保存（取り込み） --------------------------------------

export interface NewPage {
  pageNumber: number;
  content: string;
  image: Blob;
}

/**
 * 1冊分（メタ＋全ページ）を1トランザクションで端末内に保存する。
 * **冊数の上限は無い**（2026-08-17に広告と枠制限を撤去した）。
 */
export async function saveBook(title: string, pages: NewPage[]): Promise<BookRecord> {
  const db = await getDB();
  const bookId = uuid();
  const book: BookRecord = {
    id: bookId,
    title,
    uploadedAt: Date.now(),
    pageCount: pages.length,
    imageBytes: pages.reduce((n, p) => n + (p.image?.size ?? 0), 0),
    imageMime: pages[0]?.image?.type || "",
  };

  const tx = db.transaction(["books", "pages", "pageText"], "readwrite");
  await tx.objectStore("books").put(book);
  const pageStore = tx.objectStore("pages");
  const textStore = tx.objectStore("pageText");
  for (const p of pages) {
    const id = uuid();
    // 画像は pages、テキストは pageText。**同じ本文を二重に持たない**
    await pageStore.put({ id, bookId, pageNumber: p.pageNumber, image: p.image });
    await textStore.put({
      id,
      bookId,
      pageNumber: p.pageNumber,
      text: p.content,
      lower: p.content.toLowerCase(),
    });
  }
  await tx.done;
  return book;
}

// --- 検索（端末内・複数語のAND） --------------------------------

/**
 * 空白区切りの語をすべて含むページを返す（AND検索・大文字小文字は無視）。
 * 画像を含まない `pageText` だけを走査するので、蔵書が増えても軽い。
 * @param bookId 指定するとその本の中だけを検索する
 */
export async function searchPages(
  query: string,
  opts: { bookId?: string; limit?: number } = {}
): Promise<SearchResult[]> {
  const terms = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (terms.length === 0) return [];
  const limit = opts.limit ?? SEARCH_LIMIT;

  const db = await getDB();
  const books = await db.getAll("books");
  const titleById = new Map(books.map((b) => [b.id, b.title]));

  const results: SearchResult[] = [];
  const tx = db.transaction("pageText");
  const store = tx.store;
  let cursor = opts.bookId
    ? await store.index("byBook").openCursor(opts.bookId)
    : await store.openCursor();

  while (cursor) {
    const p = cursor.value;
    if (p.lower && terms.every((t) => p.lower.includes(t))) {
      results.push({
        id: p.id,
        bookId: p.bookId,
        title: titleById.get(p.bookId) ?? "(無題)",
        pageNumber: p.pageNumber,
        content: p.text,
      });
      if (results.length >= limit) break;
    }
    cursor = await cursor.continue();
  }

  results.sort((a, b) =>
    a.title === b.title ? a.pageNumber - b.pageNumber : a.title.localeCompare(b.title)
  );
  return results;
}

// --- ページ画像の取得（ビューア用 objectURL） ------------------

export async function getPageImageUrl(pageId: string): Promise<string | null> {
  const db = await getDB();
  const page = await db.get("pages", pageId);
  if (!page?.image) return null;
  return URL.createObjectURL(page.image);
}

// --- 本の一覧 / 削除（端末の容量管理用） ------------------------

export async function listBooks(): Promise<BookRecord[]> {
  const db = await getDB();
  const books = await db.getAll("books");
  return books.sort((a, b) => b.uploadedAt - a.uploadedAt);
}

export async function deleteBook(bookId: string): Promise<void> {
  const db = await getDB();
  const tx = db.transaction(["books", "pages", "pageText"], "readwrite");
  await tx.objectStore("books").delete(bookId);
  for (const name of ["pages", "pageText"] as const) {
    const idx = tx.objectStore(name).index("byBook");
    let cursor = await idx.openCursor(bookId);
    while (cursor) {
      await cursor.delete();
      cursor = await cursor.continue();
    }
  }
  await tx.done;
}
