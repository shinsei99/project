import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

// 合言葉の確認だけ。実際の防御は /api/upload 側でも毎回チェックする。
export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const password = (body?.password as string) || "";
  const ok = !!process.env.APP_PASSWORD && password === process.env.APP_PASSWORD;
  return NextResponse.json({ ok }, { status: ok ? 200 : 401 });
}
