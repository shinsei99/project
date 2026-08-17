// pdf.js のページ画像化スケール（大きいほど高精細・サイズ増）。
// 2026-08-17: 画像を WebP にして容量が大幅に下がったため 1.5 → 2.0 に上げた
// （1.5 は約108dpi相当で小さい文字が読みづらかった）。
export const RENDER_SCALE = 2.0;

// ページ画像の形式。**上から順に試して、ブラウザが対応したものを使う**。
// pdf.js の描画結果は輪郭のはっきりした合成画像なので、ロスレスWebPが極端に効く
// （文字ページの実測: PNG 856KB → ロスレスWebP 10KB → 品質80のWebP 365KB）。
// Safari が canvas.toBlob("image/webp") を書き出せるかは端末次第なので、
// 実際に返ってきた Blob の type を見て判定し、駄目なら次の候補へ落とす。
export const IMAGE_CANDIDATES: { mime: string; quality?: number }[] = [
  { mime: "image/webp" }, // quality 未指定 = ロスレス相当（実装依存だが最も小さくなる）
  { mime: "image/webp", quality: 0.9 },
  { mime: "image/png" }, // 最後の砦。どのブラウザでも必ず書き出せる
];

// 検索結果の最大件数
export const SEARCH_LIMIT = 200;
