import Anthropic from "@anthropic-ai/sdk";
import { GoogleGenerativeAI, SchemaType, type Schema } from "@google/generative-ai";

/**
 * 食事写真の栄養推定を行うAIレイヤー。
 *
 * 環境変数 AI_PROVIDER で "gemini"（既定）/ "claude" を切り替える。
 * APIキーはサーバー側の環境変数からのみ読み込む（クライアントには絶対に出さない）。
 *
 * - gemini … GEMINI_API_KEY / GEMINI_MODEL（brain-dump と同じスキーム。無料枠が大きい）
 * - claude … ANTHROPIC_API_KEY / CLAUDE_MODEL（Anthropic API。従量課金）
 *   ※ 見積書アプリ等で使っている `claude` CLI はMacローカル専用で、
 *     Vercel などのサーバー上では動かないためAPI経由にしている。
 */

export type Provider = "gemini" | "claude";

export const PROVIDER: Provider =
  process.env.AI_PROVIDER?.trim().toLowerCase() === "claude" ? "claude" : "gemini";

const GEMINI_KEY = process.env.GEMINI_API_KEY?.trim() ?? "";
const ANTHROPIC_KEY = process.env.ANTHROPIC_API_KEY?.trim() ?? "";

export const GEMINI_MODEL = process.env.GEMINI_MODEL?.trim() || "gemini-2.5-flash";
export const CLAUDE_MODEL = process.env.CLAUDE_MODEL?.trim() || "claude-opus-5";

/** 選択中のプロバイダのAPIキーが設定されているか。未設定ならルート側で 500 を返す。 */
export const hasApiKey = PROVIDER === "claude" ? ANTHROPIC_KEY.length > 0 : GEMINI_KEY.length > 0;

/** 未設定時にユーザーへ返すメッセージ。 */
export const missingKeyMessage =
  PROVIDER === "claude"
    ? "サーバーに ANTHROPIC_API_KEY が設定されていません"
    : "サーバーに GEMINI_API_KEY が設定されていません";

/* ---------------- 共通の型と入出力 ---------------- */

export type MealItem = { name: string; calories: number };

export type MealAnalysis = {
  is_food: boolean;
  food_name: string;
  calories: number;
  protein: number;
  fat: number;
  carbs: number;
  items: MealItem[];
  portion_note: string;
  confidence: "high" | "medium" | "low";
  comment: string;
};

export type InputImage = { data: string; mimeType: string };

export const PROMPT = `あなたは日本の管理栄養士です。添付された食事の写真（1枚以上。複数枚なら同じ一食を別角度で撮ったもの）を見て、この一食分の栄養を推定してください。

守ること:
- is_food: 料理・飲み物が写っていれば true。食べ物でない写真なら false にし、他の数値は0、commentに「食事の写真を撮ってください」と入れる。
- food_name: 日本語の料理名。複数品なら「唐揚げ定食（ごはん・味噌汁付き）」のように一食をまとめた名前にする。
- items: 皿ごと・品目ごとの内訳（名前と推定カロリー）。単品なら1件でよい。
- 分量は皿・箸・スプーン・コップ・手など写っているものと比較して現実的に推定する。写真に写っている量だけを数える（皿の外は数えない）。
- calories は kcal、protein / fat / carbs は g。いずれも整数。一般的な日本の食事として妥当な値にする。
- portion_note: 分量をどう見積もったかを一言で（例「ごはん茶碗1杯150g程度と推定」）。
- confidence: 推定の自信度 "high" | "medium" | "low"。判別しにくい料理や、隠れて見えない具材が多い場合は low。
- comment: ダイエット中の人へ向けた30〜60字程度の短いアドバイス。責めずに前向きに。次の食事で調整する具体案があれば添える。

日本語で、指定のJSON形式のみを出力してください。`;

/* ---------------- 出力の正規化 ---------------- */

/** モデルが文字列や負値を返しても壊れないよう、0以上の整数に丸める。 */
function num(v: unknown): number {
  const n = typeof v === "number" ? v : Number(String(v ?? "").replace(/[^\d.-]/g, ""));
  return Number.isFinite(n) && n > 0 ? Math.round(n) : 0;
}

function normalize(raw: Record<string, unknown>): MealAnalysis {
  const items = Array.isArray(raw.items)
    ? (raw.items as Record<string, unknown>[])
        .map((it) => ({ name: String(it?.name ?? "").trim(), calories: num(it?.calories) }))
        .filter((it) => it.name)
    : [];
  const confidence = String(raw.confidence);
  return {
    is_food: raw.is_food !== false,
    food_name: String(raw.food_name ?? "").trim() || "料理",
    calories: num(raw.calories),
    protein: num(raw.protein),
    fat: num(raw.fat),
    carbs: num(raw.carbs),
    items,
    portion_note: String(raw.portion_note ?? "").trim(),
    confidence:
      confidence === "high" || confidence === "low" ? confidence : "medium",
    comment: String(raw.comment ?? "").trim(),
  };
}

