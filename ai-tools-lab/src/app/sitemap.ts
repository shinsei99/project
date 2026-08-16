/**
 * sitemap.xml（Next.js のファイル規約。`/sitemap.xml` として配信される）
 *
 * 手で列挙するとページを足したときに必ず漏れるので、**コンテンツ層から生成する**。
 * `getWorks()` は public しか返さないため、非公開の記録がここに漏れることはない。
 */
import type { MetadataRoute } from "next";
import { SITE } from "@/lib/site";
import { getWorks } from "@/lib/content/works";
import { getTools } from "@/lib/content/tools";
import { getArticles } from "@/lib/content/articles";

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  const fixed = ["", "/tools", "/works", "/articles", "/history"].map((p) => ({
    url: `${SITE.url}${p}`,
    lastModified: now,
    changeFrequency: "weekly" as const,
    priority: p === "" ? 1 : 0.8,
  }));

  const works = getWorks().map((w) => ({
    url: `${SITE.url}/works/${w.slug}`,
    lastModified: now,
    changeFrequency: "monthly" as const,
    priority: 0.7,
  }));

  const tools = getTools().map((t) => ({
    url: `${SITE.url}/tools/${t.slug}`,
    lastModified: now,
    changeFrequency: "monthly" as const,
    priority: 0.6,
  }));

  const articles = getArticles().map((a) => ({
    url: `${SITE.url}/articles/${a.slug}`,
    lastModified: new Date(a.updatedAt ?? a.publishedAt),
    changeFrequency: "monthly" as const,
    priority: 0.6,
  }));

  return [...fixed, ...works, ...tools, ...articles];
}
