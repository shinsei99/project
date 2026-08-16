/** 記事の取得。下書き（draft）は本番で出さない */
import "server-only";

import { articleSchema, type Article } from "@/lib/schema";
import { readMdxFrontmatter } from "./source";

export type ArticleWithBody = Article & { body: string };

export function getArticles(): ArticleWithBody[] {
  const isProd = process.env.NODE_ENV === "production";
  return readMdxFrontmatter("articles", articleSchema)
    .filter((a) => !(isProd && a.draft))
    .sort((a, b) => b.publishedAt.localeCompare(a.publishedAt));
}

export function getFeaturedArticles(limit = 3): ArticleWithBody[] {
  const all = getArticles();
  const featured = all.filter((a) => a.featured);
  // イチオシが足りないときは新着で埋める（トップの枠が歯抜けにならないように）
  return [...featured, ...all.filter((a) => !a.featured)].slice(0, limit);
}

export function getArticle(slug: string): ArticleWithBody | undefined {
  return getArticles().find((a) => a.slug === slug);
}
