import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { CoverArt } from "@/components/ui/CoverArt";
import { getPhoto } from "@/lib/content/photos";
import type { Work } from "@/lib/schema";

/**
 * 制作記録のカード。**出すのは成果物ではなく作り方**なので、
 * 見せる数字はプロンプト数・機能数・改善数にしている。
 */
export function WorkCard({ work }: { work: Work }) {
  const photo = getPhoto(work.slug);
  const counts = [
    { label: "プロンプト", n: work.prompts.length },
    { label: "機能", n: work.features.length },
    { label: "改善", n: work.improvements.length },
  ].filter((c) => c.n > 0);

  return (
    <Card as="article" interactive className="flex h-full flex-col">
      <CoverArt seed={work.slug} label="制作記録" image={photo?.src} className="mb-4" />
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {work.stack.slice(0, 3).map((s) => (
          <Badge key={s} tone="outline">
            {s}
          </Badge>
        ))}
      </div>
      <h3 className="font-semibold leading-snug">
        <Link href={`/works/${work.slug}`} className="hover:text-accent">
          {work.name}
        </Link>
      </h3>
      <p className="mt-2 flex-1 text-sm leading-relaxed text-muted">{work.summary}</p>

      {counts.length > 0 ? (
        <dl className="mt-4 flex gap-5 border-t border-border pt-3">
          {counts.map((c) => (
            <div key={c.label}>
              <dt className="text-xs text-muted">{c.label}</dt>
              <dd className="text-lg font-bold tabular-nums">{c.n}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </Card>
  );
}
