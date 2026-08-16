/**
 * RSS（`/feed.xml`）。Zenn / note から来た人が**継続して追える口**を用意する。
 *
 * 記事と制作記録を1本のフィードにまとめる（分けるほどの本数ではない）。
 * `getWorks()` は公開ぶんしか返さないので、社内向けの記録が混ざることはない。
 */
import { SITE } from "@/lib/site";
import { getArticles } from "@/lib/content/articles";
import { getWorks } from "@/lib/content/works";

/** XMLに入れてはいけない文字を落とす */
function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function GET() {
  const items = [
    ...getArticles().map((a) => ({
      title: a.title,
      desc: a.description,
      url: `${SITE.url}/articles/${a.slug}`,
      date: new Date(a.updatedAt ?? a.publishedAt),
    })),
    ...getWorks().map((w) => ({
      title: w.name,
      desc: w.summary,
      url: `${SITE.url}/works/${w.slug}`,
      // 制作記録は日付を持たないので年だけ使う（順序の安定のため）
      date: new Date(`${w.year}-01-01`),
    })),
  ].sort((a, b) => b.date.getTime() - a.date.getTime());

  const body = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>${esc(SITE.name)}</title>
<link>${SITE.url}</link>
<description>${esc(SITE.description)}</description>
<language>ja</language>
${items
  .map(
    (it) => `<item>
<title>${esc(it.title)}</title>
<link>${it.url}</link>
<guid isPermaLink="true">${it.url}</guid>
<pubDate>${it.date.toUTCString()}</pubDate>
<description>${esc(it.desc)}</description>
</item>`,
  )
  .join("\n")}
</channel></rss>`;

  return new Response(body, {
    headers: { "content-type": "application/rss+xml; charset=utf-8" },
  });
}
