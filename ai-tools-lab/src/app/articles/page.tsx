import type { Metadata } from "next";
import { Container } from "@/components/ui/Container";
import { ArticleCard } from "@/components/articles/ArticleCard";
import { getArticles } from "@/lib/content/articles";

export const metadata: Metadata = {
  title: "記事",
  description: "導入ガイド、AIの歴史変革、ツール比較、実務で効いたプロンプトの型。",
};

export default function ArticlesPage() {
  const articles = getArticles();

  return (
    <Container className="py-14 sm:py-20">
      <h1 className="text-3xl font-bold sm:text-4xl">記事</h1>
      <p className="mt-3 max-w-2xl text-muted">
        読んだあとに手が動くことを基準に書いています。全{articles.length}本。
      </p>

      <div className="mt-10 grid gap-4 md:grid-cols-3">
        {articles.map((a) => (
          <ArticleCard key={a.slug} article={a} />
        ))}
      </div>
    </Container>
  );
}
