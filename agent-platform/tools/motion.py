"""アイテム: 写真を動かす（Veo 画像→動画）

**有料です。** Veo は無料枠では使えず、秒単位で課金される（2026-08-14 実測で疎通確認）。
  Veo 3.1 標準 $0.40/秒 ／ fast $0.10/秒 ／ lite $0.05/秒（いずれも720p）
  8秒のクリップ = 標準$3.20 / fast$0.80 / lite$0.40

そのため既定はオフ。使うときも「1枚目だけ動かす」（hero）を勧める。
無料で動きを付けたいだけなら、動画部隊のケンバーンズ（ゆっくりズーム/パン）で足りる。
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional, Tuple

NAME = "motion"
LABEL = "写真を動かす（Veo・有料）"
DESCRIPTION = ("静止写真から数秒の動画を生成する。実写真がそのまま動くので印象が変わるが、"
               "秒単位の課金なので使いどころを絞ること")

MODELS = {"lite": "veo-3.1-lite-generate-preview",
          "fast": "veo-3.1-fast-generate-preview",
          "standard": "veo-3.1-generate-preview"}
PRICE_PER_SECOND_720P = {"lite": 0.05, "fast": 0.10, "standard": 0.40}

DEFAULT_PROMPT = ("Slow, subtle cinematic camera movement on this scene. "
                  "Keep the subject unchanged and realistic. "
                  "No text, no captions, no people appearing.")


def available() -> Tuple[bool, str]:
    from core.config import get_settings

    st = get_settings()
    if not st.allow_paid:
        return False, "**有料のため既定で無効**（使うなら .env で AP_ALLOW_PAID=1）"
    if not st.gemini_key:
        return False, "Geminiキーが必要です"
    try:
        import google.genai  # noqa: F401
    except Exception:
        return False, "google-genai 未導入"
    return True, "有料（720p: lite $0.05/秒・fast $0.10/秒）。既定はオフ"


def estimate_cost(seconds: float, tier: str = "fast") -> float:
    return round(seconds * PRICE_PER_SECOND_720P.get(tier, 0.10), 2)


def animate(image_path, out_path, prompt: Optional[str] = None, tier: str = "fast",
            timeout: int = 600, poll: int = 10) -> Path:
    """静止画から動画を作る。生成には実測で40〜60秒かかる。

    **課金される。** AP_ALLOW_PAID=1 でないと実行しない。
    実在物件の広告には使わないこと（実測で元の写真に無い建物を作り出した）。
    """
    from core.config import get_settings

    if not get_settings().allow_paid:
        raise RuntimeError("有料機能は無効です（.env の AP_ALLOW_PAID=1 で解禁）")
    from google import genai
    from google.genai import types

    from core.config import get_settings

    st = get_settings()
    client = genai.Client(api_key=st.gemini_key)
    image_path = Path(image_path)
    suffix = image_path.suffix.lower()
    mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"

    operation = client.models.generate_videos(
        model=MODELS.get(tier, MODELS["fast"]),
        prompt=prompt or DEFAULT_PROMPT,
        image=types.Image(image_bytes=image_path.read_bytes(), mime_type=mime),
    )
    started = time.time()
    while not operation.done:
        if time.time() - started > timeout:
            raise TimeoutError("Veoの生成が%d秒を超えました" % timeout)
        time.sleep(poll)
        operation = client.operations.get(operation)

    videos = getattr(operation.response, "generated_videos", None) or []
    if not videos:
        raise RuntimeError("動画が返ってきませんでした")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    client.files.download(file=videos[0].video)
    videos[0].video.save(str(out_path))
    return out_path
