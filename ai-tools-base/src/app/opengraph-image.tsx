/**
 * サイト共通のOG画像（SNSやチャットにURLを貼ったときのカード画像）。
 *
 * **画像ファイルを用意せず、その場で描く。** タイトルを変えても作り直しが要らないため。
 * 記事ごとの画像は `works/[slug]/opengraph-image.tsx` が別に描く。
 *
 * 注意: ここは画像を生成する特別なファイルなので、**外部フォントを読みに行かない**。
 * 日本語フォントを fetch すると生成が遅くなり、失敗したときカードが出なくなる。
 * 既定のフォントで確実に出す方を選んでいる。
 */
import { ImageResponse } from "next/og";
import { SITE } from "@/lib/site";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = SITE.name;

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          background: "#0b1020",
          color: "#f8fafc",
          padding: 80,
        }}
      >
        <div style={{ display: "flex", fontSize: 30, color: "#7dd3fc", letterSpacing: 4 }}>
          {SITE.tagline}
        </div>
        <div style={{ display: "flex", fontSize: 92, fontWeight: 700, marginTop: 16 }}>
          {SITE.name}
        </div>
        <div style={{ display: "flex", fontSize: 34, color: "#94a3b8", marginTop: 28 }}>
          ツール比較 / 制作記録 / プロンプトと改善の記録
        </div>
        <div
          style={{
            display: "flex",
            marginTop: 48,
            height: 8,
            width: 220,
            background: "#38bdf8",
            borderRadius: 4,
          }}
        />
      </div>
    ),
    size,
  );
}
