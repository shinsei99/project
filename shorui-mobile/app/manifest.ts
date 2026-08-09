import type { MetadataRoute } from "next";

// ホーム画面に追加したとき、独立アプリ（全画面）として起動させるための設定。
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "書類キャビネット 取込",
    short_name: "書類取込",
    description: "紙の書類を撮ってDropboxへ送る。PCのキャビネットが整理します。",
    start_url: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#0f172a",
    theme_color: "#0f172a",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
