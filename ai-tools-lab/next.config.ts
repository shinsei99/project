import type { NextConfig } from "next";

/**
 * 既定は **Vercel 向け**（ルート直下・SSG）。
 *
 * 会社サーバー（FTP）へ静的書き出しする場合だけ、環境変数で切り替える:
 *   NEXT_PUBLIC_BASE_PATH=/ai-lab STATIC_EXPORT=1 npm run build
 *   python3 publish.py
 *
 * 切り替えを環境変数に寄せてあるのは、公開先を変えてもコードを触らずに済ませるため。
 */
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
const isStaticExport = process.env.STATIC_EXPORT === "1";

const nextConfig: NextConfig = {
  ...(isStaticExport ? { output: "export" as const, trailingSlash: true } : {}),
  ...(basePath ? { basePath } : {}),
  images: {
    // 静的書き出しでは Next の画像最適化サーバーが無いため、最適化を通さない
    unoptimized: isStaticExport,
  },
};

export default nextConfig;
