"use client";

import { openDB, type DBSchema, type IDBPDatabase } from "idb";
import { SEARCH_LIMIT } from "@/lib/constants";
import type { BookSource, LibraryStatus, SearchResult, StorageState } from "@/lib/types";

// ============================================================
// 端末内データベース（IndexedDB）
// データは端末の中だけに保存され、外部サーバーへは一切送信しない。
//
// v3（2026-08-17）の考え方 ─ **軽い索引を持ち歩き、重い原本は置いてくる。**
//   取り込みでは**本文テキストだけ**を保存する（1ページ1msで済む）。
//   ページ画像は**見たときにその場で作って `pageImage` に貯める**（60〜110ms/枚）。
//   原本PDFは Dropbox 等に置いたままで、必要なときだけ選び直す。
//
//   v1 … pages にテキストと画像が同居（検索のたびに画像ごと全件走査していた）
//   v2 … pageText を分離して検索を軽くした（画像は取り込み時に全ページ作成）
//   v3 … 画像は「見たページだけ」。books に原本の目印とキャッシュ量を持たせた
// ============================================================

export interface BookRecord {
  id: string;
  title: string;
  uploadedAt: number;
  pageCount: number;
  /** 本文の合計文字数（索引の重さ・未OCRの判定に使う） */
  textChars: number;
  /** 原本PDFの目印。選び直したときに同じ本かを照合する */
  source?: BookSource;
  /** キャッシュ済みのページ画像の枚数と容量（表示と掃除のため） */
  cachedPages?: number;
  cachedBytes?: number;
  /** 本文の読みやすさ（0〜1）。ひらがな率から出した目安。低い本は画像で読む方が良い */
  quality?: number;
  /** 縦書きなどで組み直したページの割合 */
  rebuiltRatio?: number;
  /** しおり（最後に読んでいたページ） */
  lastReadPage?: number;
  /**
   * 同梱の収録作品なら、`public/books/` の中のファイル名。
   * 原本がアプリの中にあるので、紙面表示のときに選び直してもらう必要がない。
   */
  bundled?: string;
}

/** 表紙（1ページ目）のサムネイル。取り込み時に作る唯一の画像 */
export interface CoverRecord {
  bookId: string;
  bytes: ArrayBuffer;
  mime: string;
  width: number;
  height: number;
}

/** 検索用の軽いレコード（画像を含まない） */
export interface PageTextRecord {
  id: string;
  bookId: string;
  pageNumber: number;
  text: string;
  /** 小文字化済みの本文。検索のたびに toLowerCase() をやり直さないために持つ */
  lower: string;
}

/**
 * 見たページの画像キャッシュ。
 * **中身は ArrayBuffer で持つ。** Safari の IndexedDB は Blob の扱いに癖があるため、
 * 素の bytes ＋ mime に分けておくのが安全（表示するときに Blob へ戻す）。
 */
export interface PageImageRecord {
  id: string; // pageText と同じ id
  bookId: string;
  pageNumber: number;
  bytes: ArrayBuffer;
  mime: string;
  width: number;
  height: number;
  cachedAt: number;
}

interface ShosaiDB extends DBSchema {
  books: { key: string; value: BookRecord };
  pageText: { key: string; value: PageTextRecord; indexes: { byBook: string } };
  pageImage: { key: string; value: PageImageRecord; indexes: { byBook: string } };
  cover: { key: string; value: CoverRecord };
}

const DB_NAME = "digital-shosai";
const DB_VERSION = 4;

let dbPromise: Promise<IDBPDatabase<ShosaiDB>> | null = null;

