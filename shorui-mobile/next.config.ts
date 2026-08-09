import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 写真を数枚まとめて送るので、サーバーアクション/APIのボディ上限を緩める
  experimental: {
    serverActions: { bodySizeLimit: "40mb" },
  },
};

export default nextConfig;
