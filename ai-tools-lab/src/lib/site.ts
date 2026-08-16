/**
 * サイト自身の情報。**URLを書く場所をここ1箇所にする。**
 *
 * 独自ドメインへ移すときに直すのはこのファイルだけ。
 * sitemap / robots / OGP / 各ページの canonical が全部ここを見る。
 */
export const SITE = {
  /** 本番URL。末尾スラッシュ無し */
  url: "https://ai-tools-lab-psi.vercel.app",
  name: "AIツールラボ",
  tagline: "Claude Code を主軸に",
  description:
    "自律型AIエージェント時代の開発ガイド。Claude Code を主軸にツールを比較し、実際に業務アプリを作った過程・プロンプト・改善記録を公開します。",
  locale: "ja_JP",
} as const;
