import type { Metadata } from "next";
import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { Badge } from "@/components/ui/Badge";
import { getNovel } from "@/lib/content/novel";
import { getWorks } from "@/lib/content/works";

export const metadata: Metadata = {
  title: "小説「不動産屋、つくってます。」",
  description:
    "このサイトの制作記録に書いた不具合が、そのまま事件になっている小説。全32話のうち、どの話がどの記録から生まれたかの対応表。",
  alternates: { canonical: "/novel" },
};

export default function NovelPage() {
  const novel = getNovel();
  const book = novel.books[0];
  const works = new Map(getWorks().map((w) => [w.slug, w]));

  // 話の番号順に並べ、同じ話に複数の記録がぶら下がる形にまとめる
  const byEpisode = new Map<number, { title: string; items: { work: string; note: string }[] }>();
  for (const e of novel.episodes) {
    const row = byEpisode.get(e.no) ?? { title: e.title, items: [] };
    row.items.push({ work: e.work, note: e.note });
    byEpisode.set(e.no, row);
  }
  const episodes = [...byEpisode.entries()].sort((a, b) => a[0] - b[0]);

  return (
    <div className="py-12">
      <Container className="max-w-3xl">
        <Badge tone={book.url ? "accent" : "outline"}>
          {book.url ? "カクヨムで公開中" : "公開準備中"}
        </Badge>

        <h1 className="mt-4 text-3xl font-bold leading-tight sm:text-4xl">{book.title}</h1>
        <p className="mt-4 text-lg text-muted">{book.lead}</p>
        <p className="mt-4 leading-relaxed">{book.summary}</p>

        {book.url ? (
          <a
            href={book.url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-6 inline-block rounded-lg bg-accent px-5 py-3 font-semibold text-bg"
          >
            カクヨムで読む ↗
          </a>
        ) : (
          <p className="mt-6 rounded-xl border border-border bg-surface p-4 text-sm text-muted">
            全{book.episodes}話・脱稿済み。公開したら、ここから読めるようにします。
          </p>
        )}

        <h2 className="mt-12 text-xl font-bold">どの記録が、どの話になったか</h2>
        <p className="mt-2 text-sm text-muted">
          事件は作っていません。ここに並ぶ記録は、実際に起きて、実際に直したものです。
          固有名詞と数字だけ、物語の側に移し替えてあります。
        </p>

        <ul className="mt-6 space-y-4">
          {episodes.map(([no, row]) => (
            <li key={no} className="rounded-xl border border-border bg-surface p-4">
              <p className="text-sm font-semibold">
                第{no}話「{row.title}」
              </p>
              <ul className="mt-2 space-y-1.5">
                {row.items.map((it) => {
                  const w = works.get(it.work);
                  return (
                    <li key={it.work} className="text-sm">
                      {w ? (
                        <Link href={`/works/${w.slug}`} className="font-semibold text-accent hover:underline">
                          {w.name}
                        </Link>
                      ) : (
                        <span className="font-semibold">{it.work}</span>
                      )}
                      <span className="ml-2 text-muted">{it.note}</span>
                    </li>
                  );
                })}
              </ul>
            </li>
          ))}
        </ul>

        <p className="mt-10 text-sm text-muted">
          全{book.episodes}話のうち、いま制作記録と結びついているのは{episodes.length}話です。
          記録が増えるたびに、この表も伸びます。
        </p>
      </Container>
    </div>
  );
}
