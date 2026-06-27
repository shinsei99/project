import { SchemaType, type Schema } from "@google/generative-ai";
import {
  getModel,
  hasApiKey,
  checkAccessCode,
  parseJsonResponse,
} from "@/lib/gemini";

export const runtime = "nodejs";
export const maxDuration = 60;

const SYSTEM_PROMPT = `あなたは優秀な思考整理アシスタントです。
ユーザーが頭の中から吐き出した雑多な文章（ブレイン・ダンプ）を解析し、以下を出力してください。

- title: この内容全体を表す短いタイトル（15文字程度。一覧で見て中身が分かるもの）
- tasks: やるべきこと。それぞれ簡潔な要約(summary)と「次に起こすべき最初のアクション(nextAction)」
- ideas: ひらめき・アイデア・やってみたいこと（簡潔な文の配列）
- business: 仕事・事業・お金・取引・キャリアに関すること（簡潔な文の配列）
- others: 上記いずれにも当てはまらないもの（感情・日常・雑記など。簡潔な文の配列）

該当する項目がなければ空配列にしてください。日本語で簡潔に。`;

const responseSchema: Schema = {
  type: SchemaType.OBJECT,
  properties: {
    title: { type: SchemaType.STRING },
    tasks: {
      type: SchemaType.ARRAY,
      items: {
        type: SchemaType.OBJECT,
        properties: {
          summary: { type: SchemaType.STRING },
          nextAction: { type: SchemaType.STRING },
        },
        required: ["summary", "nextAction"],
      },
    },
    ideas: { type: SchemaType.ARRAY, items: { type: SchemaType.STRING } },
    business: { type: SchemaType.ARRAY, items: { type: SchemaType.STRING } },
    others: { type: SchemaType.ARRAY, items: { type: SchemaType.STRING } },
  },
  required: ["title", "tasks", "ideas", "business", "others"],
};

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

  let text = "";
  try {
    const body = await request.json();
    text = typeof body?.text === "string" ? body.text.trim() : "";
  } catch {
    return Response.json({ error: "リクエストが不正です" }, { status: 400 });
  }
  if (!text) {
    return Response.json({ error: "テキストが空です" }, { status: 400 });
  }

  try {
    const model = getModel();
    const result = await model.generateContent({
      contents: [{ role: "user", parts: [{ text: `${SYSTEM_PROMPT}\n\n---\n${text}` }] }],
      generationConfig: {
        responseMimeType: "application/json",
        responseSchema,
        temperature: 0.4,
      },
    });
    const data = parseJsonResponse(result.response.text());
    return Response.json(data);
  } catch (err) {
    console.error("[/api/analyze]", err);
    return Response.json(
      { error: "AI解析に失敗しました。しばらくして再試行してください。" },
      { status: 502 }
    );
  }
}
