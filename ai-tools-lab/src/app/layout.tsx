import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { Container } from "@/components/ui/Container";
import { PhotoCredits } from "@/components/ui/PhotoCredits";
import { SITE } from "@/lib/site";

/**
 * `metadataBase` を入れておくと、各ページで相対パス（`/works/xxx`）を書くだけで
 * canonical と OGP が絶対URLになる。**独自ドメインへ移すときは `SITE.url` だけ直せばよい。**
 *
 * OG画像は `opengraph-image.tsx` が記事ごとに生成する（ファイル規約で自動的に紐づく）。
 * ここで images を指定していないのはそのため。
 */
export const metadata: Metadata = {
  metadataBase: new URL(SITE.url),
  title: {
    default: `${SITE.name} — Claude Code 主軸のAI開発ガイド`,
    template: `%s | ${SITE.name}`,
  },
  description: SITE.description,
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    siteName: SITE.name,
    locale: SITE.locale,
    url: "/",
    title: `${SITE.name} — Claude Code 主軸のAI開発ガイド`,
    description: SITE.description,
  },
  twitter: {
    card: "summary_large_image",
    title: `${SITE.name} — Claude Code 主軸のAI開発ガイド`,
    description: SITE.description,
  },
};

const NAV = [
  { href: "/tools", label: "ツール比較" },
  { href: "/works", label: "制作記録" },
  { href: "/articles", label: "記事" },
  { href: "/history", label: "AIの歴史" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body>
        <header className="sticky top-0 z-20 border-b border-border bg-bg/85 backdrop-blur">
          <Container className="flex h-16 items-center justify-between gap-6">
            <Link href="/" className="font-bold tracking-tight">
              AIツールラボ
              <span className="ml-2 hidden text-xs font-normal text-muted sm:inline">
                Claude Code を主軸に
              </span>
            </Link>
            <nav className="flex items-center gap-4 text-sm">
              {NAV.map((n) => (
                <Link key={n.href} href={n.href} className="text-muted hover:text-fg">
                  {n.label}
                </Link>
              ))}
            </nav>
          </Container>
        </header>

        <main>{children}</main>

        <footer className="border-t border-border py-10 text-sm text-muted">
          <Container>
            <div className="flex flex-wrap items-center justify-between gap-4">
              <p>AIツールラボ — 掲載する評価は実際に触った範囲のものです。</p>
              <p>料金・仕様は変動します。契約前に公式サイトで確認してください。</p>
            </div>
            <PhotoCredits />
          </Container>
        </footer>
      </body>
    </html>
  );
}
