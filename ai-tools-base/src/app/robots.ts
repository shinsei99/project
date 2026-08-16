/**
 * robots.txt（Next.js のファイル規約。`/robots.txt` として配信される）
 *
 * sitemap の場所をここで教える。これが無いと、クローラは全ページを
 * リンク伝いにしか見つけられない。
 */
import type { MetadataRoute } from "next";
import { SITE } from "@/lib/site";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/" },
    sitemap: `${SITE.url}/sitemap.xml`,
  };
}
