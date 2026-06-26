"""Gemini image-to-image で間取り図を白黒図面に変換する。"""
from __future__ import annotations

import io

from google import genai
from google.genai import types
from PIL import Image

from config import GEMINI_API_KEY

client = genai.Client(api_key=GEMINI_API_KEY)

# ── 図面タイプ別の追加ルール ──────────────────────────────────────────────────

TYPE_RULES = {
    "マンション": """
- Emphasize corner structural pillars (マンション柱): solid filled black squares at all corners and wall junctions
- Include PS (パイプスペース) and MB (メーターボックス) labels
- Balcony (バルコニー) has thin border and white fill
- 浴室 and 洗面室 are always separate adjacent rooms — label both
""",
    "戸建て": """
- Include staircase (階段) with step lines if present
- Include entrance (玄関) with step/platform indication
- Garden/parking area (庭・駐車場) if shown: thin border, white fill, label
- No structural pillars (柱) unless explicitly shown
- Include 和室 (Japanese-style room) with tatami lines if present
""",
    "1K・1R": """
- Very simple layout: one main room + bathroom/kitchen unit
- Kitchen counter along wall: sink rectangle + stove circles
- Unit bath (ユニットバス): single rectangle with bathtub oval + toilet oval inside
- Compact layout — preserve exact proportions carefully
""",
    "その他": "",
}

BASE_PROMPT = """## RULE 1 — TRACING OPERATION (NOT DESIGN)
You must trace the original spatial layout exactly.
Every room, wall, door, and equipment item must stay in its EXACT original position and size.
Do NOT rearrange, move, add, or omit ANY element. Do NOT apply your own design preferences.

## RULE 2 — STYLE CONVERSION ONLY
Change ONLY the visual style: colors → black & white, simplified icons, clean fonts.
Spatial structure must be 100% identical to the input.

## RULE 3 — ROOM LABELING (MANDATORY)
Label EVERY room with its exact Japanese name from the original.
NEVER merge two separate rooms into one label.
- 浴室 and 洗面室 are ALWAYS separate rooms with separate labels
- 物入 and クローゼット are separate rooms
- All storage spaces must be individually labeled

## RULE 4 — EQUIPMENT POSITION (MANDATORY)
Place ALL equipment in the EXACT same position as the original.
Kitchen equipment (sink + stove) belongs ONLY inside the LDK/kitchen area — NEVER in bedrooms.
Do NOT relocate any equipment based on "typical" floor plan assumptions.

## RULE 5 — VISUAL STYLE
- Background: pure white
- Outer walls: thick solid black lines
- Interior partition walls: medium black lines
- All room fills: white (remove ALL color — no orange, tan, blue, gray, green)
- Room labels: copy EXACTLY as shown in the original image
  * If original shows name only (e.g. "玄関", "トイレ"): write just the name
  * If original shows name+size as one combined label (e.g. "洋室6帖"): write as ONE line — do NOT add a separate size line below
  * If original shows name and size on separate lines (e.g. "LDK" above "11.9帖"): write them on two separate lines
  * NEVER duplicate: if "6帖" is already inside the label, do NOT add "6帖" again below it
- Equipment icons (ultra-simplified):
  * Toilet: rectangle + oval bowl
  * Bathtub: rectangle + oval tub
  * Sink/洗面台: rectangle + circle
  * Kitchen: counter rectangle + sink box + 3 stove circles
  * Washing machine: rectangle + large circle
- Doors: straight line + quarter-circle arc (dashed)
- Windows: three parallel lines across wall
- PS / MB / 棚: keep as small text labels

## RULE 6 — NO ORIENTATION / COMPASS (MANDATORY)
NEVER draw any compass, north arrow, or orientation symbol (方位記号・北マーク・"N" arrow).
This applies EVEN IF the original drawing contains one — omit it entirely.
Do NOT add letters N/E/S/W, do NOT add any directional arrow or compass circle anywhere in the output.
"""


