/**
 * 取り込んだフリー写真とそのクレジット。
 *
 * `scripts/fetch-photos.mjs` が Openverse から取り込み、
 * `content/photo-credits.json` に作者・ライセンス・出典を記録している。
 * **CC BY / BY-SA は出典表示が必須**なので、needsCredit のものは必ず画面に出す。
 * 写真が無い場合は undefined を返し、呼び出し側は自前SVGの表紙にフォールバックする。
 */
import "server-only";

import fs from "node:fs";
import path from "node:path";
import { z } from "zod";

const creditSchema = z.object({
  title: z.string(),
  creator: z.string(),
  license: z.string(),
  licenseCode: z.string(),
  needsCredit: z.boolean(),
  source: z.string(),
  provider: z.string(),
});

export type PhotoCredit = z.infer<typeof creditSchema>;

const CREDITS_FILE = path.join(process.cwd(), "content", "photo-credits.json");

function loadCredits(): Record<string, PhotoCredit> {
  if (!fs.existsSync(CREDITS_FILE)) return {};
  const parsed = z
    .record(z.string(), creditSchema)
    .safeParse(JSON.parse(fs.readFileSync(CREDITS_FILE, "utf8")));
  if (!parsed.success) {
    throw new Error(`content/photo-credits.json の形が違います:\n${parsed.error.message}`);
  }
  return parsed.data;
}

/** slug に対応する写真。無ければ undefined（＝SVGの表紙を使う） */
export function getPhoto(slug: string): { src: string; credit: PhotoCredit } | undefined {
  const credit = loadCredits()[slug];
  if (!credit) return undefined;
  const rel = `/photos/${slug}.jpg`;
  if (!fs.existsSync(path.join(process.cwd(), "public", rel))) return undefined;
  return { src: rel, credit };
}

/** 出典表示が要るものだけ。フッターにまとめて出す */
export function getRequiredCredits(): (PhotoCredit & { slug: string })[] {
  return Object.entries(loadCredits())
    .filter(([, c]) => c.needsCredit)
    .map(([slug, c]) => ({ slug, ...c }));
}
