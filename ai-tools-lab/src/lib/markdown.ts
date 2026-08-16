/**
 * 記事本文（MDXファイルのMarkdown部分）をHTMLにする。
 *
 * 中身は素のMarkdownしか使っていない（表・見出し・コード・引用）ので、
 * MDXランタイムは入れずに Markdown パーサだけで済ませている。
 * JSXコンポーネントを本文に埋め込みたくなったら、そのとき MDX へ移す。
 */
import "server-only";

import { marked } from "marked";

marked.setOptions({
  gfm: true, // 表・打ち消し線・自動リンク
  breaks: false,
});

export function renderMarkdown(body: string): string {
  return marked.parse(body, { async: false }) as string;
}