def analyze_from_maisoku(image: Image.Image, floor_type: str = "マンション") -> bytes:
    """マイソク全体画像 → 間取り図を見つけて白黒引き直し。"""
    img = image.copy()
    if img.width > 1400:
        r = 1400 / img.width
        img = img.resize((1400, int(img.height * r)), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    img_bytes = buf.getvalue()

    type_rules = TYPE_RULES.get(floor_type, "")

    prompt = f"""This image is a Japanese real estate flyer (マイソク/物件チラシ).
It contains a building photo, a street map, property details text, AND a floor plan diagram (間取り図).

STEP 1 — Locate the floor plan diagram (間取り図): the top-down architectural drawing showing room shapes and labels like 洋室・LDK・浴室・トイレ・バルコニー・玄関. Ignore the building exterior photo, the street/area map, and all text blocks.

STEP 2 — Redraw ONLY that floor plan as a clean black-and-white floor plan using the rules below.

{BASE_PROMPT}
## FLOOR TYPE: {floor_type}
{type_rules}"""

    response = client.models.generate_content(
        model="gemini-3.1-flash-image",
        contents=[
            types.Part(inline_data=types.Blob(mime_type="image/jpeg", data=img_bytes)),
            types.Part(text=prompt),
        ],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        ),
    )

    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            return part.inline_data.data

    texts = [p.text for p in response.candidates[0].content.parts if p.text]
    raise RuntimeError("画像が生成されませんでした。\n" + "\n".join(texts)[:300])


def _resize_and_encode(image: Image.Image) -> bytes:
    img = image.copy()
    if img.width > 1400:
        r = 1400 / img.width
        img = img.resize((1400, int(img.height * r)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def analyze(
    image: Image.Image,
    floor_type: str = "マンション",
    correction: str = "",
    prev_result: bytes | None = None,
) -> bytes:
    """
    image: 元のカラー間取り図（初回生成 / 参照用）
    floor_type: 図面タイプ
    correction: 修正指示（空文字なら初回生成）
    prev_result: 前回の生成結果バイト列（リトライ時に渡すと前回画像をベースにする）
    """
    type_rules = TYPE_RULES.get(floor_type, "")

    if correction and prev_result:
        # リトライ：前回の白黒図面をベースに、指定箇所だけ修正
        prev_img = Image.open(io.BytesIO(prev_result)).convert("RGB")
        img_bytes = _resize_and_encode(prev_img)
        prompt = f"""This is a black-and-white floor plan that was already generated.
Make ONLY the following correction and leave everything else EXACTLY as-is:

"{correction}"

Do NOT redraw, restyle, or move anything that is not mentioned above.
Keep all room labels, wall positions, icons, and proportions identical to this image.
Output the corrected floor plan in the same black-and-white style."""

    elif correction:
        # prev_result なしのリトライ（フォールバック：元画像から再生成）
        img_bytes = _resize_and_encode(image)
        prompt = f"""Redraw this floor plan as a clean black-and-white floor plan.
Apply this correction: "{correction}"

{BASE_PROMPT}
## FLOOR TYPE: {floor_type}
{type_rules}"""

    else:
        # 初回生成
        img_bytes = _resize_and_encode(image)
        prompt = f"""Redraw this floor plan as a clean black-and-white floor plan.

{BASE_PROMPT}
## FLOOR TYPE: {floor_type}
{type_rules}"""

    response = client.models.generate_content(
        model="gemini-3.1-flash-image",
        contents=[
            types.Part(inline_data=types.Blob(mime_type="image/jpeg", data=img_bytes)),
            types.Part(text=prompt),
        ],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        ),
    )

    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            return part.inline_data.data

    texts = [p.text for p in response.candidates[0].content.parts if p.text]
    raise RuntimeError("画像が生成されませんでした。\n" + "\n".join(texts)[:300])
