import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { CoverArt } from "@/components/ui/CoverArt";
import { getPhoto } from "@/lib/content/photos";
import type { Article } from "@/lib/schema";

const KIND_LABELS: Record<Article["kind"], string> = {
  review: "レビュー",
  compare: "比較",
  howto: "使い方",
  feature: "特集",
  log: "制作記録",
};

export function ArticleCard({ article }: { article: Article }) {
  const photo = getPhoto(article.slug);
  return (
    <Card as="article" interactive className="flex h-full flex-col">
      <CoverArt
        seed={article.slug}
        label={KIND_LABELS[article.kind]}
        image={photo?.src}
        className="mb-4"
      />
      <div className="mb-3 flex items-center gap-2">
        <Badge tone={article.featured ? "accent" : "default"}>{KIND_LABELS[article.kind]}</Badge>
        <time className="text-xs text-muted" dateTime={article.publishedAt}>
          {article.publishedAt}
        </time>
        {article.readingMinutes ? (
          <span className="text-xs text-muted">約{article.readingMinutes}分</span>
        ) : null}
      </div>
      <h3 className="font-semibold leading-snug">
        <Link href={`/articles/${article.slug}`} className="hover:text-accent">
          {article.title}
        </Link>
      </h3>
      <p className="mt-2 flex-1 text-sm leading-relaxed text-muted">{article.description}</p>
    </Card>
  );
}
