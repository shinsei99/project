import { NextRequest, NextResponse } from "next/server";
import { analyzeFloorPlan } from "@/lib/analyzer";
import { renderSVG } from "@/lib/renderer";

export const maxDuration = 60;

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const file = formData.get("image") as File | null;

    if (!file) {
      return NextResponse.json({ error: "画像ファイルが必要です" }, { status: 400 });
    }

    const allowedTypes = ["image/jpeg", "image/png", "image/webp"];
    if (!allowedTypes.includes(file.type)) {
      return NextResponse.json({ error: "JPEG / PNG / WebP のみ対応しています" }, { status: 400 });
    }

    const arrayBuffer = await file.arrayBuffer();
    const base64 = Buffer.from(arrayBuffer).toString("base64");

    const mediaType = file.type as "image/jpeg" | "image/png" | "image/webp";
    const floorPlanData = await analyzeFloorPlan(base64, mediaType);
    const svg = renderSVG(floorPlanData);

    return NextResponse.json({ svg, data: floorPlanData });
  } catch (err) {
    console.error(err);
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
