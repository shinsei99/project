"use client";

// そのセッションのあいだだけ、選んだ原本PDFを覚えておく置き場。
//
// **原本は端末に保存しない**（Dropbox等に置いたままにするのが設計の要）。
// ただしアプリを開いているあいだは、同じ本のページを続けて見ることが多いので、
// 一度選んだ File をここに持っておく。タブを閉じれば消える。
//
// ブラウザには「次回も同じファイルを読む」権限を残す方法が無い（iOSは特に無い）。
// アプリ版（Capacitor）では iOS のブックマークで場所を記憶できるので、
// そのときはここを差し替える。

const files = new Map<string, File>();

export function remember(bookId: string, file: File) {
  files.set(bookId, file);
}

export function recall(bookId: string): File | null {
  return files.get(bookId) ?? null;
}

export function forget(bookId: string) {
  files.delete(bookId);
}

export function knownBookIds(): string[] {
  return [...files.keys()];
}
