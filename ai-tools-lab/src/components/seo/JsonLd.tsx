/**
 * 構造化データ（JSON-LD）。検索結果でパンくずや記事情報として扱われやすくなる。
 *
 * **`dangerouslySetInnerHTML` を使うのはここだけに閉じ込める。**
 * 値は自前のコンテンツ（`content/`）由来だが、`<` を含む文字列が入ると
 * スクリプトタグが閉じてしまうため、必ずエスケープしてから埋める。
 */
export function JsonLd({ data }: { data: Record<string, unknown> }) {
  const json = JSON.stringify(data).replace(/</g, "\\u003c");
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: json }} />;
}

/** パンくず。`items` は上位→下位の順（末尾が現在地） */
export function breadcrumb(base: string, items: { name: string; path: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((it, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: it.name,
      item: `${base}${it.path}`,
    })),
  };
}
