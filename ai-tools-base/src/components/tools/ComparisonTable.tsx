"use client";

/**
 * ツール比較テーブル。トップページの主役。
 *
 * クライアントコンポーネントなのは検索・絞り込み・並べ替えのため。
 * **データの読み出しはサーバー側で済ませて props で渡す**（ここで fetch しない）。
 * 表は横に長くなるので、ページ本体ではなく表自身を横スクロールさせる。
 */
import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import {
  overallScore,
  type Category,
  type PricingModel,
  type Tool,
  type ToolCategory,
} from "@/lib/schema";

const PRICING_LABELS: Record<PricingModel, string> = {
  free: "無料",
  freemium: "無料枠あり",
  subscription: "定額",
  usage: "従量",
};

type SortKey = "overall" | "autonomy" | "costEfficiency" | "learningCurve" | "name";

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: "overall", label: "総合スコア順" },
  { key: "autonomy", label: "自律性が高い順" },
  { key: "costEfficiency", label: "費用対効果が高い順" },
  { key: "learningCurve", label: "習得しやすい順" },
  { key: "name", label: "名前順" },
];

/** 0〜5 のスコアを細い横棒で表す。数値だけより差が一目で分かる */
function ScoreBar({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 shrink-0 overflow-hidden rounded-full bg-surface-2">
        <div className="h-full rounded-full bg-accent" style={{ width: `${(value / 5) * 100}%` }} />
      </div>
      <span className="tabular-nums text-xs text-muted">{value.toFixed(1)}</span>
    </div>
  );
}

export function ComparisonTable({
  tools,
  categories,
}: {
  tools: Tool[];
  categories: Category[];
}) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<ToolCategory | "all">("all");
  const [freeOnly, setFreeOnly] = useState(false);
  const [sort, setSort] = useState<SortKey>("overall");

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = tools.filter((t) => {
      if (category !== "all" && t.category !== category) return false;
      if (freeOnly && !t.pricing.freeTier) return false;
      if (!q) return true;
      // 名前・提供元・要約・強みまで含めて拾う（型名だけだと日本語で引っかからない）
      return [t.name, t.vendor, t.summary, ...t.strengths].join(" ").toLowerCase().includes(q);
    });

    return [...filtered].sort((a, b) => {
      if (sort === "name") return a.name.localeCompare(b.name);
      if (sort === "overall") return overallScore(b.scores) - overallScore(a.scores);
      return b.scores[sort] - a.scores[sort];
    });
  }, [tools, query, category, freeOnly, sort]);

  return (
    <div>
      {/* 絞り込み操作 */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="ツール名・特徴で検索"
          aria-label="ツールを検索"
          className="min-w-0 flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm outline-none placeholder:text-muted focus:border-accent"
        />
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value as ToolCategory | "all")}
          aria-label="カテゴリで絞り込む"
          className="rounded-lg border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
        >
          <option value="all">すべてのカテゴリ</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.label}
            </option>
          ))}
        </select>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value as SortKey)}
          aria-label="並べ替え"
          className="rounded-lg border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
        >
          {SORT_OPTIONS.map((o) => (
            <option key={o.key} value={o.key}>
              {o.label}
            </option>
          ))}
        </select>
        <label className="flex cursor-pointer items-center gap-2 text-sm text-muted">
          <input
            type="checkbox"
            checked={freeOnly}
            onChange={(e) => setFreeOnly(e.target.checked)}
            className="size-4 accent-[var(--color-accent)]"
          />
          無料で試せるものだけ
        </label>
      </div>

      <div className="table-scroll rounded-xl border border-border bg-surface">
        <table className="w-full min-w-[52rem] border-collapse text-sm">
          <thead>
            <tr className="border-b border-border bg-surface-2 text-left">
              <th scope="col" className="px-4 py-3 font-semibold">ツール</th>
              <th scope="col" className="px-4 py-3 font-semibold">料金</th>
              <th scope="col" className="px-4 py-3 font-semibold">自律性</th>
              <th scope="col" className="px-4 py-3 font-semibold">費用対効果</th>
              <th scope="col" className="px-4 py-3 font-semibold">習得しやすさ</th>
              <th scope="col" className="px-4 py-3 text-right font-semibold">総合</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => (
              <tr
                key={t.slug}
                className={`border-b border-border last:border-0 ${
                  t.featured ? "bg-accent-soft/40" : ""
                }`}
              >
                <th scope="row" className="px-4 py-3 text-left font-normal align-top">
                  <div className="flex flex-wrap items-center gap-2">
                    <a
                      href={t.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-semibold underline-offset-4 hover:underline"
                    >
                      {t.name}
                    </a>
                    {t.featured ? <Badge tone="accent">イチオシ</Badge> : null}
                  </div>
                  <p className="mt-1 max-w-md text-xs leading-relaxed text-muted">{t.summary}</p>
                </th>
                <td className="px-4 py-3 align-top">
                  <div className="whitespace-nowrap">{t.pricing.label}</div>
                  <div className="mt-1">
                    <Badge>{PRICING_LABELS[t.pricing.model]}</Badge>
                  </div>
                </td>
                <td className="px-4 py-3 align-top"><ScoreBar value={t.scores.autonomy} /></td>
                <td className="px-4 py-3 align-top"><ScoreBar value={t.scores.costEfficiency} /></td>
                <td className="px-4 py-3 align-top"><ScoreBar value={t.scores.learningCurve} /></td>
                <td className="px-4 py-3 text-right align-top tabular-nums font-semibold">
                  {overallScore(t.scores).toFixed(1)}
                </td>
              </tr>
            ))}
            {rows.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-muted">
                  条件に合うツールがありません。検索語を短くするか、絞り込みを外してください。
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-xs text-muted">
        スコアは0〜5。実際に触った範囲での評価で、根拠のない点は付けていません。
        料金は変動するため、契約前に必ず公式サイトで確認してください。
      </p>
    </div>
  );
}
