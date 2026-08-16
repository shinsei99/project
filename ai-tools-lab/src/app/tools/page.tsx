import type { Metadata } from "next";
import { Container } from "@/components/ui/Container";
import { ComparisonTable } from "@/components/tools/ComparisonTable";
import { getCategories, getTools } from "@/lib/content/tools";

export const metadata: Metadata = {
  title: "ツール比較",
  description:
    "AI開発支援ツールを5つの共通軸で比較。検索・カテゴリ・料金体系で絞り込めます。",
};

export default function ToolsPage() {
  const tools = getTools();
  const categories = getCategories();

  return (
    <Container className="py-14 sm:py-20">
      <h1 className="text-3xl font-bold sm:text-4xl">ツール比較</h1>
      <p className="mt-3 max-w-2xl text-muted">
        「どれが最強か」ではなく「主軸を1つ決めて、足りない部分に何を足すか」で見ています。
        全{tools.length}件。
      </p>

      <div className="mt-10">
        <ComparisonTable tools={tools} categories={categories} />
      </div>

      <section className="mt-14">
        <h2 className="text-xl font-bold">カテゴリの意味</h2>
        <dl className="mt-4 grid gap-4 sm:grid-cols-2">
          {categories.map((c) => (
            <div key={c.id} className="rounded-xl border border-border bg-surface p-5">
              <dt className="font-semibold">{c.label}</dt>
              <dd className="mt-1 text-sm text-muted">{c.description}</dd>
            </div>
          ))}
        </dl>
      </section>
    </Container>
  );
}
