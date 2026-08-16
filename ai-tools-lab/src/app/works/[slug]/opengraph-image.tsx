/**
 * 制作記録ごとのOG画像。**記事タイトルが入ったカード**になる。
 *
 * SNSやチャットに貼られたとき、サイト共通の画像だと何の記事か分からず踏まれない。
 * ここでタイトルを描いておくと、リンク自体が見出しとして働く。
 *
 * `generateStaticParams` はページ側と同じ集合（公開ぶんのみ）を使う。
 */
import { ImageResponse } from "next/og";
import { getWork, getWorks } from "@/lib/content/works";
import { SITE } from "@/lib/site";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export function generateStaticParams() {
  return getWorks().map((w) => ({ slug: w.slug }));
}

export default async function Image({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const work = getWork(slug);

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#0b1020",
          color: "#f8fafc",
          padding: 72,
        }}
      >
        <div style={{ display: "flex", fontSize: 28, color: "#7dd3fc", letterSpacing: 3 }}>
          制作記録
        </div>
        <div style={{ display: "flex", fontSize: 64, fontWeight: 700, lineHeight: 1.25 }}>
          {work?.name ?? SITE.name}
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
          <div style={{ display: "flex", fontSize: 28, color: "#94a3b8" }}>
            {work?.stack.slice(0, 4).join(" / ") ?? ""}
          </div>
          <div style={{ display: "flex", fontSize: 30, fontWeight: 700, color: "#38bdf8" }}>
            {SITE.name}
          </div>
        </div>
      </div>
    ),
    size,
  );
}
