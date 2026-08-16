import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Container } from "@/components/ui/Container";
import { Badge } from "@/components/ui/Badge";
import { getTool, getTools } from "@/lib/content/tools";
import { getArticles } from "@/lib/content/articles";
import { overallScore } from "@/lib/schema";
import { JsonLd, breadcrumb } from "@/components/seo/JsonLd";
import { SITE } from "@/lib/site";

const SCORE_LABELS: Record<string, string> = {
  autonomy: "自律性（どこまで任せられるか）",
  codeQuality: "出力の質",
  costEfficiency: "費用対効果",
  learningCurve: "習得しやすさ",
  japanese: "日本語の扱い",
};

export function generateStaticParams() {
  return getTools().map((t) => ({ slug: t.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const tool = getTool(slug);
  if (!tool) return {};
  return {
    title: tool.name,
    description: tool.summary,
    alternates: { canonical: `/tools/${tool.slug}` },
    openGraph: { type: "article", title: tool.name, description: tool.summary, url: `/tools/${tool.slug}` },
    twitter: { card: "summary_large_image", title: tool.name, description: tool.summary },
  };
}

export default async function ToolPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const tool = getTool(slug);
  if (!tool) notFound();

  // このツールに触れている記事
  const related = getArticles().filter((a) => a.tools.includes(tool.slug));

  return (
    <Container className="max-w-3xl py-12 sm:py-16">
      <JsonLd
        data={breadcrumb(SITE.url, [
          { name: SITE.name, path: "/" },
          { name: "ツール比較", path: "/tools" },
          { name: tool.name, path: `/tools/${tool.slug}` },
        ])}
      />
      <Link href="/tools" className="text-sm text-muted hover:text-fg">
        ← ツール一覧
      </Link>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <h1 className="text-3xl font-bold sm:text-4xl">{tool.name}</h1>
        {tool.featured ? <Badge tone="accent">イチオシ</Badge> : null}
      </div>
      <p className="mt-2 text-sm text-muted">{tool.vendor}</p>
      <p className="mt-4 text-lg text-muted">{tool.summary}</p>

      <div className="mt-6 flex flex-wrap gap-3">
        <a
          href={tool.url}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-accent-fg transition-opacity hover:opacity-90"
        >
          公式サイトを見る
        </a>
        <span className="rounded-lg border border-border bg-surface px-5 py-2.5 text-sm">
          {tool.pricing.label}
        </span>
      </div>

      <section className="mt-12">
        <div className="flex items-end justify-between border-b border-border pb-3">
          <h2 className="text-xl font-bold">評価</h2>
          <p className="text-sm text-muted">
            総合 <span className="text-2xl font-bold tabular-nums text-fg">{overallScore(tool.scores).toFixed(1)}</span> / 5
          </p>
        </div>
        <dl className="mt-5 space-y-4">
          {Object.entries(tool.scores).map(([key, value]) => (
            <div key={key}>
              <div className="flex items-baseline justify-between text-sm">
                <dt>{SCORE_LABELS[key] ?? key}</dt>
                <dd className="tabular-nums font-semibold">{value.toFixed(1)}</dd>
              </div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-2">
                <div className="h-full rounded-full bg-accent" style={{ width: `${(value / 5) * 100}%` }} />
              </div>
            </div>
          ))}
        </dl>

        {tool.review ? (
          <div className="mt-6 rounded-xl border border-border bg-surface-2 p-5 text-sm">
            <p className="font-semibold">この点数の根拠</p>
            <p className="mt-2 text-muted">{tool.review.basis}</p>
            <p className="mt-2 text-xs text-muted">最終更新: {tool.review.updatedAt}</p>
          </div>
        ) : (
          <p className="mt-6 rounded-xl border border-border bg-surface-2 p-5 text-sm text-muted">
            ⚠️ このツールはまだ十分に触れていないため、点数の根拠を書けていません。
            公開情報からの暫定評価です。
          </p>
        )}
      </section>

      <div className="mt-12 grid gap-6 sm:grid-cols-2">
        <section>
          <h2 className="font-bold">強み</h2>
          <ul className="mt-3 space-y-2 text-sm">
            {tool.strengths.map((s, i) => (
              <li key={i} className="flex gap-2">
                <span aria-hidden className="text-accent">＋</span>
                <span>{s}</span>
              </li>
            ))}
          </ul>
        </section>
        <section>
          <h2 className="font-bold">弱み・注意点</h2>
          <ul className="mt-3 space-y-2 text-sm">
            {tool.weaknesses.map((s, i) => (
              <li key={i} className="flex gap-2">
                <span aria-hidden className="text-muted">−</span>
                <span>{s}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>

      {related.length > 0 ? (
        <section className="mt-12 border-t border-border pt-6">
          <h2 className="font-bold">このツールに触れている記事</h2>
          <ul className="mt-3 space-y-2 text-sm">
            {related.map((a) => (
              <li key={a.slug}>
                <Link href={`/articles/${a.slug}`} className="font-semibold hover:text-accent">
                  {a.title}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <p className="mt-10 text-xs text-muted">
        料金・仕様は変動します。契約前に必ず公式サイトで確認してください。
      </p>
    </Container>
  );
}
