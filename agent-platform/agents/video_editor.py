"""07 動画プロデューサー・編集

役割: 画像素材とナレーション音声をタイムラインで同期させ、1本の .mp4 に合成する。
使用: moviepy + FFmpeg

前提メモ（このMacで確認したこと）:
  - システムに ffmpeg は入っていない → `imageio-ffmpeg` 同梱バイナリを使う
  - moviepy は v1系と v2系で API 名が違う（set_audio / with_audio 等）ため互換シムを持つ
  - moviepy が使えない場合は、ffmpeg コマンドを並べた render.sh を出力して手動実行できるようにする
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.base_agent import BaseAgent, register
from core.config import get_settings
from core.context import JobContext
from core.io_utils import slugify, write_text

MIN_SLIDE_SECONDS = 3.0


@register
class VideoEditorAgent(BaseAgent):
    key = "video"
    name_ja = "動画プロデューサー"
    role_ja = "画像と音声を同期させて解説動画(mp4)に合成する"
    icon = "🎬"
    uses = "moviepy + FFmpeg"
    depends_on = ("image", "voice")
    deliverable = "video"

    def _run(self, ctx: JobContext) -> Dict[str, Any]:
        st = get_settings()
        images = {r["slide_no"]: ctx.root / r["path"] for r in ctx.state.get("images", [])}
        audio = {r["slide_no"]: (ctx.root / r["path"], r["seconds"])
                 for r in ctx.state.get("audio", [])}
        if not images:
            return {"summary": "画像が無いため、動画は作っていません", "degraded": True}

        deck = ctx.state.get("deck", {})
        name = slugify(deck.get("title", "")) or "video"
        out_path = ctx.dir("video") / ("%s.mp4" % name)

        timeline = []
        for no in sorted(images):
            img = images[no]
            if not img.exists() or img.stat().st_size == 0:
                continue
            snd, seconds = audio.get(no, (None, 0))
            timeline.append({"no": no, "image": img, "audio": snd,
                             "seconds": max(float(seconds or 0), MIN_SLIDE_SECONDS)})
        if not timeline:
            return {"summary": "有効な素材が無いため、動画は作っていません", "degraded": True}

        total = sum(t["seconds"] for t in timeline)
        self.log(ctx, "%d カットの動画を合成します（想定 %d分%02d秒）"
                 % (len(timeline), int(total // 60), int(total % 60)))

        backend = st.video_backend
        if backend != "script":
            try:
                # 静止画＋音声なら ffmpeg に直接やらせる方が圧倒的に速い。
                # moviepy は Python 側で1フレームずつ合成するため、2分の動画に
                # 実測で8分以上かかっていた（Intel Mac・CPU 100%張り付き）。
                if backend in ("auto", "ffmpeg"):
                    self._render_with_ffmpeg(ctx, timeline, out_path, st)
                else:
                    self._render_with_moviepy(ctx, timeline, out_path, st)
                ctx.state["video"] = ctx.rel(out_path)
                ctx.add_artifact("video", out_path, label="解説動画", agent=self.key,
                                 seconds=round(total, 1))
                size_mb = out_path.stat().st_size / (1024 * 1024)
                return {
                    "summary": "解説動画を書き出しました（%d分%02d秒・%.1fMB）"
                               % (int(total // 60), int(total % 60), size_mb),
                    "detail": ctx.rel(out_path),
                    "data": {"path": ctx.rel(out_path), "seconds": round(total, 1)},
                }
            except Exception as exc:
                self.log(ctx, "高速な書き出しに失敗したため、moviepyで作り直します（%s）"
                         % str(exc)[:120], level="warn")
                self.log(ctx, repr(exc), level="debug")
                try:
                    self._render_with_moviepy(ctx, timeline, out_path, st)
                    ctx.state["video"] = ctx.rel(out_path)
                    ctx.add_artifact("video", out_path, label="解説動画", agent=self.key,
                                     seconds=round(total, 1))
                    return {
                        "summary": "解説動画を書き出しました（%d分%02d秒・%.1fMB）"
                                   % (int(total // 60), int(total % 60),
                                      out_path.stat().st_size / (1024 * 1024)),
                        "detail": ctx.rel(out_path),
                        "data": {"path": ctx.rel(out_path), "seconds": round(total, 1)},
                    }
                except Exception as exc2:
                    self.log(ctx, "動画合成に失敗したため、手動実行用のスクリプトを出力します（%s）"
                             % str(exc2)[:120], level="warn")

        script_path = self._write_ffmpeg_script(ctx, timeline, out_path)
        ctx.add_artifact("script", script_path, label="動画書き出しスクリプト", agent=self.key)
        return {
            "summary": "動画の書き出しは保留し、手動実行用スクリプトを出力しました",
            "detail": "bash %s で書き出せます" % ctx.rel(script_path),
            "data": {"script": ctx.rel(script_path)},
            "degraded": True,
        }

    # --- ffmpeg で直接書き出す（既定・速い） ---
    def _render_with_ffmpeg(self, ctx: JobContext, timeline: List[Dict[str, Any]],
                            out_path: Path, st) -> None:
        """1カットずつ ffmpeg で作って連結する。

        静止画を尺の分だけ引き伸ばす処理は ffmpeg の得意分野で、
        Python にフレームを作らせる moviepy より2桁速い。
        画像サイズがばらついていても scale+pad で統一するので連結できる。
        """
        binary = _ffmpeg_binary()
        if not binary:
            raise RuntimeError("ffmpeg が見つかりません")

        width, height = st.video_size
        volume = float(ctx.options.get("audio_volume", st.audio_volume))
        work = ctx.dir("video")
        parts = []

        motion = st.video_motion

        for i, cut in enumerate(timeline, start=1):
            self.progress(ctx, "%d番目のカットを書き出しています（%.1f秒）"
                          % (cut["no"], cut["seconds"]), current=i, total=len(timeline))
            part = work / (".part_%02d.mp4" % cut["no"])
            # **文字の入った面（スライド）は、動かすと端が切れる。**
            # ケンバーンズは写真のための手法で、文字には使えない
            # （見出しの左端が欠けた動画が実際に出た）
            vf = _motion_filter(motion, i, cut["seconds"], width, height,
                                st.video_fps, has_text=_is_text_slide(ctx, cut))
            cmd = [binary, "-y", "-loglevel", "error", "-loop", "1", "-i", str(cut["image"])]
            if cut["audio"] and Path(cut["audio"]).exists():
                cmd += ["-i", str(cut["audio"])]
            cmd += ["-t", "%.3f" % cut["seconds"], "-vf", vf,
                    "-r", str(st.video_fps), "-c:v", "libx264",
                    "-preset", st.video_preset, "-tune", "stillimage",
                    "-pix_fmt", "yuv420p"]
            if cut["audio"] and Path(cut["audio"]).exists():
                cmd += ["-c:a", "aac", "-b:a", "192k", "-ac", "2", "-ar", "44100"]
                if abs(volume - 1.0) > 0.01:
                    cmd += ["-filter:a", "volume=%.2f" % volume]
            else:
                # 音声トラックが無いカットが混ざると連結できないので無音を足す
                cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                        "-c:a", "aac", "-shortest"]
            cmd += [str(part)]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if proc.returncode != 0:
                raise RuntimeError((proc.stderr or "ffmpegが失敗").strip()[:300])
            parts.append(part)

        self.progress(ctx, "カットを1本につないでいます", current=len(timeline),
                      total=len(timeline))
        list_file = work / ".concat.txt"
        list_file.write_text("".join("file '%s'\n" % p.name for p in parts),
                             encoding="utf-8")
        tmp_path = out_path.with_name(".tmp_" + out_path.name)
        proc = subprocess.run(
            [binary, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
             "-i", str(list_file), "-c", "copy", str(tmp_path)],
            capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or "連結に失敗").strip()[:300])
        os.replace(str(tmp_path), str(out_path))

        for path in parts + [list_file]:
            try:
                path.unlink()
            except OSError:
                pass

    # --- moviepy 本体（逃げ道） ---
    def _render_with_moviepy(self, ctx: JobContext, timeline: List[Dict[str, Any]],
                             out_path: Path, st) -> None:
        ImageClip, AudioFileClip, concatenate = _import_moviepy()
        _ensure_ffmpeg_env()

        # 音量は 画面のスライダー > .env の AP_AUDIO_VOLUME > 1.0（原音） の順で決まる
        volume = float(ctx.options.get("audio_volume", st.audio_volume))
        if abs(volume - 1.0) > 0.01:
            self.log(ctx, "ナレーションの音量を %d%% にして合成します" % int(volume * 100))

        clips = []
        for i, cut in enumerate(timeline, start=1):
            self.progress(ctx, "%d番目のカットを組み立てています（%.1f秒）"
                          % (cut["no"], cut["seconds"]), current=i, total=len(timeline))
            clip = ImageClip(str(cut["image"]))
            clip = _with_duration(clip, cut["seconds"])
            if cut["audio"] and Path(cut["audio"]).exists():
                audio = _with_volume(AudioFileClip(str(cut["audio"])), volume)
                clip = _with_audio(clip, audio)
            clips.append(clip)

        self.progress(ctx, "動画ファイルを書き出しています（1〜数分かかります）",
                      current=len(timeline), total=len(timeline))
        final = concatenate(clips, method="compose")
        # 書き出し途中のファイルは moov atom が無く再生できない。
        # 一時名で書いてから rename し、「完成したものだけが最終パスに存在する」状態にする。
        # ※拡張子は .mp4 のまま保つこと。ffmpeg はファイル名からコンテナ形式を決めるため、
        #   `.part` などにすると "Unable to choose an output format" で落ちる（実際に踏んだ）。
        tmp_path = out_path.with_name(".tmp_" + out_path.name)
        final.write_videofile(
            str(tmp_path), fps=st.video_fps, codec="libx264", audio_codec="aac",
            preset=st.video_preset, threads=st.video_threads,
            logger=_progress_logger(self, ctx),
        )
        os.replace(str(tmp_path), str(out_path))
        for clip in clips:
            try:
                clip.close()
            except Exception:
                pass
        try:
            final.close()
        except Exception:
            pass

    # --- 逃げ道: ffmpeg コマンドを書き出す ---
    def _write_ffmpeg_script(self, ctx: JobContext, timeline, out_path: Path) -> Path:
        ffmpeg = _ffmpeg_binary() or "ffmpeg"
        lines = ["#!/bin/bash",
                 "# moviepy が使えない環境向け。ffmpeg で1カットずつ作って連結する。",
                 "set -e", 'cd "$(dirname "$0")/.."', ""]
        parts = []
        for cut in timeline:
            part = "video/part_%02d.mp4" % cut["no"]
            parts.append(part)
            if cut["audio"]:
                lines.append('"%s" -y -loop 1 -i "%s" -i "%s" -c:v libx264 -tune stillimage '
                             '-c:a aac -b:a 192k -pix_fmt yuv420p -shortest "%s"'
                             % (ffmpeg, ctx.rel(cut["image"]), ctx.rel(cut["audio"]), part))
            else:
                lines.append('"%s" -y -loop 1 -i "%s" -c:v libx264 -t %.2f -pix_fmt yuv420p "%s"'
                             % (ffmpeg, ctx.rel(cut["image"]), cut["seconds"], part))
        list_file = "video/parts.txt"
        concat_body = "\n".join("file '%s'" % Path(p).name for p in parts)
        lines += ["", "cat > %s <<'EOF'" % list_file, concat_body, "EOF", ""]
        lines += ['"%s" -y -f concat -safe 0 -i %s -c copy "%s"'
                  % (ffmpeg, list_file, ctx.rel(out_path)), "",
                  'echo "書き出し完了: %s"' % ctx.rel(out_path)]
        path = write_text(ctx.dir("video") / "render.sh", "\n".join(lines) + "\n")
        os.chmod(path, 0o755)
        return path


def _is_text_slide(ctx, cut) -> bool:
    """この絵は文字が主役か（作図したスライドか）。

    ビジュアル制作が「実写真（uploaded）」か「作図（card / stub）」かを
    記録しているので、それで判断する。分からないときは**安全側**（文字あり）に倒す。
    """
    name = Path(str(cut.get("image", ""))).name
    for record in (ctx.state.get("images") or []):
        if Path(str(record.get("path", ""))).name == name:
            return str(record.get("backend", "")) != "uploaded"
    return True


def _motion_filter(motion: str, index: int, seconds: float, width: int, height: int,
                   fps: int, has_text: bool = False) -> str:
    """1カット分の映像フィルタ。

    ケンバーンズ（ゆっくりズーム／パン）は、静止画に動きを付ける昔ながらの手法。
    **写真の中身は一切変わらない**ので、実在の物件・商品の広告で安全に使える。
    （AIの画像→動画生成は実測で元の写真に無い建物を作り出した。不動産広告では
      不当表示になるため使わない。しかも有料）
    """
    fit = ("scale=%d:%d:force_original_aspect_ratio=decrease,"
           "pad=%d:%d:(ow-iw)/2:(oh-ih)/2,setsar=1" % (width, height, width, height))
    if motion in ("off", "none", "static"):
        return fit

    frames = max(int(seconds * fps), 1)
    # 拡大してから切り出すことで、ズームしても画質が落ちないようにする
    base = ("scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d"
            % (width * 2, height * 2, width * 2, height * 2))

    if has_text:
        # 文字の面は**中心に向かってごく僅かに寄る**だけ。パンは禁止。
        # 1.18倍＋横パンで見出しの左端が切れた。1.03なら端の切れは1.5%で、
        # スライドの余白の中に収まる
        zoom_max = 1.03
        step = (zoom_max - 1.0) / frames
        expr = "z='min(zoom+%.6f,%.3f)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'" % (
            step, zoom_max)
        return ("%s,zoompan=%s:d=%d:s=%dx%d:fps=%d,setsar=1"
                % (base, expr, frames, width, height, fps))

    zoom_max = 1.18
    step = (zoom_max - 1.0) / frames

    # カットごとに動きを変える（全部同じ動きだと単調になるため）
    kind = index % 4
    if kind == 0:
        expr = "z='min(zoom+%.6f,%.3f)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'" % (
            step, zoom_max)
    elif kind == 1:
        expr = ("z='if(lte(zoom,1.0),%.3f,max(zoom-%.6f,1.0))':"
                "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'" % (zoom_max, step))
    elif kind == 2:
        expr = "z='%.3f':x='(iw-iw/zoom)*on/%d':y='ih/2-(ih/zoom/2)'" % (zoom_max, frames)
    else:
        expr = "z='%.3f':x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*on/%d'" % (zoom_max, frames)

    return ("%s,zoompan=%s:d=%d:s=%dx%d:fps=%d,setsar=1"
            % (base, expr, frames, width, height, fps))


def _progress_logger(agent, ctx):
    """moviepy の英語プログレスバーを、日本語の進捗メッセージに置き換える。

    proglog が無い / 形が変わった場合は None を返し、moviepy 既定の無表示に戻す。
    """
    try:
        from proglog import ProgressBarLogger  # type: ignore
    except Exception:
        return None

    class _JapaneseLogger(ProgressBarLogger):
        def __init__(self):
            super().__init__()
            # バーごとに別のカウンタを持つこと。1つで共用すると、先に走る音声が
            # 100%に達した時点で、続く映像の進捗が一切出なくなる（実際に踏んだ）。
            self._last = {}

        def bars_callback(self, bar, attr, value, old_value=None):
            if attr != "index":
                return
            total = (self.bars.get(bar) or {}).get("total") or 0
            if not total:
                return
            percent = int(value * 100 / total)
            if percent - self._last.get(bar, -10) < 10:
                return
            self._last[bar] = percent
            label = "音声を書き出しています" if bar == "chunk" else "映像を書き出しています"
            agent.progress(ctx, "%s（%d%%）" % (label, min(percent, 100)))

    return _JapaneseLogger()


# --- moviepy 互換シム -----------------------------------------------------

def _import_moviepy():
    try:  # moviepy v2 系
        from moviepy import (AudioFileClip, ImageClip,  # type: ignore
                             concatenate_videoclips)
    except Exception:  # moviepy v1 系
        from moviepy.editor import (AudioFileClip, ImageClip,  # type: ignore
                                    concatenate_videoclips)
    return ImageClip, AudioFileClip, concatenate_videoclips


def _with_duration(clip, seconds: float):
    if hasattr(clip, "with_duration"):
        return clip.with_duration(seconds)
    return clip.set_duration(seconds)


def _with_audio(clip, audio):
    if hasattr(clip, "with_audio"):
        return clip.with_audio(audio)
    return clip.set_audio(audio)


def _with_volume(audio, factor: float):
    """音量倍率をかける。moviepy v2 は with_volume_scaled、v1 は volumex。"""
    if abs(factor - 1.0) < 0.01:
        return audio
    if hasattr(audio, "with_volume_scaled"):
        return audio.with_volume_scaled(factor)
    if hasattr(audio, "volumex"):
        return audio.volumex(factor)
    return audio


def _ffmpeg_binary() -> Optional[str]:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _ensure_ffmpeg_env() -> None:
    """システムに ffmpeg が無い環境で moviepy に同梱バイナリを使わせる。"""
    if shutil.which("ffmpeg"):
        return
    binary = _ffmpeg_binary()
    if binary:
        os.environ.setdefault("IMAGEIO_FFMPEG_EXE", binary)
        os.environ.setdefault("FFMPEG_BINARY", binary)
