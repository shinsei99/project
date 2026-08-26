import Link from "next/link";
import { getNovel } from "@/lib/content/novel";

/**
 * フッターに置く小説への導線。**全ページに出る**。
 *
 * 公開前は `/novel`（サイト内の紹介）へ、カクヨムに出したら作品ページへ直接送る。
 * 切り替えは `content/novel.json` の `url` を入れるだけで、ここは触らなくてよい。
 */
export function NovelLink() {
  const book = getNovel().books[0];
  if (!book) return null;
  return (
    <p className="text-sm">
      <span className="text-muted">ここに書いた不具合が、そのまま事件になっている小説があります —</span>{" "}
      {book.url ? (
        <a
          href={book.url}
          target="_blank"
          rel="noopener noreferrer"
          className="font-semibold text-accent hover:underline"
        >
          『{book.title}』をカクヨムで読む ↗
        </a>
      ) : (
        <Link href="/novel" className="font-semibold text-accent hover:underline">
          『{book.title}』について →
        </Link>
      )}
    </p>
  );
}
