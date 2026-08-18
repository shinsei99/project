export interface SearchResult {
  id: string; // page id
  bookId: string;
  title: string;
  pageNumber: number;
  content: string;
}

/** 原本PDFの目印。同じ本かどうかを照合するために持つ（中身は保存しない） */
export interface BookSource {
  fileName: string;
  fileSize: number;
  lastModified: number;
}

/** 蔵書と端末容量の状況 */
export interface LibraryStatus {
  bookCount: number;
  pageCount: number;
  /** 本文テキストの合計文字数（索引の重さの目安） */
  textChars: number;
  /** キャッシュしたページ画像の枚数と合計バイト数 */
  cachedPages: number;
  cachedBytes: number;
  /** ブラウザが報告する使用量・上限。取れない環境では null */
  usageBytes: number | null;
  quotaBytes: number | null;
}

/** 保存できる状態かどうか（プライベートブラウズ等の検知結果） */
export interface StorageState {
  writable: boolean;
  /** 書けなかったときの理由（画面にそのまま出す） */
  reason?: string;
  quotaBytes: number | null;
}
