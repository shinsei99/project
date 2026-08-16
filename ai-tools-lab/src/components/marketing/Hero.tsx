import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { TerminalMock } from "@/components/marketing/TerminalMock";
import { getPhoto } from "@/lib/content/photos";

/**
 * トップの第一印象。立ち位置（Claude Codeが主軸）を最初に言い切る。
 *
 * ビジュアルは3層構造:
 *   1. 背景写真（CC0）… テクスチャとして薄く敷く。読みやすさを壊さない範囲で
 *   2. 発色のグラデーション … 平坦さを消す
 *   3. ターミナル画面 … **主役**。何をするサイトかを一目で伝える
 */
export function Hero({
  stats,
}: {
  stats: { label: string; value: string }[];
}) {
  const photo = getPhoto("hero");

  return (
    <section className="relative isolate overflow-hidden border-b border-border">
      {/* 1. 背景写真 */}
      {photo ? (
        // eslint-disable-next-line @next/next/no-img-element -- 背景装飾。比率固定のため最適化を通さない
        <img
          src={photo.src}
          alt=""
          aria-hidden
          className="absolute inset-0 -z-20 h-full w-full object-cover opacity-25 dark:opacity-20"
        />
      ) : null}

      {/* 2. 覆い。写真の上でも文字が確実に読めるようにする */}
      <div className="absolute inset-0 -z-10 bg-gradient-to-br from-bg/95 via-bg/88 to-bg/95" />
      <div
        aria-hidden
        className="absolute -top-24 -right-16 -z-10 size-[28rem] rounded-full bg-accent/20 blur-3xl"
      />
      <div
        aria-hidden
        className="absolute -bottom-32 -left-24 -z-10 size-[24rem] rounded-full bg-accent/10 blur-3xl"
      />

      <Container className="py-16 sm:py-24">
        <div className="grid items-center gap-12 lg:grid-cols-[1.05fr_1fr]">
          {/* 左: 言葉 */}
          <div>
            <p className="mb-5 inline-flex rounded-full border border-border bg-surface/80 px-3 py-1 text-xs font-semibold text-accent backdrop-blur">
              チャット型AI → 自律型エージェントへ
            </p>

            {/*
              h1 は「サイトの名前」。標語を h1 に置くと、
              名前がヘッダーの小さな文字にしか無い状態になり階層が逆転する。
              標語はサブタイトルとして直下に置く。
            */}
            <h1 className="text-5xl font-bold tracking-tight sm:text-6xl">AIツールラボ</h1>
            <p className="mt-4 text-xl font-semibold text-muted sm:text-2xl">
              Claude Code を主軸に、AIに<span className="text-accent">任せる範囲</span>を広げる。
            </p>

            <p className="mt-6 max-w-xl text-muted">
              比較して終わりにはしません。主軸を1つ決めたうえで、実際に業務アプリを作った
              過程・投げたプロンプト・つまずいた原因まで公開します。
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/articles/claude-code-setup"
                className="rounded-lg bg-accent px-5 py-3 text-sm font-semibold text-accent-fg transition-opacity hover:opacity-90"
              >
                まずは導入ガイドから
              </Link>
              <Link
                href="#tools"
                className="rounded-lg border border-border bg-surface px-5 py-3 text-sm font-semibold transition-colors hover:border-accent"
              >
                ツールを比較する
              </Link>
            </div>
          </div>

          {/* 右: 主役のビジュアル。狭い画面では言葉の下に回る */}
          <div className="lg:pl-4">
            <TerminalMock />
            <p className="mt-3 text-center text-xs text-muted">
              指示を1行渡すと、調べて・直して・テストするまでを続けて行う
            </p>
          </div>
        </div>

        <dl className="mt-14 grid grid-cols-2 gap-6 border-t border-border pt-8 sm:grid-cols-4">
          {stats.map((s) => (
            <div key={s.label}>
              <dt className="text-xs text-muted">{s.label}</dt>
              <dd className="mt-1 text-2xl font-bold tabular-nums">{s.value}</dd>
            </div>
          ))}
        </dl>
      </Container>
    </section>
  );
}
