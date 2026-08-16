/**
 * コンテンツ読み出しの**唯一の入口**。
 *
 * ページ・コンポーネントは必ずこの層を経由してコンテンツを取る（`fs` を直接触らない）。
 * 将来コンテンツをDB（Prisma等）やCMSへ移すときは、**このファイルの実装だけ差し替える**。
 * 呼び出し側の書き換えが要らないことが、この境界を置いている唯一の理由。
 *
 * 実装方針:
 * - サーバー側でのみ動く（`server-only` を付けてクライアントへの混入を防ぐ）
 * - 読み込みは同期。件数が数千件になったら非同期＋キャッシュへ変える
 * - **検証に落ちたコンテンツは黙って捨てず、どのファイルが悪いか出して例外にする**
 */
import "server-only";

import fs from "node:fs";
import path from "node:path";
import matter from "gray-matter";
import { z } from "zod";

const CONTENT_DIR = path.join(process.cwd(), "content");

/** JSONを1件読んで検証する。壊れていればファイル名つきで落とす */
function readJson<T>(file: string, schema: z.ZodType<T>): T {
  const raw = fs.readFileSync(file, "utf8");
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (e) {
    throw new Error(`JSONとして読めません: ${path.relative(process.cwd(), file)}\n${String(e)}`);
  }
  const result = schema.safeParse(parsed);
  if (!result.success) {
    throw new Error(
      `コンテンツの形が違います: ${path.relative(process.cwd(), file)}\n` +
        result.error.issues.map((i) => `  - ${i.path.join(".") || "(root)"}: ${i.message}`).join("\n"),
    );
  }
  return result.data;
}

/** ディレクトリ内のJSONを全件読む。フォルダが無い場合は空配列（初期状態を壊さない） */
export function readJsonCollection<T>(dir: string, schema: z.ZodType<T>): T[] {
  const target = path.join(CONTENT_DIR, dir);
  if (!fs.existsSync(target)) return [];
  return fs
    .readdirSync(target)
    .filter((f) => f.endsWith(".json"))
    .sort()
    .map((f) => readJson(path.join(target, f), schema));
}

/** MDXの frontmatter だけを読む。本文レンダリングは Stage 2（ページ側で別途読む） */
export function readMdxFrontmatter<T>(dir: string, schema: z.ZodType<T>): (T & { body: string })[] {
  const target = path.join(CONTENT_DIR, dir);
  if (!fs.existsSync(target)) return [];
  return fs
    .readdirSync(target)
    .filter((f) => f.endsWith(".mdx"))
    .sort()
    .map((f) => {
      const file = path.join(target, f);
      const { data, content } = matter(fs.readFileSync(file, "utf8"));
      const result = schema.safeParse(data);
      if (!result.success) {
        throw new Error(
          `frontmatterの形が違います: ${path.relative(process.cwd(), file)}\n` +
            result.error.issues.map((i) => `  - ${i.path.join(".") || "(root)"}: ${i.message}`).join("\n"),
        );
      }
      return { ...result.data, body: content };
    });
}

/** 単一のJSONファイル（categories.json など） */
export function readJsonFile<T>(relPath: string, schema: z.ZodType<T>): T {
  return readJson(path.join(CONTENT_DIR, relPath), schema);
}