/** モデルが返した JSON 文字列を安全にパースする（```json フェンス除去にも対応）。 */
function parseJson(rawText: string): Record<string, unknown> {
  let text = rawText.trim();
  if (text.startsWith("```")) {
    text = text.replace(/^```(?:json)?/i, "").replace(/```$/, "").trim();
  }
  return JSON.parse(text) as Record<string, unknown>;
}

/* ---------------- Gemini ---------------- */

const geminiSchema: Schema = {
  type: SchemaType.OBJECT,
  properties: {
    is_food: { type: SchemaType.BOOLEAN },
    food_name: { type: SchemaType.STRING },
    calories: { type: SchemaType.NUMBER },
    protein: { type: SchemaType.NUMBER },
    fat: { type: SchemaType.NUMBER },
    carbs: { type: SchemaType.NUMBER },
    items: {
      type: SchemaType.ARRAY,
      items: {
        type: SchemaType.OBJECT,
        properties: {
          name: { type: SchemaType.STRING },
          calories: { type: SchemaType.NUMBER },
        },
        required: ["name", "calories"],
      },
    },
    portion_note: { type: SchemaType.STRING },
    confidence: { type: SchemaType.STRING, format: "enum", enum: ["high", "medium", "low"] },
    comment: { type: SchemaType.STRING },
  },
  required: [
    "is_food",
    "food_name",
    "calories",
    "protein",
    "fat",
    "carbs",
    "items",
    "portion_note",
    "confidence",
    "comment",
  ],
};

async function analyzeWithGemini(images: InputImage[]): Promise<MealAnalysis> {
  const model = new GoogleGenerativeAI(GEMINI_KEY).getGenerativeModel({ model: GEMINI_MODEL });
  const result = await model.generateContent({
    contents: [
      {
        role: "user",
        parts: [
          ...images.map((img) => ({
            inlineData: { data: img.data, mimeType: img.mimeType },
          })),
          { text: PROMPT },
        ],
      },
    ],
    generationConfig: {
      responseMimeType: "application/json",
      responseSchema: geminiSchema,
      temperature: 0.2,
    },
  });
  return normalize(parseJson(result.response.text()));
}

/* ---------------- Claude（Anthropic API） ---------------- */

/** Structured Outputs 用スキーマ。全オブジェクトに additionalProperties:false が必要。 */
const claudeSchema = {
  type: "object",
  properties: {
    is_food: { type: "boolean" },
    food_name: { type: "string" },
    calories: { type: "integer" },
    protein: { type: "integer" },
    fat: { type: "integer" },
    carbs: { type: "integer" },
    items: {
      type: "array",
      items: {
        type: "object",
        properties: {
          name: { type: "string" },
          calories: { type: "integer" },
        },
        required: ["name", "calories"],
        additionalProperties: false,
      },
    },
    portion_note: { type: "string" },
    confidence: { type: "string", enum: ["high", "medium", "low"] },
    comment: { type: "string" },
  },
  required: [
    "is_food",
    "food_name",
    "calories",
    "protein",
    "fat",
    "carbs",
    "items",
    "portion_note",
    "confidence",
    "comment",
  ],
  additionalProperties: false,
} as const;

/** 安全性フィルタで解析が拒否されたときに投げるエラー（呼び出し側で文言を分ける）。 */
export class RefusalError extends Error {}

async function analyzeWithClaude(images: InputImage[]): Promise<MealAnalysis> {
  const client = new Anthropic({ apiKey: ANTHROPIC_KEY });
  const response = await client.beta.messages.create({
    model: CLAUDE_MODEL,
    max_tokens: 16000,
    // 安全性フィルタで拒否された場合にサーバー側で自動フォールバックさせる
    betas: ["server-side-fallback-2026-07-01"],
    fallbacks: "default",
    thinking: { type: "adaptive" },
    output_config: {
      effort: "medium",
      format: { type: "json_schema", schema: claudeSchema },
    },
    messages: [
      {
        role: "user",
        content: [
          ...images.map((img) => ({
            type: "image" as const,
            source: {
              type: "base64" as const,
              media_type: img.mimeType as "image/jpeg" | "image/png" | "image/webp",
              data: img.data,
            },
          })),
          { type: "text" as const, text: PROMPT },
        ],
      },
    ],
  });

  if (response.stop_reason === "refusal") {
    throw new RefusalError("この画像は解析できませんでした");
  }

  const text = response.content
    .filter((b): b is Anthropic.Beta.BetaTextBlock => b.type === "text")
    .map((b) => b.text)
    .join("");
  if (!text.trim()) throw new Error("Claude から空の応答が返りました");

  return normalize(parseJson(text));
}

/* ---------------- 入口 ---------------- */

export async function analyzeMeal(images: InputImage[]): Promise<MealAnalysis> {
  return PROVIDER === "claude" ? analyzeWithClaude(images) : analyzeWithGemini(images);
}
