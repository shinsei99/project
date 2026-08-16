/**
 * 制作記録（ビルドログ）の取得。
 *
 * **`getWorks()` は `visibility: "public"` しか返さない。** これは表示側の都合ではなく
 * 安全装置なので、`internal` を通す関数をここに足さないこと。
 * `internal` は本数を数えるためだけに `getWorkStats()` で使う。
 */
import "server-only";

import { workSchema, type Work } from "@/lib/schema";
import { readJsonCollection } from "./source";

/** 公開してよいものだけ。新しい年が上 */
export function getWorks(): Work[] {
  return readJsonCollection("works", workSchema)
    .filter((w) => w.visibility === "public")
    .sort((a, b) => b.year - a.year || a.name.localeCompare(b.name));
}

export function getFeaturedWorks(limit = 3): Work[] {
  const all = getWorks();
  return [...all.filter((w) => w.featured), ...all.filter((w) => !w.featured)].slice(0, limit);
}

export function getWork(slug: string): Work | undefined {
  return getWorks().find((w) => w.slug === slug);
}

/**
 * 実績の規模を数字で出すための集計。
 * `internal` は**本数にだけ**数える（名前も中身も外へ出さない）。
 */
export function getWorkStats() {
  const all = readJsonCollection("works", workSchema);
  const published = all.filter((w) => w.visibility === "public");
  return {
    total: all.length,
    published: published.length,
    internal: all.length - published.length,
    prompts: published.reduce((n, w) => n + w.prompts.length, 0),
    improvements: published.reduce((n, w) => n + w.improvements.length, 0),
  };
}
