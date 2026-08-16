/** ツールの取得。並び順の既定はここで決める（表示側で毎回sortしない） */
import "server-only";

import { categorySchema, overallScore, toolSchema, type Category, type Tool } from "@/lib/schema";
import { readJsonCollection, readJsonFile } from "./source";
import { z } from "zod";

export function getTools(): Tool[] {
  return readJsonCollection("tools", toolSchema).sort(
    (a, b) => overallScore(b.scores) - overallScore(a.scores),
  );
}

export function getFeaturedTools(): Tool[] {
  return getTools().filter((t) => t.featured);
}

export function getTool(slug: string): Tool | undefined {
  return getTools().find((t) => t.slug === slug);
}

export function getCategories(): Category[] {
  return readJsonFile("categories.json", z.array(categorySchema));
}
