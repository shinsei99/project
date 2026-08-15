"""06 AIボイスジェネレーター

役割: スライド1枚ごとのナレーション音声を作る。
使用: OpenAI TTS API / ElevenLabs API / gTTS（無料・キー不要）
      いずれも使えない場合は、尺だけ合わせた無音WAVを作る（動画工程を止めないため）。
"""
from __future__ import annotations

import subprocess
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.base_agent import BaseAgent, register
from core.config import get_settings
from core.context import JobContext

CHARS_PER_SECOND = 5.5  # 日本語の読み上げ速度の目安（実測に近い値）


@register
class VoiceAgent(BaseAgent):
    key = "voice"
    name_ja = "AIボイス"
    role_ja = "ナレーション音声の合成"
    icon = "🔊"
    uses = "OpenAI TTS / ElevenLabs / gTTS"
    depends_on = ("supervisor",)
    deliverable = "audio"

    def _run(self, ctx: JobContext) -> Dict[str, Any]:
        st = get_settings()
        deck = ctx.state.get("deck")
        if not deck:
            return {"summary": "原稿がまだ無いため、音声は作っていません", "degraded": True}

        backend = _decide_backend(st)
        if backend == "silent":
            self.note_degraded(ctx, "音声合成に使えるものがありません（gTTS未導入・キー未設定）")
        else:
            self.log(ctx, "%s でナレーションを合成します" % backend.upper())

        out_dir = ctx.dir("audio")
        records: List[Dict[str, Any]] = []
        slides = deck["slides"]
        used_fallback = 0

        for i, slide in enumerate(slides, start=1):
            text = (slide.get("narration") or slide.get("title") or "").strip()
            self.progress(ctx, "%d枚目のナレーションを合成しています（%d文字）"
                          % (slide["no"], len(text)), current=i, total=len(slides))
            dest_base = out_dir / ("narration_%02d" % slide["no"])
            path, actual = self._synthesize(backend, text, dest_base, ctx)
            if actual == "silent" and backend != "silent":
                used_fallback += 1
            duration = _probe_duration(path) or _estimate_seconds(text)
            records.append({"slide_no": slide["no"], "path": ctx.rel(path),
                            "seconds": round(duration, 2), "backend": actual,
                            "chars": len(text)})
            ctx.add_artifact("audio", path, label="%d枚目のナレーション" % slide["no"],
                             agent=self.key, seconds=round(duration, 2), backend=actual)

        ctx.state["audio"] = records
        total_sec = sum(r["seconds"] for r in records)
        return {
            "summary": "ナレーション %d本（合計 %d分%02d秒）を作りました"
                       % (len(records), int(total_sec // 60), int(total_sec % 60)),
            "detail": "無音で代用: %d本" % used_fallback if used_fallback else "",
            "data": {"audio": records, "total_seconds": round(total_sec, 2)},
            "degraded": backend == "silent" or used_fallback > 0,
        }

    def _synthesize(self, backend: str, text: str, dest_base: Path, ctx: JobContext):
        """戻り値: (生成したファイルパス, 実際に使ったバックエンド名)"""
        if backend != "silent" and text:
            try:
                if backend == "openai":
                    dest = dest_base.with_suffix(".mp3")
                    _openai_tts(text, dest)
                    return dest, "openai"
                if backend == "elevenlabs":
                    dest = dest_base.with_suffix(".mp3")
                    _elevenlabs_tts(text, dest)
                    return dest, "elevenlabs"
                if backend == "gtts":
                    dest = dest_base.with_suffix(".mp3")
                    _gtts_tts(text, dest)
                    return dest, "gtts"
            except Exception as exc:
                self.log(ctx, "音声合成に失敗したため無音で代用します（%s）" % exc, level="warn")
        dest = dest_base.with_suffix(".wav")
        _silent_wav(dest, _estimate_seconds(text))
        return dest, "silent"


def _decide_backend(st) -> str:
    choice = st.tts_backend
    available = {
        "openai": bool(st.openai_key) and _module("openai"),
        "elevenlabs": bool(st.elevenlabs_key) and _module("requests"),
        "gtts": _module("gtts"),
    }
    if choice in ("openai", "elevenlabs", "gtts"):
        return choice if available.get(choice) else "silent"
    if choice == "silent":
        return "silent"
    for name in ("openai", "elevenlabs", "gtts"):
        if available[name]:
            return name
    return "silent"


def _module(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


def _openai_tts(text: str, dest: Path) -> None:
    from openai import OpenAI  # type: ignore

    st = get_settings()
    client = OpenAI(api_key=st.openai_key, timeout=float(st.llm_timeout))
    resp = client.audio.speech.create(model=st.openai_tts_model,
                                      voice=st.openai_tts_voice, input=text)
    resp.stream_to_file(str(dest))


def _elevenlabs_tts(text: str, dest: Path) -> None:
    import requests  # type: ignore

    st = get_settings()
    resp = requests.post(
        "https://api.elevenlabs.io/v1/text-to-speech/%s" % st.elevenlabs_voice_id,
        headers={"xi-api-key": st.elevenlabs_key, "Content-Type": "application/json"},
        json={"text": text, "model_id": "eleven_multilingual_v2",
              "voice_settings": {"stability": 0.5, "similarity_boost": 0.7}},
        timeout=180,
    )
    resp.raise_for_status()
    dest.write_bytes(resp.content)


def _gtts_tts(text: str, dest: Path) -> None:
    from gtts import gTTS  # type: ignore

    st = get_settings()
    gTTS(text=text, lang=st.tts_lang).save(str(dest))


def _silent_wav(dest: Path, seconds: float, rate: int = 22050) -> None:
    """無音WAV。動画側で尺を確保するためだけのもの。"""
    frames = int(max(seconds, 1.0) * rate)
    with wave.open(str(dest), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"\x00\x00" * frames)


def _estimate_seconds(text: str) -> float:
    return max(len(text) / CHARS_PER_SECOND, 2.0)


def _probe_duration(path: Path) -> Optional[float]:
    """ffmpeg で実際の尺を測る。ffmpeg が無い場合は None（推定値にフォールバック）。"""
    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path)) as wf:
                return wf.getnframes() / float(wf.getframerate())
        except Exception:
            return None
    binary = _ffmpeg_binary()
    if not binary:
        return None
    try:
        proc = subprocess.run([binary, "-i", str(path)], capture_output=True,
                              text=True, timeout=60)
        for line in proc.stderr.splitlines():
            if "Duration:" in line:
                stamp = line.split("Duration:")[1].split(",")[0].strip()
                hours, minutes, seconds = stamp.split(":")
                return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except Exception:
        return None
    return None


def _ffmpeg_binary() -> Optional[str]:
    """システムに ffmpeg が無くても imageio-ffmpeg 同梱のものを使う。"""
    import shutil as _shutil

    found = _shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None
