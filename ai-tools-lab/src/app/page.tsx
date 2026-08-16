/**
 * トップページ。サーバーコンポーネント。
 *
 * ここでの役割は「コンテンツ層から取って、表示コンポーネントへ渡す」だけ。
 * 絞り込みなどの対話的な処理は ComparisonTable（クライアント側）が持つ。
 */
import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { Hero } from "@/components/marketing/Hero";
import { FeatureGrid } from "@/components/marketing/FeatureGrid";
import { ComparisonTable } from "@/components/tools/ComparisonTable";
import { ArticleCard } from "@/components/articles/ArticleCard";
import { WorkCard } from "@/components/works/WorkCard";
import { getCategories, getTools } from "@/lib/content/tools";
import { getFeaturedArticles } from "@/lib/content/articles";
import { getFeaturedWorks, getWorkStats } from "@/lib/content/works";

export default function HomePage() {
  const tools = getTools();
  const categories = getCategories();
  const articles = getFeaturedArticles(3);
  const works = getFeaturedWorks(3);
  const workStats = getWorkStats();

  return (
    <>
      <Hero
        stats={[
          { label: "比較しているツール", value: `${tools.length}` },
          { label: "公開している制作記録", value: `${workStats.published}` },
          { label: "掲載プロンプト", value: `${workStats.prompts}` },
          { label: "記録した改善", value: `${workStats.improvements}` },
        ]}
      />

      <section className="py-14 sm:py-20">
        <SectionHeading
          eyebrow="このサイトの方針"
          title="比較して終わりにしない"
          description="読んだあとに手が動くことを基準に、載せる情報を決めています。"
        />
        <FeatureGrid />
      </section>

      <section id="tools" className="scroll-mt-8 border-t border-border py-14 sm:py-20">
        <SectionHeading
          eyebrow="ツール比較"
          title="主軸を決めるための比較表"
          description="検索・カテゴリ・料金体系で絞り込めます。並べ替えると重視する軸が変えられます。"
          action={
            <Link
              href="/tools"
              className="rounded-lg border border-border bg-surface px-4 py-2 text-sm font-semibold transition-colors hover:border-accent"
            >
              全ツールを見る
            </Link>
          }
        />
        <Container>
          <ComparisonTable tools={tools} categories={categories} />
        </Container>
      </section>

      <section className="border-t border-border py-14 sm:py-20">
        <SectionHeading
          eyebrow="制作記録"
          title="作り方を公開する"
          description={`投げたプロンプト・できた機能・完成までの過程・その後の改善過程。公開${workStats.published}本（ほかに社内向け${workStats.internal}本は本数のみ集計）。`}
          action={
            <Link
              href="/works"
              className="rounded-lg border border-border bg-surface px-4 py-2 text-sm font-semibold transition-colors hover:border-accent"
            >
              すべての記録
            </Link>
          }
        />
        <Container>
          <div className="grid gap-4 md:grid-cols-3">
            {works.map((w) => (
              <WorkCard key={w.slug} work={w} />
            ))}
          </div>
        </Container>
      </section>

      <section className="border-t border-border py-14 sm:py-20">
        <SectionHeading
          eyebrow="記事"
          title="読みもの"
          description="導入手順、変革期の整理、実務で効いたプロンプトの型。"
          action={
            <Link
              href="/articles"
              className="rounded-lg border border-border bg-surface px-4 py-2 text-sm font-semibold transition-colors hover:border-accent"
            >
              記事一覧
            </Link>
          }
        />
        <Container>
          <div className="grid gap-4 md:grid-cols-3">
            {articles.map((a) => (
              <ArticleCard key={a.slug} article={a} />
            ))}
          </div>
        </Container>
      </section>
    </>
  );
}
