import type { Metadata } from "next";
import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { Badge } from "@/components/ui/Badge";
import { getArticle } from "@/lib/content/articles";

export const metadata: Metadata = {
  title: "AIの歴史変革",
  description:
    "黎明期のチャット型AIと、いまの自律型エージェント。年表ではなく「任せられる範囲」の変化として整理します。",
};

/** 3段階。年号ではなく「人間の役割がどう変わったか」で区切る */
const ERAS = [
  {
    era: "黎明期",
    name: "チャット型",
    human: "質問し、コピペし、貼り直す",
    ai: "断片を答える",
    failure: "文脈を知らないので、それらしい嘘を返す",
    detail:
      "手元のコードを知らない相手に説明してから聞く必要があった。会話のたびに前提を渡し直すので、大きな仕事ほど割に合わなかった。",
  },
  {
    era: "補完期",
    name: "エディタ内蔵",
    human: "書きながら承認する",
    ai: "次の数行を予測する",
    failure: "部分最適。設計の誤りは直せない",
    detail:
      "手が動いている場面の速度は上がった。ただし運転席には人が座り続けるので、任せられる量そのものは増えていない。",
  },
  {
    era: "エージェント期",
    name: "自律実行",
    human: "目的とゴールを渡し、レビューする",
    ai: "調べ、書き、試し、直す",
    failure: "任せすぎると差分が巨大になる",
    detail:
      "リポジトリを読んでから直し、テストを走らせて結果を見て直す。一発で正解を出す必要がなくなったことが決定的だった。",
  },
];

const ENABLERS = [
  { title: "文脈の量", body: "リポジトリ全体を読んでから直せるようになり、断片を答える必要がなくなった。" },
  { title: "道具を使う能力", body: "ファイルを読む、コマンドを打つ、テストを走らせる、結果を見て直す。" },
  {
    title: "失敗して直せること",
    body: "人間の開発も一発では終わらない。試して直せるなら、最初の答えが完璧でなくてよい。ここで差が開いた。",
  },
];

const UNCHANGED = [
  { title: "レビューの負荷は人間に残る", body: "むしろ増える。書く時間より読む時間が増えた。" },
  { title: "仕様の曖昧さは解決しない", body: "曖昧な依頼からは、曖昧な成果物が出てくる。" },
  { title: "責任の所在は動かない", body: "動かないものを出荷したら、それは人間の責任。" },
];

export default function HistoryPage() {
  const article = getArticle("agent-era");

  return (
    <Container className="max-w-4xl py-14 sm:py-20">
      <Badge tone="accent">特集</Badge>
      <h1 className="mt-4 text-3xl font-bold sm:text-4xl">AIの歴史変革</h1>
      <p className="mt-4 max-w-2xl text-lg text-muted">
        「AIがコードを書ける」という話は何年も前からありました。それでも現場の景色が本当に変わったのは
        ここ最近です。何が変わったのか——答えは性能の数字ではなく、
        <strong className="text-fg">人間が運転席に座り続ける必要があるかどうか</strong>でした。
      </p>

      {/* 3段階 */}
      <section className="mt-14">
        <h2 className="text-xl font-bold">3つの段階</h2>
        <div className="mt-6 space-y-4">
          {ERAS.map((e, i) => (
            <div
              key={e.era}
              className={`rounded-xl border p-6 ${
                i === ERAS.length - 1 ? "border-accent/50 bg-accent-soft/30" : "border-border bg-surface"
              }`}
            >
              <div className="flex flex-wrap items-baseline gap-3">
                <span className="text-2xl font-bold tabular-nums text-accent">0{i + 1}</span>
                <h3 className="text-lg font-bold">{e.era}</h3>
                <Badge>{e.name}</Badge>
              </div>
              <p className="mt-3 text-sm leading-relaxed text-muted">{e.detail}</p>
              <dl className="mt-4 grid gap-3 border-t border-border pt-4 text-sm sm:grid-cols-3">
                <div>
                  <dt className="text-xs text-muted">人間の役割</dt>
                  <dd className="mt-0.5">{e.human}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">AIの役割</dt>
                  <dd className="mt-0.5">{e.ai}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">失敗の形</dt>
                  <dd className="mt-0.5">{e.failure}</dd>
                </div>
              </dl>
            </div>
          ))}
        </div>
        <p className="mt-5 rounded-xl border border-border bg-surface-2 p-5 text-sm">
          黎明期の弱点は「知らないこと」でした。エージェント期の弱点は「やりすぎること」です。
          <strong>問題の質が変わった</strong>ことが、この変革の本質です。
        </p>
      </section>

      <section className="mt-14">
        <h2 className="text-xl font-bold">何が可能にしたのか</h2>
        <div className="mt-5 grid gap-4 sm:grid-cols-3">
          {ENABLERS.map((x) => (
            <div key={x.title} className="rounded-xl border border-border bg-surface p-5">
              <h3 className="font-semibold">{x.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted">{x.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-14">
        <h2 className="text-xl font-bold">何が変わらなかったのか</h2>
        <div className="mt-5 grid gap-4 sm:grid-cols-3">
          {UNCHANGED.map((x) => (
            <div key={x.title} className="rounded-xl border border-border bg-surface-2 p-5">
              <h3 className="font-semibold">{x.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted">{x.body}</p>
            </div>
          ))}
        </div>
        <p className="mt-5 text-muted">
          「AIが全部やる」ではなく、
          <strong className="text-fg">人間の仕事が、書くことからレビューと意思決定に移った</strong>
          というのが正確な言い方です。学ぶべきはプロンプトの書き方ではなく、
          <strong className="text-fg">任せる範囲の設計</strong>——どこまで任せ、どこで止め、何を確認するか。
        </p>
      </section>

      <div className="mt-14 flex flex-wrap gap-3 border-t border-border pt-8">
        <Link
          href="/works"
          className="rounded-lg bg-accent px-5 py-3 text-sm font-semibold text-accent-fg transition-opacity hover:opacity-90"
        >
          線引きの実例を見る（制作記録）
        </Link>
        {article ? (
          <Link
            href={`/articles/${article.slug}`}
            className="rounded-lg border border-border bg-surface px-5 py-3 text-sm font-semibold transition-colors hover:border-accent"
          >
            記事版を読む
          </Link>
        ) : null}
      </div>
    </Container>
  );
}