function getDB() {
  if (!dbPromise) {
    dbPromise = openDB<ShosaiDB>(DB_NAME, DB_VERSION, {
      async upgrade(db, oldVersion, _newVersion, tx) {
        const names: DOMStringList = db.objectStoreNames;

        if (!names.contains("books")) db.createObjectStore("books", { keyPath: "id" });
        if (!names.contains("pageText")) {
          db.createObjectStore("pageText", { keyPath: "id" }).createIndex("byBook", "bookId");
        }
        if (!names.contains("pageImage")) {
          db.createObjectStore("pageImage", { keyPath: "id" }).createIndex("byBook", "bookId");
        }
        // v4: 表紙（本棚に並べる）
        if (!names.contains("cover")) db.createObjectStore("cover", { keyPath: "bookId" });
        // 広告（動画リワードで枠+1）をやめたので、その保存先も捨てる
        if (names.contains("profile")) (db as unknown as IDBDatabase).deleteObjectStore("profile");

        // v1 のデータ移行: pages に同居していた本文を pageText へ写す
        if (oldVersion === 1 && names.contains("pages")) {
          const textStore = tx.objectStore("pageText");
          let cur = await (tx as any).objectStore("pages").openCursor();
          while (cur) {
            const p = cur.value as { id: string; bookId: string; pageNumber: number; content?: string };
            const text = p.content ?? "";
            await textStore.put({
              id: p.id, bookId: p.bookId, pageNumber: p.pageNumber, text, lower: text.toLowerCase(),
            });
            cur = await cur.continue();
          }
        }

        // v1/v2 の画像（全ページ分）を pageImage へ移し、古い pages ストアは捨てる。
        // **ここでは Blob をそのまま入れる**（upgrade の中で読み出せないため）。
        // 読み出し側が Blob と ArrayBuffer の両方を受けられるようにしてある。
        if (oldVersion < 4 && names.contains("pages")) {
          const imgStore = tx.objectStore("pageImage");
          let cur = await (tx as any).objectStore("pages").openCursor();
          while (cur) {
            const p = cur.value as { id: string; bookId: string; pageNumber: number; image?: Blob };
            if (p.image) {
              await imgStore.put({
                id: p.id, bookId: p.bookId, pageNumber: p.pageNumber,
                bytes: p.image as unknown as ArrayBuffer, // 旧データは Blob のまま
                mime: p.image.type || "image/png",
                width: 0, height: 0, cachedAt: Date.now(),
              });
            }
            cur = await cur.continue();
          }
          (db as unknown as IDBDatabase).deleteObjectStore("pages");
        }
      },
    });
  }
  return dbPromise;
}

function uuid(): string {
  return crypto.randomUUID();
}

// --- 保存できる状態かの確認（プライベートブラウズ等の検知） ------
//
// **無言で失敗させない。** Safari のプライベートタブでは IndexedDB への書き込みが
// エラー内容 null のまま失敗し、上限も 1000MB と小さく申告される（2026-08-17 実機で確認）。
// 起動時に1KBだけ書いて判定し、駄目なら画面に理由を出す。

export async function probeStorage(): Promise<StorageState> {
  let quotaBytes: number | null = null;
  try {
    if (typeof navigator !== "undefined" && navigator.storage?.estimate) {
      quotaBytes = (await navigator.storage.estimate()).quota ?? null;
    }
  } catch {
    /* 取れなくても続ける */
  }
  const name = "digital-shosai-probe";
  try {
    const db = await new Promise<IDBDatabase>((res, rej) => {
      const r = indexedDB.open(name, 1);
      r.onupgradeneeded = () => r.result.createObjectStore("s");
      r.onsuccess = () => res(r.result);
      r.onerror = () => rej(r.error ?? new Error("データベースを開けませんでした"));
      setTimeout(() => rej(new Error("応答がありません")), 8000);
    });
    await new Promise<void>((res, rej) => {
      const tx = db.transaction("s", "readwrite");
      tx.objectStore("s").put(new Uint8Array(1024).buffer, "k");
      tx.oncomplete = () => res();
      tx.onabort = () => rej(tx.error ?? new Error("書き込みが中断されました"));
      tx.onerror = () => rej(tx.error ?? new Error("書き込みに失敗しました"));
    });
    db.close();
    indexedDB.deleteDatabase(name);
    return { writable: true, quotaBytes };
  } catch (e: any) {
    try { indexedDB.deleteDatabase(name); } catch { /* noop */ }
    const detail = e?.name ? `${e.name}: ${e.message ?? ""}` : String(e?.message ?? e ?? "原因不明");
    return {
      writable: false,
      quotaBytes,
      reason:
        "この状態では端末に保存できません（" + detail + "）。" +
        "プライベートブラウズを使っていませんか。通常のタブで開くか、ホーム画面に追加したアイコンから開いてください。",
    };
  }
}

/** ブラウザに「勝手に消さないで」と頼む（対応していない環境では何もしない） */
export async function requestPersistence(): Promise<boolean> {
  try {
    if (navigator.storage?.persist) return await navigator.storage.persist();
  } catch {
    /* noop */
  }
  return false;
}

// --- 状態（蔵書と容量） ----------------------------------------

export async function getStatus(): Promise<LibraryStatus> {
  const db = await getDB();
  const books = await db.getAll("books");
  const sum = (f: (b: BookRecord) => number) => books.reduce((n, b) => n + f(b), 0);

  let usageBytes: number | null = null;
  let quotaBytes: number | null = null;
  try {
    if (navigator.storage?.estimate) {
      const est = await navigator.storage.estimate();
      usageBytes = est.usage ?? null;
      quotaBytes = est.quota ?? null;
    }
  } catch {
    /* noop */
  }
  return {
    bookCount: books.length,
    pageCount: sum((b) => b.pageCount ?? 0),
    textChars: sum((b) => b.textChars ?? 0),
    cachedPages: sum((b) => b.cachedPages ?? 0),
    cachedBytes: sum((b) => b.cachedBytes ?? 0),
    usageBytes,
    quotaBytes,
  };
}

