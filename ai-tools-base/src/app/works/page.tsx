import type { Metadata } from "next";
import { Container } from "@/components/ui/Container";
import { WorkCard } from "@/components/works/WorkCard";
import { getWorks, getWorkStats } from "@/lib/content/works";

export const metadata: Metadata = {
  title: "制作記録",
  description:
    "投げたプロンプト・できた機能・完成までの過程・その後の改善過程。成果物ではなく作り方を公開しています。",
};

export default function WorksPage() {
  const works = getWorks();
  const stats = getWorkStats();

  return (
    <Container className="py-14 sm:py-20">
      <h1 className="text-3xl font-bold sm:text-4xl">制作記録</h1>
      <p className="mt-3 max-w-2xl text-muted">
        出すのは成果物ではなく<strong className="text-fg">作り方</strong>です。
        ①投げたプロンプト ②できた機能 ③完成までの過程 ④その後の改善過程 の4点。
        アプリ本体・画面・顧客データは公開しません。だから社内業務アプリでも記録にできます。
      </p>

      <dl className="mt-8 flex flex-wrap gap-8 border-y border-border py-5">
        {[
          { label: "公開している記録", value: stats.published },
          { label: "掲載プロンプト", value: stats.prompts },
          { label: "記録した改善", value: stats.improvements },
          { label: "社内のみ（本数だけ計上）", value: stats.internal },
        ].map((s) => (
          <div key={s.label}>
            <dt className="text-xs text-muted">{s.label}</dt>
            <dd className="mt-1 text-2xl font-bold tabular-nums">{s.value}</dd>
          </div>
        ))}
      </dl>

      <div className="mt-10 grid gap-4 md:grid-cols-3">
        {works.map((w) => (
          <WorkCard key={w.slug} work={w} />
        ))}
      </div>
    </Container>
  );
}
