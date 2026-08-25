/**
 * 小説（カクヨム）の情報と、制作記録との対応。
 *
 * ここに書いた不具合が、そのまま小説の事件になっている。制作記録の詳細ページから
 * 作品へ送るための層。**続編は未投稿**なので、リンク先は公開済みの前作になる。
 */
import "server-only";

import { novelSchema, type Novel } from "@/lib/schema";
import { readJsonFile } from "./source";

export function getNovel(): Novel {
  return readJsonFile("novel.json", novelSchema);
}

/** 公開済みで、いちばん読ませたい作品（＝カクヨムの行き先） */
export function getReadableBook() {
  return getNovel().books.find((b) => b.status === "published" && b.url);
}

/** この制作記録が題材になった話。無ければ空 */
export function getEpisodesForWork(slug: string) {
  const novel = getNovel();
  return novel.episodes
    .filter((e) => e.work === slug)
    .map((e) => ({ ...e, book: novel.books.find((b) => b.slug === e.book) }))
    .filter((e) => e.book);
}
