import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Container } from "@/components/ui/Container";
import { Badge } from "@/components/ui/Badge";
import { CoverArt } from "@/components/ui/CoverArt";
import { getArticle, getArticles } from "@/lib/content/articles";
import { getTool } from "@/lib/content/tools";
import { getPhoto } from "@/lib/content/photos";
import { renderMarkdown } from "@/lib/markdown";
import type { Article } from "@/lib/schema";

const KIND_LABELS: Record<Article["kind"], string> = {
  review: "レビュー",
  compare: "比較",
  howto: "使い方",
  feature: "特集",
  log: "制作記録",
};

/** ビルド時に全記事を静的生成する */
export function generateStaticParams() {
  return getArticles().map((a) => ({ slug: a.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const article = getArticle(slug);
  if (!article) return {};
  return { title: article.title, description: article.description };
}

export default async function ArticlePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const article = getArticle(slug);
  if (!article) notFound();

  const photo = getPhoto(article.slug);
  const html = renderMarkdown(article.body);
  // 関連ツールは slug 参照。存在しないslugが書かれていても落とさず無視する
  const relatedTools = article.tools.map((s) => getTool(s)).filter((t) => t !== undefined);

  return (
    <article className="py-12 sm:py-16">
      <Container className="max-w-3xl">
        <Link href="/articles" className="text-sm text-muted hover:text-fg">
          ← 記事一覧
        </Link>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <Badge tone="accent">{KIND_LABELS[article.kind]}</Badge>
          <time className="text-sm text-muted" dateTime={article.publishedAt}>
            {article.publishedAt}
          </time>
          {article.readingMinutes ? (
            <span className="text-sm text-muted">約{article.readingMinutes}分で読めます</span>
          ) : null}
        </div>

        <h1 className="mt-4 text-3xl font-bold leading-tight sm:text-4xl">{article.title}</h1>
        <p className="mt-4 text-lg text-muted">{article.description}</p>

        <CoverArt
          seed={article.slug}
          label={KIND_LABELS[article.kind]}
          image={photo?.src}
          className="mt-8 !h-56"
        />

        {/* 本文 */}
        <div
          className="prose prose-neutral dark:prose-invert mt-10 max-w-none"
          dangerouslySetInnerHTML={{ __html: html }}
        />

        {relatedTools.length > 0 ? (
          <aside className="mt-14 rounded-xl border border-border bg-surface-2 p-5">
            <h2 className="text-sm font-semibold">この記事で触れているツール</h2>
            <ul className="mt-3 space-y-2">
              {relatedTools.map((t) => (
                <li key={t.slug} className="text-sm">
                  <a
                    href={t.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-semibold underline-offset-4 hover:underline"
                  >
                    {t.name}
                  </a>
                  <span className="text-muted"> — {t.summary}</span>
                </li>
              ))}
            </ul>
          </aside>
        ) : null}
      </Container>
    </article>
  );
}
