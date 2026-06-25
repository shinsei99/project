import Anthropic from "@anthropic-ai/sdk";
import { FloorPlanJSON } from "./types";

const client = new Anthropic();

const SYSTEM_PROMPT = `あなたは不動産間取り図を解析する専門AIです。
提供された間取り図画像を詳細に解析し、指定されたJSONフォーマットで構造化データを返してください。

## 重要な規則
- 座標はすべて 0〜100 の正規化グリッド（画像の幅・高さを100として）で指定する
- polygonは必ず時計回りで頂点を列挙する
- 部屋名は画像内の表記をそのまま使用する（例: "LDK", "洋室6帖", "WIC"）
- 回答はJSONのみ。説明文は不要。

## 出力フォーマット
{
  "canvas": { "width": 100, "height": 100 },
  "rooms": [
    {
      "id": "room_1",
      "name": "LDK",
      "type": "living",
      "size": "16.5帖",
      "polygon": [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
    }
  ],
  "walls": [
    { "from": [x1,y1], "to": [x2,y2], "type": "outer" }
  ],
  "pillars": [
    { "x": 0, "y": 0, "width": 3, "height": 3 }
  ],
  "equipment": [
    { "type": "toilet", "x": 10, "y": 20, "width": 5, "height": 8, "rotation": 0 }
  ],
  "doors": [
    { "x": 15, "y": 30, "width": 8, "rotation": 90, "swing": "left" }
  ],
  "windows": [
    { "x": 0, "y": 20, "width": 15, "rotation": 0 }
  ],
  "labels": [],
  "compass": { "x": 90, "y": 90, "angle": 0 },
  "scale": "1:100"
}

## typeの値
- rooms.type: "living" | "dining" | "kitchen" | "bedroom" | "storage" | "bathroom" | "toilet" | "entrance" | "corridor" | "balcony" | "other"
- walls.type: "outer"（外壁）| "inner"（間仕切り）| "pillar"（柱・梁）
- equipment.type: "toilet" | "bath" | "sink" | "kitchen_sink" | "stove" | "washing_machine" | "other"
- doors.swing: "left" | "right"（開き方向）`;

export async function analyzeFloorPlan(
  base64Image: string,
  mediaType: "image/jpeg" | "image/png" | "image/webp"
): Promise<FloorPlanJSON> {
  const response = await client.messages.create({
    model: "claude-sonnet-4-6",
    max_tokens: 4096,
    system: SYSTEM_PROMPT,
    messages: [
      {
        role: "user",
        content: [
          {
            type: "image",
            source: {
              type: "base64",
              media_type: mediaType,
              data: base64Image,
            },
          },
          {
            type: "text",
            text: "この間取り図を解析し、指定されたJSONフォーマットで出力してください。壁・部屋・設備・ドア・窓をすべて抽出してください。",
          },
        ],
      },
    ],
  });

  const content = response.content[0];
  if (content.type !== "text") {
    throw new Error("Unexpected response type from Claude");
  }

  // Extract JSON from response (may be wrapped in ```json blocks)
  const text = content.text;
  const jsonMatch = text.match(/```json\s*([\s\S]*?)\s*```/) || text.match(/(\{[\s\S]*\})/);
  if (!jsonMatch) {
    throw new Error("Could not extract JSON from response");
  }

  try {
    return JSON.parse(jsonMatch[1]) as FloorPlanJSON;
  } catch {
    throw new Error(`Failed to parse JSON: ${jsonMatch[1].substring(0, 200)}`);
  }
}
