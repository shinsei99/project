"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Search, Loader2 } from "lucide-react";
import { SearchResults } from "@/components/SearchResults";
import { listBooks, searchPages, type BookRecord } from "@/lib/db";
import type { SearchResult } from "@/lib/types";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [committed, setCommitted] = useState(""); // 実際に検索したキーワード
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [books, setBooks] = useState<BookRecord[]>([]);
  const [bookId, setBookId] = useState(""); // "" = すべての本
  const [elapsed, setElapsed] = useState<number | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 蔵書の一覧（絞り込み用）。`/search?book=<id>` で来たときは最初から絞る。
  // 静的書き出し（output: "export"）なので、クエリは window から読む
  useEffect(() => {
    listBooks().then(setBooks).catch(() => setBooks([]));
    const q = new URLSearchParams(window.location.search).get("book");
    if (q) setBookId(q);
  }, []);

  const doSearch = useCallback(async (q: string, book: string) => {
    const kw = q.trim();
    setCommitted(kw);
    if (!kw) {
      setResults([]);
      setSearched(false);
      setElapsed(null);
      return;
    }
    setLoading(true);
    setSearched(true);
    const t0 = performance.now();
    try {
      setResults(await searchPages(kw, book ? { bookId: book } : {}));
      setElapsed(Math.round(performance.now() - t0));
    } catch {
      setResults([]);
      setElapsed(null);
    } finally {
      setLoading(false);
    }
  }, []);

  // 入力のデバウンス検索（300ms）。本の絞り込みを変えたときも走らせる
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(query, bookId), 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, bookId, doSearch]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">書斎を検索</h1>
        <p className="mt-1 text-sm text-slate-400">
          保存済みの全ページから部分一致で探します。
          <strong className="text-slate-300">空白で区切ると、すべての語を含むページ</strong>
          （AND検索）だけが出ます。
        </p>
      </div>

      {/* 検索窓 */}
      <div className="relative">
        <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" />
        <input
          autoFocus
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="例: 契約 特約 ／ 減価償却 ／ 第3章"
          className="w-full rounded-xl border border-slate-700 bg-slate-900 py-3 pl-12 pr-4 text-base outline-none focus:border-sky-500"
        />
        {loading && (
          <Loader2 className="absolute right-4 top-1/2 h-5 w-5 -translate-y-1/2 animate-spin text-slate-400" />
        )}
      </div>

      {/* 本で絞り込み */}
      {books.length > 1 && (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <label htmlFor="bookFilter" className="text-slate-400">
            対象の本
          </label>
          <select
            id="bookFilter"
            value={bookId}
            onChange={(e) => setBookId(e.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 outline-none focus:border-sky-500"
          >
            <option value="">すべての本（{books.length}冊）</option>
            {books.map((b) => (
              <option key={b.id} value={b.id}>
                {b.title}（{b.pageCount}ページ）
              </option>
            ))}
          </select>
        </div>
      )}

      {/* 結果 */}
      {committed && !loading && (
        <p className="text-sm text-slate-400">
          「{committed}」の検索結果：{results.length} 件
          {elapsed !== null && <span className="text-slate-500">（{elapsed}ms）</span>}
        </p>
      )}

      <SearchResults
        results={results}
        keyword={committed}
        onSelect={(r) => {
          // ヒットしたページから**本として読み始める**（前後のページへ移動できる）
          const q = new URLSearchParams({ book: r.bookId, page: String(r.pageNumber), q: committed });
          window.location.href = `/read?${q.toString()}`;
        }}
      />

      {searched && !loading && results.length === 0 && committed && (
        <p className="py-10 text-center text-sm text-slate-500">
          一致するページが見つかりませんでした。
          {committed.includes(" ") && "（AND検索です。語を減らすと見つかることがあります）"}
        </p>
      )}

    </div>
  );
}