// --- 索引の保存（取り込み。画像は作らない） ---------------------

export interface NewPageText {
  pageNumber: number;
  text: string;
}

/** 同じ原本がもう入っていないか（名前とサイズで照合） */
export async function findBookBySource(source: BookSource): Promise<BookRecord | null> {
  const db = await getDB();
  const books = await db.getAll("books");
  return (
    books.find(
      (b) => b.source && b.source.fileName === source.fileName && b.source.fileSize === source.fileSize
    ) ?? null
  );
}

export async function saveIndex(
  title: string,
  pages: NewPageText[],
  source: BookSource,
  meta: { quality?: number; rebuiltRatio?: number; bundled?: string } = {}
): Promise<BookRecord> {
  const db = await getDB();
  const bookId = uuid();
  const book: BookRecord = {
    id: bookId,
    title,
    uploadedAt: Date.now(),
    pageCount: pages.length,
    textChars: pages.reduce((n, p) => n + p.text.length, 0),
    source,
    cachedPages: 0,
    cachedBytes: 0,
    quality: meta.quality,
    rebuiltRatio: meta.rebuiltRatio,
    lastReadPage: 1,
    bundled: meta.bundled,
  };

  const tx = db.transaction(["books", "pageText"], "readwrite");
  await tx.objectStore("books").put(book);
  const textStore = tx.objectStore("pageText");
  for (const p of pages) {
    await textStore.put({
      id: uuid(),
      bookId,
      pageNumber: p.pageNumber,
      text: p.text,
      lower: p.text.toLowerCase(),
    });
  }
  await tx.done;
  return book;
}

/** 原本を選び直したときに目印を更新する */
export async function relinkSource(bookId: string, source: BookSource): Promise<void> {
  const db = await getDB();
  const book = await db.get("books", bookId);
  if (book) await db.put("books", { ...book, source });
}

// --- 検索（複数語のAND・端末内） --------------------------------

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
  const store = db.transaction("pageText").store;
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

// --- ページ画像のキャッシュ（見たページだけ） -------------------

/** キャッシュ済みの画像を objectURL で返す（無ければ null） */
export async function getCachedImageUrl(pageId: string): Promise<string | null> {
  const db = await getDB();
  const rec = await db.get("pageImage", pageId);
  if (!rec) return null;
  // 旧データ（v1/v2 から移した Blob）と新データ（ArrayBuffer）の両方を受ける
  const blob =
    rec.bytes instanceof Blob ? rec.bytes : new Blob([rec.bytes], { type: rec.mime || "image/png" });
  return URL.createObjectURL(blob);
}

export async function cacheImage(
  pageId: string,
  bookId: string,
  pageNumber: number,
  blob: Blob,
  size: { width: number; height: number }
): Promise<void> {
  const db = await getDB();
  const bytes = await blob.arrayBuffer();
  const tx = db.transaction(["pageImage", "books"], "readwrite");
  const store = tx.objectStore("pageImage");
  const already = await store.get(pageId);
  await store.put({
    id: pageId,
    bookId,
    pageNumber,
    bytes,
    mime: blob.type || "image/png",
    width: size.width,
    height: size.height,
    cachedAt: Date.now(),
  });
  const books = tx.objectStore("books");
  const book = await books.get(bookId);
  if (book) {
    const prevBytes = already
      ? (already.bytes instanceof Blob ? already.bytes.size : already.bytes.byteLength)
      : 0;
    await books.put({
      ...book,
      cachedPages: (book.cachedPages ?? 0) + (already ? 0 : 1),
      cachedBytes: Math.max(0, (book.cachedBytes ?? 0) - prevBytes + bytes.byteLength),
    });
  }
  await tx.done;
}

/** その本のページ画像キャッシュだけを消す（索引と検索は残る） */
export async function clearImageCache(bookId: string): Promise<void> {
  const db = await getDB();
  const tx = db.transaction(["pageImage", "books"], "readwrite");
  const idx = tx.objectStore("pageImage").index("byBook");
  let cursor = await idx.openCursor(bookId);
  while (cursor) {
    await cursor.delete();
    cursor = await cursor.continue();
  }
  const books = tx.objectStore("books");
  const book = await books.get(bookId);
  if (book) await books.put({ ...book, cachedPages: 0, cachedBytes: 0 });
  await tx.done;
}

// --- 本の一覧 / 削除 -------------------------------------------

export async function listBooks(): Promise<BookRecord[]> {
  const db = await getDB();
  const books = await db.getAll("books");
  return books.sort((a, b) => b.uploadedAt - a.uploadedAt);
}

export async function getBook(bookId: string): Promise<BookRecord | undefined> {
  const db = await getDB();
  return db.get("books", bookId);
}

