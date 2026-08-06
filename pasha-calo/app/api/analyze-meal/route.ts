import {
  analyzeMeal,
  hasApiKey,
  missingKeyMessage,
  RefusalError,
  type InputImage,
} from "@/lib/ai";
import { checkAccessCode } from "@/lib/auth";

export const runtime = "nodejs";
export const maxDuration = 60;

const MAX_IMAGES = 6;
const ALLOWED_MIME = ["image/jpeg", "image/png", "image/webp"];

/** data URL or 生base64 を {data, mimeType} に分解。 */
function parseImage(raw: string): InputImage | null {
  if (typeof raw !== "string" || !raw) return null;
  const match = raw.match(/^data:(image\/[a-zA-Z+]+);base64,(.*)$/);
  if (match) return { mimeType: match[1], data: match[2] };
  return { mimeType: "image/jpeg", data: raw };
}

export async function POST(request: Request) {
  if (!checkAccessCode(request)) {
    return Response.json({ error: "アクセスコードが違います" }, { status: 401 });
  }
  if (!hasApiKey) {
    return Response.json({ error: missingKeyMessage }, { status: 500 });
  }

  let rawImages: string[] = [];
  try {
    const body = await request.json();
    if (Array.isArray(body?.images)) {
      rawImages = body.images.filter((x: unknown) => typeof x === "string");
    } else if (typeof body?.image === "string") {
      rawImages = [body.image];
    }
  } catch {
    return Response.json({ error: "リクエストが不正です" }, { status: 400 });
  }

  if (rawImages.length === 0) {
    return Response.json({ error: "画像がありません" }, { status: 400 });
  }
  if (rawImages.length > MAX_IMAGES) {
    return Response.json({ error: `画像は最大${MAX_IMAGES}枚までです` }, { status: 400 });
  }

  const images: InputImage[] = [];
  for (const raw of rawImages) {
    const img = parseImage(raw);
    if (!img) return Response.json({ error: "画像の形式が不正です" }, { status: 400 });
    if (!ALLOWED_MIME.includes(img.mimeType)) {
      return Response.json(
        { error: "対応していない画像形式です（JPEG/PNG/WebP）" },
        { status: 400 }
      );
    }
    images.push(img);
  }

  try {
    return Response.json(await analyzeMeal(images));
  } catch (err) {
    console.error("[/api/analyze-meal]", err);
    if (err instanceof RefusalError) {
      return Response.json(
        { error: "この写真は解析できませんでした。別の写真でお試しください。" },
        { status: 422 }
      );
    }
    return Response.json(
      { error: "解析に失敗しました。明るい場所で料理全体が入るように撮り直してみてください。" },
      { status: 502 }
    );
  }
}
