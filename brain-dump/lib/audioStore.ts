/**
 * 録音した音声の「元データ」をブラウザ内に保存するための IndexedDB ラッパー。
 *
 * 音声は 1 本で数 MB になるため、履歴メタデータを置く localStorage には入れず、
 * 容量の大きい IndexedDB に本体（ArrayBuffer）だけを保存する。
 * localStorage 側の履歴には音声 id（と長さ・MIME）だけを持たせて紐付ける。
 *
 * ArrayBuffer で保存するのは、一部の古い iOS Safari で Blob を IndexedDB に
 * 入れると読み出せなくなる不具合を避けるため（読み出し時に Blob へ復元する）。
 */

const DB_NAME = "bd_audio";
const STORE = "clips";
const VERSION = 1;

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("IndexedDB が使えません"));
      return;
    }
    const req = indexedDB.open(DB_NAME, VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE);
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error ?? new Error("IndexedDB を開けません"));
  });
}

/** 音声本体（ArrayBuffer）を id で保存する。 */
export async function putAudio(id: string, buf: ArrayBuffer): Promise<void> {
  const db = await openDB();
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE, "readwrite");
      tx.objectStore(STORE).put(buf, id);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error);
    });
  } finally {
    db.close();
  }
}

/** 保存済みの音声本体を取り出す。無ければ null。 */
export async function getAudio(id: string): Promise<ArrayBuffer | null> {
  const db = await openDB();
  try {
    return await new Promise<ArrayBuffer | null>((resolve, reject) => {
      const tx = db.transaction(STORE, "readonly");
      const r = tx.objectStore(STORE).get(id);
      r.onsuccess = () => resolve((r.result as ArrayBuffer) ?? null);
      r.onerror = () => reject(r.error);
    });
  } finally {
    db.close();
  }
}

/** 指定した id 群の音声を削除する（履歴からの削除に合わせて呼ぶ）。 */
export async function deleteAudio(ids: string[]): Promise<void> {
  if (ids.length === 0) return;
  const db = await openDB();
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE, "readwrite");
      const store = tx.objectStore(STORE);
      for (const id of ids) store.delete(id);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error);
    });
  } finally {
    db.close();
  }
}