export async function deleteBook(bookId: string): Promise<void> {
  const db = await getDB();
  const tx = db.transaction(["books", "pageText", "pageImage", "cover"], "readwrite");
  await tx.objectStore("books").delete(bookId);
  await tx.objectStore("cover").delete(bookId);
  for (const name of ["pageText", "pageImage"] as const) {
    const idx = tx.objectStore(name).index("byBook");
    let cursor = await idx.openCursor(bookId);
    while (cursor) {
      await cursor.delete();
      cursor = await cursor.continue();
    }
  }
  await tx.done;
}

// --- 表紙（本棚用） --------------------------------------------

export async function setCover(bookId: string, blob: Blob, size: { width: number; height: number }) {
  const db = await getDB();
  await db.put("cover", {
    bookId,
    bytes: await blob.arrayBuffer(),
    mime: blob.type || "image/png",
    width: size.width,
    height: size.height,
  });
}

/** 本棚に並べるための表紙URL（無ければ null）。**画像は端末内から作る** */
export async function getCoverUrl(bookId: string): Promise<string | null> {
  const db = await getDB();
  const rec = await db.get("cover", bookId);
  if (!rec) return null;
  const blob = rec.bytes instanceof Blob ? rec.bytes : new Blob([rec.bytes], { type: rec.mime });
  return URL.createObjectURL(blob);
}

// --- しおり（最後に読んだページ） -------------------------------

export async function setLastRead(bookId: string, pageNumber: number) {
  const db = await getDB();
  const book = await db.get("books", bookId);
  if (book && book.lastReadPage !== pageNumber) {
    await db.put("books", { ...book, lastReadPage: pageNumber });
  }
}

// --- 読書用のページ取得 ----------------------------------------

export interface ReadPage { id: string; pageNumber: number; text: string }

/** その本の指定ページ（前後の移動に使う。テキストだけなので軽い） */
export async function getPage(bookId: string, pageNumber: number): Promise<ReadPage | null> {
  const db = await getDB();
  const all = await db.getAllFromIndex("pageText", "byBook", bookId);
  const hit = all.find((p) => p.pageNumber === pageNumber);
  return hit ? { id: hit.id, pageNumber: hit.pageNumber, text: hit.text } : null;
}

/** その本の全ページ（連続して読むときに使う。1冊分の本文なら数百KB） */
export async function getBookPages(bookId: string): Promise<ReadPage[]> {
  const db = await getDB();
  const all = await db.getAllFromIndex("pageText", "byBook", bookId);
  return all
    .sort((a, b) => a.pageNumber - b.pageNumber)
    .map((p) => ({ id: p.id, pageNumber: p.pageNumber, text: p.text }));
}

// --- 書き出し / 読み込み（バックアップと端末間の受け渡し） ------

export async function exportPayload(): Promise<{
  version: 3;
  exportedAt: number;
  books: BookRecord[];
  pageText: PageTextRecord[];
}> {
  const db = await getDB();
  const [books, pageText] = await Promise.all([db.getAll("books"), db.getAll("pageText")]);
  // 画像キャッシュは**入れない**（見れば作り直せるものなので、受け渡しを軽くする）
  return { version: 3, exportedAt: Date.now(), books, pageText };
}

export interface ImportResult {
  added: number;
  skipped: number;
  pages: number;
}

/** 書き出したものを取り込む。**同じ原本の本は飛ばす**（重複を作らない） */
export async function importPayload(payload: any): Promise<ImportResult> {
  if (!payload || !Array.isArray(payload.books) || !Array.isArray(payload.pageText)) {
    throw new Error("この形式のファイルは読み込めません（書斎の書き出しファイルを選んでください）");
  }
  const db = await getDB();
  const existing = await db.getAll("books");
  const key = (b: any) => (b.source ? b.source.fileName + "|" + b.source.fileSize : b.title);
  const have = new Set(existing.map(key));

  const byBook = new Map<string, PageTextRecord[]>();
  for (const t of payload.pageText as PageTextRecord[]) {
    if (!byBook.has(t.bookId)) byBook.set(t.bookId, []);
    byBook.get(t.bookId)!.push(t);
  }

  let added = 0, skipped = 0, pages = 0;
  for (const book of payload.books as BookRecord[]) {
    if (have.has(key(book))) { skipped++; continue; }
    const tx = db.transaction(["books", "pageText"], "readwrite");
    await tx.objectStore("books").put({ ...book, cachedPages: 0, cachedBytes: 0 });
    const textStore = tx.objectStore("pageText");
    for (const t of byBook.get(book.id) ?? []) {
      await textStore.put({ ...t, lower: t.lower ?? (t.text ?? "").toLowerCase() });
      pages++;
    }
    await tx.done;
    added++;
  }
  return { added, skipped, pages };
}
