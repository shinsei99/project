export interface SearchResult {
  id: string; // page id
  bookId: string;
  title: string;
  pageNumber: number;
  content: string;
}

/** 蔵書と端末容量の状況（本棚メーターの表示に使う） */
export interface LibraryStatus {
  bookCount: number;
  pageCount: number;
  /** ページ画像の合計バイト数（本ごとに保存時に記録した値の合計） */
  imageBytes: number;
  /** ブラウザが報告する使用量・上限。取れない環境では null */
  usageBytes: number | null;
  quotaBytes: number | null;
}
