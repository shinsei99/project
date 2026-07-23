import { checkAccessCode } from "@/lib/gemini";

export const runtime = "nodejs";

/** アクセスコードの検証のみを行う軽量エンドポイント（ログイン時の即時判定用）。 */
function handle(req: Request): Response {
  return checkAccessCode(req)
    ? Response.json({ ok: true })
    : Response.json({ error: "アクセスコードが違います" }, { status: 401 });
}

export async function GET(req: Request) {
  return handle(req);
}
export async function POST(req: Request) {
  return handle(req);
}
