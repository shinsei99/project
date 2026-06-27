import { SchemaType, type Schema } from "@google/generative-ai";
import {
  getModel,
  hasApiKey,
  checkAccessCode,
  parseJsonResponse,
} from "@/lib/gemini";

export const runtime = "nodejs";
export const maxDuration = 60;

const MAX_IMAGES = 10;

const IMAGE_PROMPT = `添付された画像（1枚以上）は、本の一節・ネット記事・資料の複数ページ、会合/イベントの案内、または関連する複数の写真です。
すべての画像を読み取り、全体を**1つにまとめて**整理してください。

- title: 全体のタイトル、または内容から推測される見出し
- summary: 重要なポイントの箇条書き（配列。1枚なら3つ程度、複数枚なら3〜5つ）
- details: 画像内の**正確に記録すべき事実**をラベルと値で抽出（配列）。
  会合・イベント・セミナー・面談などの案内の場合は【日時】【場所】【会場/住所】【主催・連絡先】【締切】【参加費】などを、
  **原文の表記を変えず正確に**入れる（例: {"label":"日時","value":"7月3日(木) 14:00〜16:00"}）。
  本・記事でも日付・金額・固有名詞・締切など重要な確定情報があれば入れる。該当が無ければ空配列。
- nextAction: この内容を踏まえた具体的な次の行動アドバイス

日本語で出力してください。日時・場所・金額などは推測で補わず、書かれているとおりに正確に。`;

const responseSchema: Schema = {
  type: SchemaType.OBJECT,
  properties: {
    title: { type: SchemaType.STRING },
    summary: {
      type: SchemaType.ARRAY,
      items: { type: SchemaType.STRING },
    },
    details: {
      type: SchemaType.ARRAY,
      items: {
        type: SchemaType.OBJECT,
        properties: {
          label: { type: SchemaType.STRING },
          value: { type: SchemaType.STRING },
        },
        required: ["label", "value"],
      },
    },
    nextAction: { type: SchemaType.STRING },
  },
  required: ["title", "summary", "details", "nextAction"],
};

const ALLOWED_MIME = ["image/jpeg", "image/png", "image/webp"];

type Img = { data: string; mimeType: string };

/** data URL or 生base64 を {data, mimeType} に分解。失敗時 null */
function parseImage(raw: string): Img | null {
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
    return Response.json(
      { error: "サーバーに GEMINI_API_KEY が設定されていません" },
      { status: 500 }
    );
  }

  let rawImages: string[] = [];
  try {
    const body = await request.json();
    if (Array.isArray(body?.images)) {
      rawImages = body.images.filter((x: unknown) => typeof x === "string");
    } else if (typeof body?.image === "string") {
      rawImages = [body.image]; // 後方互換（単一画像）
    }
  } catch {
    return Response.json({ error: "リクエストが不正です" }, { status: 400 });
  }

  if (rawImages.length === 0) {
    return Response.json({ error: "画像がありません" }, { status: 400 });
  }
  if (rawImages.length > MAX_IMAGES) {
    return Response.json(
      { error: `画像は最大${MAX_IMAGES}枚までです` },
      { status: 400 }
    );
  }

  const images: Img[] = [];
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
    const model = getModel();
    const result = await model.generateContent({
      contents: [
        {
          role: "user",
          parts: [
            ...images.map((img) => ({
              inlineData: { data: img.data, mimeType: img.mimeType },
            })),
            { text: IMAGE_PROMPT },
          ],
        },
      ],
      generationConfig: {
        responseMimeType: "application/json",
        responseSchema,
        temperature: 0.2,
      },
    });
    const data = parseJsonResponse(result.response.text());
    return Response.json(data);
  } catch (err) {
    console.error("[/api/analyze-image]", err);
    return Response.json(
      { error: "画像の解析に失敗しました。枚数を減らすか別の画像でお試しください。" },
      { status: 502 }
    );
  }
}
