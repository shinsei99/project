"""04 画像生成プロデューサー

役割: アイキャッチ／スライド背景／動画素材の画像を用意する。
使用: OpenAI DALL-E 3 API、または Stability AI API
      どちらのキーも無い場合は Pillow で自前のグラデーション画像を作る（縮退）。

ユーザーがアップロードした画像がある場合は、それを先頭のスライドから優先的に割り当て、
足りない分だけ生成する（せっかく渡された素材を無視しないため）。
"""
from __future__ import annotations

import base64
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.base_agent import BaseAgent, register
from core.config import get_settings
from core.context import JobContext
from core.fonts import load_font

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")
MAX_IMAGE_PARALLEL = 3   # 同時生成数。上げすぎるとAPIのレート制限に当たる
PALETTE = [
    ((18, 42, 88), (58, 116, 186)),
    ((26, 60, 74), (70, 150, 150)),
    ((60, 30, 70), (140, 90, 160)),
    ((70, 45, 25), (190, 140, 80)),
]


@register
class ImageGeneratorAgent(BaseAgent):
    key = "image"
    name_ja = "画像生成プロデューサー"
    role_ja = "アイキャッチ・スライド背景・動画素材の生成"
    icon = "🎨"
    uses = "OpenAI DALL-E 3 / Gemini画像 / Stability AI"
    depends_on = ("supervisor",)
    deliverable = "images"

    def _run(self, ctx: JobContext) -> Dict[str, Any]:
        st = get_settings()
        deck = ctx.state.get("deck")
        if not deck:
            return {"summary": "構成がまだ無いため、画像は作っていません", "degraded": True}

        slides = deck["slides"]
        uploaded = _uploaded_images(ctx)
        if uploaded:
            self.log(ctx, "アップロードされた画像 %d枚 を先に使います" % len(uploaded))

        backend = _decide_backend(st)
        # 実写真が渡っているなら生成しない。実在の物件・商品にAI画像を混ぜると
        # 不当表示になり得るうえ、1枚あたり数十秒を無駄にするため。
        if uploaded and len(uploaded) >= len(slides):
            backend = "stub"
            self.log(ctx, "実写真が%d枚あるので、画像生成はせず写真をそのまま使います"
                     % len(uploaded))
        elif backend == "stub" and not st.allow_paid:
            self.log(ctx, "画像生成は有料のため行いません。"
                          "写真をアップロードすると、それを使って組み立てます", level="warn")
        elif backend == "stub":
            self.note_degraded(ctx, "画像生成APIのキーが未設定です")
        else:
            self.log(ctx, "%s で画像を生成します（%d枚）" % (backend.upper(), len(slides)))

        out_dir = ctx.dir("images")

        def build(index_slide):
            """1枚分。並列で呼ばれるのでここでは共有状態を触らない。"""
            index, slide = index_slide
            no = slide["no"]
            dest = out_dir / ("slide_%02d.png" % no)
            self.progress(ctx, "%d枚目「%s」の画像を用意しています" % (no, slide["title"]),
                          current=index + 1, total=len(slides))
            if index < len(uploaded):
                shutil.copyfile(uploaded[index], dest)
                return {"slide_no": no, "path": ctx.rel(dest), "backend": "uploaded"}
            if backend != "stub" and self._generate(backend, slide, dest, ctx):
                return {"slide_no": no, "path": ctx.rel(dest), "backend": backend}
            _placeholder(dest, slide, index, st.video_size)
            return {"slide_no": no, "path": ctx.rel(dest), "backend": "stub"}

        # 画像生成は1枚あたり数十秒かかる。枚数分待つと致命的に遅いので同時に走らせる。
        # 同時数はAPIのレート制限を考えて控えめに。
        workers = min(MAX_IMAGE_PARALLEL, max(1, len(slides)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            records = list(pool.map(build, list(enumerate(slides))))
        records.sort(key=lambda r: r["slide_no"])

        generated = sum(1 for r in records if r["backend"] not in ("uploaded", "stub"))
        for record in records:
            ctx.add_artifact("image", ctx.root / record["path"],
                             label="%d枚目の画像" % record["slide_no"], agent=self.key,
                             backend=record["backend"])

        ctx.state["images"] = records
        degraded = generated == 0 and any(r["backend"] == "stub" for r in records)
        return {
            "summary": "画像 %d枚 を用意しました（生成 %d / 添付 %d / 簡易 %d）" % (
                len(records), generated,
                sum(1 for r in records if r["backend"] == "uploaded"),
                sum(1 for r in records if r["backend"] == "stub")),
            "data": {"images": records},
            "degraded": degraded,
        }

    # --- 生成本体 ---
    def _generate(self, backend: str, slide: Dict[str, Any], dest: Path,
                  ctx: JobContext) -> bool:
        prompt = slide.get("image_prompt") or slide.get("title", "")
        prompt = prompt + ", clean professional illustration, no text, no logos, no faces"
        try:
            if backend == "openai":
                return _openai_image(prompt, dest)
            if backend == "gemini":
                return _gemini_image(prompt, dest)
            if backend == "stability":
                return _stability_image(prompt, dest)
        except Exception as exc:
            self.log(ctx, "%d枚目の画像生成に失敗したため簡易画像に切り替えます（%s）"
                     % (slide["no"], exc), level="warn")
        return False


def _decide_backend(st) -> str:
    """使える画像生成の当てを決める。

    **重要（2026-08-14 確認）: 画像生成はどれも有料。**
      - Gemini の画像モデル（nano banana）は**無料枠なし**
      - DALL-E 3 / Stability も従量課金
    そのため既定では生成しない（AP_ALLOW_PAID=1 のときだけ生成する）。
    課金なしのときは、アップロードされた実写真＋簡易画像で組む。

    物件・商品のチラシではそもそも**実写真が必須**（AI画像は不当表示になる）ので、
    生成が止まっていて困る場面は実は少ない。
    """
    if not st.allow_paid:
        return "stub"
    keys = {"openai": bool(st.openai_key), "gemini": bool(st.gemini_key),
            "stability": bool(st.stability_key)}
    choice = st.image_backend
    if choice == "stub":
        return "stub"
    if choice in keys:
        return choice if keys[choice] else "stub"
    for name in ("openai", "gemini", "stability"):
        if keys[name]:
            return name
    return "stub"


def _openai_image(prompt: str, dest: Path) -> bool:
    from openai import OpenAI  # type: ignore

    st = get_settings()
    client = OpenAI(api_key=st.openai_key, timeout=float(st.llm_timeout))
    resp = client.images.generate(model=st.openai_image_model, prompt=prompt,
                                  size="1792x1024", quality="standard", n=1)
    item = resp.data[0]
    if getattr(item, "b64_json", None):
        dest.write_bytes(base64.b64decode(item.b64_json))
        return True
    if getattr(item, "url", None):
        import requests  # type: ignore

        r = requests.get(item.url, timeout=120)
        r.raise_for_status()
        dest.write_bytes(r.content)
        return True
    return False


def _gemini_image(prompt: str, dest: Path) -> bool:
    """Gemini の画像生成モデルを使う（madori-tracer と同じ新SDK・同じ呼び方）。

    テキストのみを渡し、返ってきた inline_data（画像バイト列）を保存する。
    """
    from google import genai  # type: ignore
    from google.genai import types  # type: ignore

    st = get_settings()
    # timeout はミリ秒。画像は生成に時間がかかるので長めに取るが、無制限にはしない
    client = genai.Client(api_key=st.gemini_key,
                          http_options=types.HttpOptions(timeout=st.image_timeout * 1000))
    resp = client.models.generate_content(
        model=st.gemini_image_model,
        contents=[types.Part(text=prompt)],
        config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
    )
    for part in resp.candidates[0].content.parts:
        if getattr(part, "inline_data", None) and part.inline_data.data:
            dest.write_bytes(part.inline_data.data)
            return True
    return False


def _stability_image(prompt: str, dest: Path) -> bool:
    import requests  # type: ignore

    st = get_settings()
    resp = requests.post(
        "https://api.stability.ai/v2beta/stable-image/generate/core",
        headers={"authorization": "Bearer %s" % st.stability_key, "accept": "image/*"},
        files={"none": ""},
        data={"prompt": prompt, "output_format": "png", "aspect_ratio": "16:9"},
        timeout=180,
    )
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    return True


# --- 縮退用のプレースホルダ画像 ---

def _placeholder(dest: Path, slide: Dict[str, Any], index: int, size) -> None:
    """APIが無くても後続（パワポ・動画）が動くように、必ず画像を1枚作る。"""
    try:
        from PIL import Image, ImageDraw  # type: ignore
    except Exception:
        dest.write_bytes(b"")
        return

    width, height = size
    top, bottom = PALETTE[index % len(PALETTE)]
    img = Image.new("RGB", (width, height), top)
    draw = ImageDraw.Draw(img)
    for y in range(height):
        ratio = y / max(height - 1, 1)
        draw.line(
            [(0, y), (width, y)],
            fill=(int(top[0] + (bottom[0] - top[0]) * ratio),
                  int(top[1] + (bottom[1] - top[1]) * ratio),
                  int(top[2] + (bottom[2] - top[2]) * ratio)),
        )
    font = load_font(int(height * 0.06))
    if font:
        text = slide.get("title", "")
        draw.text((int(width * 0.08), int(height * 0.42)), text, font=font,
                  fill=(255, 255, 255))
        small = load_font(int(height * 0.028))
        if small:
            draw.text((int(width * 0.08), int(height * 0.56)),
                      "※ 画像生成APIが未設定のため簡易画像です", font=small,
                      fill=(220, 226, 240))
    img.save(dest, "PNG")


def _uploaded_images(ctx: JobContext) -> List[Path]:
    return sorted(p for p in Path(ctx.dir("input")).glob("*")
                  if p.suffix.lower() in IMAGE_EXT)
