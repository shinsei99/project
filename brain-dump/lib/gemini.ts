import { GoogleGenerativeAI } from "@google/generative-ai";

/**
 * Gemini クライアントとアクセスコード検証を集約するモジュール。
 * APIキーは環境変数 GEMINI_API_KEY からのみ読み込む（コードに直書きしない）。
 */

const apiKey = process.env.GEMINI_API_KEY?.trim() ?? "";

/** 既定モデル。GEMINI_MODEL で上書き可能（例: gemini-2.5-flash / gemini-1.5-flash）。 */
export const MODEL_NAME = process.env.GEMINI_MODEL?.trim() || "gemini-2.5-flash";

/** APIキーが設定されているか。未設定ならルート側で 500 を返す。 */
export const hasApiKey = apiKey.length > 0;

const genAI = hasApiKey ? new GoogleGenerativeAI(apiKey) : null;

export function getModel() {
  if (!genAI) {
    throw new Error("GEMINI_API_KEY が未設定です（.env.local を確認してください）");
  }
  return genAI.getGenerativeModel({ model: MODEL_NAME });
}

/**
 * リクエストヘッダ x-access-code が環境変数 ACCESS_CODE と一致するか検証する。
 * ACCESS_CODE が未設定の場合は「鍵なし」とみなしアクセスを拒否する（誤って全公開しないため）。
 */
export function checkAccessCode(req: Request): boolean {
  const expected = process.env.ACCESS_CODE?.trim() ?? "";
  if (!expected) return false;
  const provided = req.headers.get("x-access-code")?.trim() ?? "";
  return provided.length > 0 && provided === expected;
}

/** Gemini が返した JSON 文字列を安全にパースする（```json フェンス除去にも対応）。 */
export function parseJsonResponse<T>(raw: string): T {
  let text = raw.trim();
  if (text.startsWith("```")) {
    text = text.replace(/^```(?:json)?/i, "").replace(/```$/, "").trim();
  }
  return JSON.parse(text) as T;
}
