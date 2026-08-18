// pdf.js のページ画像化スケール（大きいほど高精細・サイズ増）。
// 2.0 で A4 が約 992×1454px。実測でスキャン本の本文がしっかり読める大きさ。
export const RENDER_SCALE = 2.0;

// ページ画像の形式。**上から順に試して、返ってきた Blob の type が一致したものを使う。**
// v3（2026-08-17）から「見たページだけ」その場で作る方式にしたので、
// 1ページあたりの画質と容量の釣り合いを優先して**非可逆**を既定にした。
//
// 実測（スキャン本1ページ・992×1454）:
//   WebP q85  … 約160KB   ← Mac/Chrome で採用される
//   JPEG q85  … 約255KB   ← iPhone(Safari) は WebP を書き出せないのでこちら
//   PNG       … 約1.6MB   ← 最後の砦（使われたら容量を食うので画面に出す）
export const IMAGE_CANDIDATES: { mime: string; quality?: number }[] = [
  { mime: "image/webp", quality: 0.85 },
  { mime: "image/jpeg", quality: 0.85 },
  { mime: "image/png" },
];

// 検索結果の最大件数
export const SEARCH_LIMIT = 200;

// 取り込み時に「文字層が無い（未OCR）」と判断するしきい値。1ページあたりの文字数
export const MIN_CHARS_PER_PAGE = 3;

// 表紙（1ページ目）のサムネイル。**取り込み時にこれだけは作る**（本棚に並べるため）。
// 幅480pxなら1冊30〜60KB程度で、77冊でも数MBに収まる。
export const COVER_TARGET_WIDTH = 480;
export const COVER_CANDIDATES: { mime: string; quality?: number }[] = [
  { mime: "image/webp", quality: 0.8 },
  { mime: "image/jpeg", quality: 0.8 },
  { mime: "image/png" },
];

// 読書画面の既定（本文の読みやすさ。端末ごとに保存する）
export const READER_DEFAULTS = { fontSize: 18, lineHeight: 1.9, serif: true };

// 「文字で読める」と判断するひらがな率のしきい値。
// 実測: きれいな本 41% / まだらな本 24% / 図解主体の本 22%（散文の目安は30〜45%）
// → 30% を境にする。quality は 0.35 を満点とした比率なので 30% ≒ 0.857
export const READABLE_QUALITY = 0.857;
// ページ単位で「文字が崩れている」と見なすひらがな率
export const PAGE_GARBLED_HIRAGANA = 0.15;
