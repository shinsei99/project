/**
 * アクセスコード認証（brain-dump と同じ方式）。
 * リクエストヘッダ x-access-code が環境変数 ACCESS_CODE と一致するかだけを見る。
 */

/**
 * ACCESS_CODE が未設定の場合は「鍵なし」とみなしアクセスを拒否する
 * （設定漏れで誤って全公開しないため）。
 */
export function checkAccessCode(req: Request): boolean {
  const expected = process.env.ACCESS_CODE?.trim() ?? "";
  if (!expected) return false;
  const provided = req.headers.get("x-access-code")?.trim() ?? "";
  return provided.length > 0 && provided === expected;
}
