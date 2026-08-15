#!/usr/bin/env python3
"""agent-platform の起点。

使い方:
    python main_orchestrator.py "新規事業の企画からパワポ・音声・動画・SNS告知まで全部作って"
    python main_orchestrator.py --doctor              # 接続できるAPIと導入済みライブラリを確認
    python main_orchestrator.py --list-agents         # 部隊一覧
    python main_orchestrator.py "..." --input 資料.txt 写真.jpg
    python main_orchestrator.py "..." --only planner,ppt      # 一部工程だけ
    python main_orchestrator.py "..." --skip video            # 重い工程を飛ばす
    python main_orchestrator.py "..." --dry-run               # 実行順の確認だけ
    python main_orchestrator.py --resume --job-id X --only video   # 失敗した工程だけやり直す
    python main_orchestrator.py --job-id X --revise "写真を4枚並べて" --only flyer  # 直しを指示

画面には日本語の進捗だけを出す（技術ログは --verbose で表示）。
"""
from __future__ import annotations

import argparse
import shutil
import sys
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

# 画面には日本語の進捗だけを出したいので、ライブラリの警告は伏せる
# （Python 3.9 のサポート終了告知・LibreSSL 警告など、こちらで対処できないもの）
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*OpenSSL.*")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.config import PROVIDER_LABELS, get_settings  # noqa: E402
from core.context import JobContext  # noqa: E402
from core.pipeline import PIPELINE_ORDER, Pipeline  # noqa: E402


# --- 進捗の表示（日本語のみ） -------------------------------------------------

class ConsolePrinter:
    ICONS = {"success": "✅", "warn": "⚠️ ", "error": "❌", "info": "  ",
             "debug": "   ·"}

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def __call__(self, event: Dict[str, Any]) -> None:
        kind = event.get("type")
        level = event.get("level", "info")
        if level == "debug" and not self.verbose:
            return
        message = event.get("message", "")
        if kind == "pipeline_start":
            print("\n" + message)
            print("-" * 60)
        elif kind == "step":
            print("\n%s" % message)
        elif kind == "agent_end":
            print("   %s %s（%.1f秒）" % (self.ICONS.get(level, ""), message,
                                          event.get("elapsed", 0)))
        elif kind == "progress":
            current, total = event.get("current"), event.get("total")
            prefix = "   [%s/%s] " % (current, total) if current and total else "   "
            print(prefix + message)
        elif kind == "log":
            print("   %s %s" % (self.ICONS.get(level, "  "), message))
        elif kind == "pipeline_end":
            print("-" * 60)
            print(message)


# --- ジョブ実行 ---------------------------------------------------------------

def run_job(brief: str, options: Optional[Dict[str, Any]] = None,
            inputs: Optional[List[str]] = None,
            on_event=None, job_id: Optional[str] = None,
            only: Optional[List[str]] = None, skip: Optional[List[str]] = None,
            dry_run: bool = False, resume: bool = False):
    """1件の依頼を最初から最後まで通す。UI からもここを呼ぶ。"""
    if resume and job_id:
        ctx = JobContext.load(job_id, on_event=on_event)
        ctx.log("保存済みジョブ %s を読み込みました（済んだ工程はやり直しません）" % job_id)
    else:
        ctx = JobContext(brief=brief, job_id=job_id, options=options or {},
                         on_event=on_event)
    for src in inputs or []:
        src_path = Path(src)
        if src_path.exists():
            shutil.copyfile(src_path, ctx.dir("input") / src_path.name)
            ctx.log("入力ファイルを受け取りました: %s" % src_path.name)
    results = Pipeline().run(ctx, only=only, skip=skip, dry_run=dry_run)
    return ctx, results


# --- 環境診断 -----------------------------------------------------------------

