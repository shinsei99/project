import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Container } from "@/components/ui/Container";
import { Badge } from "@/components/ui/Badge";
import { CoverArt } from "@/components/ui/CoverArt";
import { getWork, getWorks } from "@/lib/content/works";
import { getPhoto } from "@/lib/content/photos";
import type { Work } from "@/lib/schema";

const PHASE_LABELS: Record<Work["prompts"][number]["phase"], string> = {
  kickoff: "着手",
  feature: "機能追加",
  fix: "修正",
  refactor: "作り直し",
};

export function generateStaticParams() {
  return getWorks().map((w) => ({ slug: w.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const work = getWork(slug);
  if (!work) return {};
  // OG画像は同階層の opengraph-image.tsx が自動で付く。ここでは文言と正規URLだけ指定する
  return {
    title: work.name,
    description: work.summary,
    alternates: { canonical: `/works/${work.slug}` },
    openGraph: {
      type: "article",
      title: work.name,
      description: work.summary,
      url: `/works/${work.slug}`,
    },
    twitter: { card: "summary_large_image", title: work.name, description: work.summary },
  };
}

/** 見出し＋中身。4本柱を同じ形で並べる */
function Section({
  n,
  title,
  note,
  children,
}: {
  n: string;
  title: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mt-14">
      <div className="mb-5 border-b border-border pb-3">
        <h2 className="text-xl font-bold">
          <span className="mr-2 text-accent">{n}</span>
          {title}
        </h2>
        {note ? <p className="mt-1 text-sm text-muted">{note}</p> : null}
      </div>
      {children}
    </section>
  );
}

export default async function WorkPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const work = getWork(slug);
  if (!work) notFound();

  const photo = getPhoto(work.slug);

  return (
    <article className="py-12 sm:py-16">
      <Container className="max-w-3xl">
        <Link href="/works" className="text-sm text-muted hover:text-fg">
          ← 制作記録の一覧
        </Link>

        <div className="mt-6 flex flex-wrap gap-2">
          {work.stack.map((s) => (
            <Badge key={s} tone="outline">
              {s}
            </Badge>
          ))}
        </div>

        <h1 className="mt-4 text-3xl font-bold leading-tight sm:text-4xl">{work.name}</h1>
        <p className="mt-4 text-lg text-muted">{work.summary}</p>

        {work.buildTime ? (
          <p className="mt-3 text-sm text-muted">
            <span className="font-semibold text-fg">所要:</span> {work.buildTime}
          </p>
        ) : null}

        {work.links.length > 0 ? (
          <div className="mt-6 rounded-xl border border-border bg-surface p-4">
            <p className="text-sm font-semibold">この記録から書いた記事</p>
            <ul className="mt-2 space-y-1.5">
              {work.links.map((l) => (
                <li key={l.url} className="text-sm">
                  <a
                    href={l.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-semibold text-accent hover:underline"
                  >
                    {l.label} ↗
                  </a>
                  {l.note ? <span className="ml-2 text-muted">{l.note}</span> : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <CoverArt seed={work.slug} label="制作記録" image={photo?.src} className="mt-8 !h-56" />

        {work.prompts.length > 0 ? (
          <Section
            n="①"
            title="投げたプロンプト"
            note="読みやすさのため、体裁と語調を整えています（内容と指示の粒度はそのまま）。"
          >
            <div className="space-y-6">
              {work.prompts.map((p, i) => (
                <div key={i} className="rounded-xl border border-border bg-surface p-5">
                  <div className="mb-3 flex flex-wrap items-center gap-2">
                    <Badge tone="accent">{PHASE_LABELS[p.phase]}</Badge>
                    <span className="text-sm text-muted">{p.intent}</span>
                  </div>
                  <pre className="table-scroll rounded-lg bg-surface-2 p-4 text-sm leading-relaxed whitespace-pre-wrap">
                    {p.text}
                  </pre>
                  {p.result ? (
                    <p className="mt-3 border-l-2 border-accent pl-3 text-sm text-muted">
                      <span className="font-semibold text-fg">結果: </span>
                      {p.result}
                    </p>
                  ) : null}
                </div>
              ))}
            </div>
          </Section>
        ) : null}

        {work.features.length > 0 ? (
          <Section n="②" title="できた機能">
            <ul className="space-y-2">
              {work.features.map((f, i) => (
                <li key={i} className="flex gap-3">
                  <span aria-hidden className="mt-1 text-accent">
                    ✓
                  </span>
                  <span>{f}</span>
                </li>
              ))}
            </ul>
          </Section>
        ) : null}

        {work.process.length > 0 ? (
          <Section n="③" title="完成までの過程">
            <ol className="space-y-5">
              {work.process.map((s, i) => (
                <li key={i} className="border-l-2 border-border pl-5">
                  <div className="text-xs font-semibold text-accent">{s.step}</div>
                  <h3 className="mt-1 font-semibold">{s.title}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-muted">{s.detail}</p>
                </li>
              ))}
            </ol>
          </Section>
        ) : null}

        {work.improvements.length > 0 ? (
          <Section
            n="④"
            title="改善過程"
            note="症状 → 原因 → 直し方。原因が分かっていないものは「未特定」と書いています。"
          >
            <div className="space-y-4">
              {work.improvements.map((im, i) => (
                <div key={i} className="rounded-xl border border-border bg-surface p-5">
                  <p className="font-semibold">{im.symptom}</p>
                  <dl className="mt-3 space-y-2 text-sm">
                    <div className="flex gap-3">
                      <dt className="w-14 shrink-0 text-muted">原因</dt>
                      <dd>{im.cause}</dd>
                    </div>
                    <div className="flex gap-3">
                      <dt className="w-14 shrink-0 text-muted">直し方</dt>
                      <dd>{im.fix}</dd>
                    </div>
                    {im.metric ? (
                      <div className="flex gap-3">
                        <dt className="w-14 shrink-0 text-muted">実測</dt>
                        <dd className="font-semibold tabular-nums">{im.metric}</dd>
                      </div>
                    ) : null}
                  </dl>
                </div>
              ))}
            </div>
          </Section>
        ) : null}
      </Container>
    </article>
  );
}