def doctor() -> int:
    st = get_settings()
    print("=== 接続できるAI（.env の設定状況）===")
    availability = st.availability_report()
    for provider, ok in availability.items():
        print("  %s %s" % ("✅" if ok else "－", PROVIDER_LABELS[provider]))

    print("\n=== 役割ごとの割り当て ===")
    role_labels = {"reasoning": "司令塔・企画・法務（高精度）",
                   "longcontext": "リサーチャー（長文）",
                   "fast": "高速チェッカー",
                   "light": "SNS発信"}
    for role, label in role_labels.items():
        provider = st.resolve_provider(role)
        print("  %-28s → %s" % (label, PROVIDER_LABELS.get(provider, "使えるものがありません")))

    print("\n=== 生成バックエンド ===")
    from agents.image_generator import _decide_backend

    image_labels = {"openai": "OpenAI DALL-E 3", "gemini": "Gemini 画像生成",
                    "stability": "Stability AI", "stub": "簡易画像（キー未設定）"}
    print("  画像: %s" % image_labels.get(_decide_backend(st), "不明"))
    tts = ("OpenAI TTS" if st.openai_key else
           ("ElevenLabs" if st.elevenlabs_key else
            ("gTTS（無料）" if _module("gtts") else "無音（合成手段なし）")))
    print("  音声: %s" % tts)
    print("  動画: %s" % ("moviepy" if _module("moviepy") else "未導入"))

    print("\n=== 各部隊が使えるアイテム ===")
    try:
        import tools as tool_pack

        for item in tool_pack.catalog():
            print("  %s %-26s %s" % ("✅" if item["available"] else "－",
                                     item["label"], item["note"]))
    except Exception as exc:
        print("  取得できませんでした（%s）" % exc)

    mcp = st.mcp_config
    if mcp:
        import json as _json
        try:
            servers = list((_json.loads(Path(mcp).read_text(encoding="utf-8"))
                            .get("mcpServers") or {}).keys())
        except Exception:
            servers = []
        print("  MCP: %s（%s）" % ("・".join(servers) or "なし", mcp.name))
    else:
        print("  MCP: 無効（AP_MCP=off か mcp.json 無し）")

    print("\n=== ライブラリ ===")
    for module, label in [("streamlit", "UI"), ("pptx", "パワポ生成"),
                          ("PIL", "画像処理"), ("moviepy", "動画合成"),
                          ("imageio_ffmpeg", "ffmpeg同梱"), ("gtts", "音声合成(無料)"),
                          ("anthropic", "Anthropic SDK"), ("openai", "OpenAI SDK"),
                          ("google.genai", "Gemini SDK"), ("requests", "HTTP"),
                          ("pytest", "テスト")]:
        print("  %s %s（%s）" % ("✅" if _module(module) else "－", module, label))

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg and _module("imageio_ffmpeg"):
        import imageio_ffmpeg  # type: ignore
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe() + "（imageio-ffmpeg同梱）"
    print("\n  ffmpeg: %s" % (ffmpeg or "見つかりません（動画書き出し不可）"))
    print("  出力先: %s" % st.output_dir)

    if not any(availability.values()):
        print("\n⚠️  使えるLLMが1つもありません。.env にキーを設定するか claude CLI を用意してください。")
        return 1
    return 0


def _module(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


def list_agents() -> None:
    from agents import agent_catalog

    print("=== 部隊一覧（実行順）===")
    for i, a in enumerate(agent_catalog(), start=1):
        print("%2d. %s %-16s %s" % (i, a["icon"], a["name_ja"], a["role_ja"]))
        print("     使用: %s" % a["uses"])


# --- CLI ----------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="マルチプロダクション（企画から紙面・音声・動画まで）",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("brief", nargs="?", help="やってほしいことを日本語で（例: 新規事業の企画一式を作って）")
    parser.add_argument("--doctor", action="store_true", help="環境と接続状況を確認する")
    parser.add_argument("--list-agents", action="store_true", help="部隊一覧を表示する")
    parser.add_argument("--input", nargs="*", default=[], help="参考資料（テキスト・画像）")
    parser.add_argument("--slides", type=int, default=None, help="スライド枚数")
    parser.add_argument("--job-id", default=None, help="出力フォルダ名（既定は日時）")
    parser.add_argument("--only", default="", help="実行する工程をカンマ区切りで指定")
    parser.add_argument("--skip", default="", help="飛ばす工程をカンマ区切りで指定")
    parser.add_argument("--dry-run", action="store_true", help="実行順の確認だけ行う")
    parser.add_argument("--resume", action="store_true",
                        help="--job-id の保存済みジョブを読み込んで続きから実行する"
                             "（例: 動画だけ失敗したとき --resume --job-id X --only video）")
    parser.add_argument("--revise", default="",
                        help="前回の成果物への修正指示（--resume --job-id と一緒に使う）")
    parser.add_argument("--open", action="store_true",
                        help="終わったら出力フォルダをFinderで開く")
    parser.add_argument("--verbose", action="store_true", help="技術ログも表示する")
    args = parser.parse_args(argv)

    if args.doctor:
        return doctor()
    if args.list_agents:
        list_agents()
        return 0
    if not args.brief and not (args.resume and args.job_id):
        parser.print_help()
        print("\n工程キー: %s" % ", ".join(PIPELINE_ORDER))
        return 1

    options: Dict[str, Any] = {}
    if args.slides:
        options["slide_count"] = args.slides
    if args.revise:
        options["revision"] = args.revise
        args.resume = True

    ctx, results = run_job(
        brief=args.brief or "", options=options, inputs=args.input,
        on_event=ConsolePrinter(verbose=args.verbose), job_id=args.job_id,
        only=[s for s in args.only.split(",") if s] or None,
        skip=[s for s in args.skip.split(",") if s] or None,
        dry_run=args.dry_run, resume=args.resume,
    )

    # 端末では file:// のリンクを ⌘+クリック で開ける
    print("\n成果物: %s" % ctx.root)
    print("　　　  file://%s" % str(ctx.root).replace(" ", "%20"))
    for art in ctx.artifacts:
        print("  - %s: %s" % (art.label or art.kind, art.path))
    print("レポート: %s" % ctx.state.get("report_path", ""))
    if args.open:
        import subprocess

        try:
            subprocess.run(["open", str(ctx.root)], timeout=10)
        except Exception:
            pass
    return 0 if all(r.ok for r in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
