"""設定の一元管理。

`.env` を読み込み、「どのプロバイダが今使えるか」を判定する。
APIキーが無い場合でもプラットフォーム全体が止まらないよう、
可用性の判定結果をパイプライン側が見て縮退（stub）に切り替える。
"""
from __future__ import annotations

import os
import shutil
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent

# 役割ごとのプロバイダ優先順（.env の AP_ROUTE_* が auto のとき使う）
PROVIDER_CHAINS: Dict[str, List[str]] = {
    "reasoning": ["anthropic", "claude_cli", "openai", "gemini", "groq"],
    "longcontext": ["gemini", "anthropic", "claude_cli", "openai"],
    "fast": ["groq", "gemini", "claude_cli", "anthropic", "openai"],
    "light": ["groq", "gemini", "openai", "claude_cli", "anthropic"],
    # 道具（Web取得・検索・ファイル読み）が要る仕事。いま道具を持てるのは claude CLI だけ。
    "tools": ["claude_cli"],
}

PROVIDER_LABELS = {
    "anthropic": "Claude (Anthropic API)",
    "claude_cli": "Claude Code CLI (キー不要)",
    "openai": "OpenAI",
    "gemini": "Google Gemini",
    "groq": "Groq",
}


def load_dotenv(path: Optional[Path] = None) -> None:
    """`.env` を環境変数へ読み込む。既存の環境変数は上書きしない。

    python-dotenv があればそれを使い、無ければ自前の簡易パーサで読む
    （依存を1つ増やすためだけに起動できなくならないようにするため）。
    """
    env_path = Path(path) if path else ROOT / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv as _ld  # type: ignore

        _ld(dotenv_path=str(env_path), override=False)
        return
    except Exception:
        pass
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _module_available(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


class Settings:
    """環境変数のラッパー。値の取り出しと可用性判定だけを担当する。"""

    def __init__(self) -> None:
        load_dotenv()

    # --- APIキー ---
    @property
    def anthropic_key(self) -> str:
        return os.getenv("ANTHROPIC_API_KEY", "").strip()

    @property
    def openai_key(self) -> str:
        return os.getenv("OPENAI_API_KEY", "").strip()

    @property
    def pexels_key(self) -> str:
        """フリー写真（Pexels）の鍵。**無料・登録のみで支払いは無い**。

        無くても Openverse（鍵不要）で写真は入るが、質にムラがある。
        https://www.pexels.com/api/ で取得して .env に置くと、写真が見違える。
        """
        return os.getenv("PEXELS_API_KEY", "").strip()

    @property
    def gemini_key(self) -> str:
        return (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()

    @property
    def groq_key(self) -> str:
        return os.getenv("GROQ_API_KEY", "").strip()

    @property
    def elevenlabs_key(self) -> str:
        return os.getenv("ELEVENLABS_API_KEY", "").strip()

    @property
    def stability_key(self) -> str:
        return os.getenv("STABILITY_API_KEY", "").strip()

    # --- モデル ---
    @property
    def anthropic_model(self) -> str:
        return os.getenv("ANTHROPIC_MODEL", "claude-opus-5")

    @property
    def anthropic_model_fast(self) -> str:
        return os.getenv("ANTHROPIC_MODEL_FAST", "claude-haiku-4-5-20251001")

    @property
    def openai_model(self) -> str:
        return os.getenv("OPENAI_MODEL", "gpt-4o")

    @property
    def gemini_model(self) -> str:
        # 2026-08-14 時点で gemini-2.0-flash は提供終了（404）。既定を 3.5-flash に更新
        return os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

    @property
    def gemini_image_model(self) -> str:
        return os.getenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")

    @property
    def groq_model(self) -> str:
        return os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    @property
    def openai_image_model(self) -> str:
        return os.getenv("OPENAI_IMAGE_MODEL", "dall-e-3")

    @property
    def openai_tts_model(self) -> str:
        return os.getenv("OPENAI_TTS_MODEL", "tts-1-hd")

    @property
    def openai_tts_voice(self) -> str:
        return os.getenv("OPENAI_TTS_VOICE", "alloy")

    @property
    def elevenlabs_voice_id(self) -> str:
        return os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

    # --- バックエンド選択 ---
    @property
    def image_backend(self) -> str:
        return os.getenv("AP_IMAGE_BACKEND", "auto").lower()

    @property
    def tts_backend(self) -> str:
        return os.getenv("AP_TTS_BACKEND", "auto").lower()

    @property
    def video_backend(self) -> str:
        return os.getenv("AP_VIDEO_BACKEND", "auto").lower()

    # --- 動作設定 ---
    @property
    def output_dir(self) -> Path:
        raw = os.getenv("AP_OUTPUT_DIR", "output")
        p = Path(raw)
        return p if p.is_absolute() else ROOT / p

    @property
    def default_slides(self) -> int:
        return _int_env("AP_DEFAULT_SLIDES", 8)

    @property
    def video_size(self):
        # 既定は720p。1080pだとIntel Macで2分の動画に10分近くかかった（実測）ため、
        # スライド動画には十分な720pを既定にしている。必要なら .env で上げる。
        return (_int_env("AP_VIDEO_WIDTH", 1280), _int_env("AP_VIDEO_HEIGHT", 720))

    @property
    def video_fps(self) -> int:
        return _int_env("AP_VIDEO_FPS", 24)

    @property
    def allow_paid(self) -> bool:
        """お金のかかる機能を使ってよいか。**既定は禁止**。

        Veo（画像→動画）のように秒単位で課金されるものは、うっかり使うと
        1本で数ドル飛ぶ。既定で塞ぎ、明示的に AP_ALLOW_PAID=1 にしたときだけ通す。
        """
        return os.getenv("AP_ALLOW_PAID", "0").strip().lower() in ("1", "true", "yes", "on")

    @property
    def video_motion(self) -> str:
        """静止画に付ける動き。

        kenburns … ゆっくりズーム／パン（**無料**・写真の中身は変わらない・既定）
        off      … 完全な静止画
        """
        return os.getenv("AP_VIDEO_MOTION", "kenburns").strip().lower()

    @property
    def video_preset(self) -> str:
        """x264のエンコード速度。ultrafast〜veryslow。速いほどファイルは大きい。"""
        return os.getenv("AP_VIDEO_PRESET", "veryfast")

    @property
    def video_threads(self) -> int:
        value = _int_env("AP_VIDEO_THREADS", 0)
        return value if value > 0 else max(1, (os.cpu_count() or 2) - 1)

    @property
    def tts_lang(self) -> str:
        return os.getenv("AP_TTS_LANG", "ja")

    @property
    def audio_volume(self) -> float:
        """動画に載せるナレーションの音量倍率（1.0 = 原音のまま）。"""
        try:
            return max(0.0, float(os.getenv("AP_AUDIO_VOLUME", "1.0").strip()))
        except (TypeError, ValueError):
            return 1.0

    @property
    def max_retake(self) -> int:
        """司令塔が不合格を出したとき、作り直す回数の上限。

        0 にすると指摘を出すだけで直さない。多くしすぎると時間と費用が増えるので既定は1。
        """
        return _int_env("AP_MAX_RETAKE", 1)

    @property
    def strict_legal(self) -> bool:
        return os.getenv("AP_STRICT_LEGAL", "0").strip() in ("1", "true", "True", "yes")

    @property
    def llm_timeout(self) -> int:
        return _int_env("AP_LLM_TIMEOUT", 180)

    @property
    def allow_web(self) -> bool:
        """調査でWebを見に行くか。claude CLI のツール（WebFetch/WebSearch）を使う。"""
        return os.getenv("AP_ALLOW_WEB", "1").strip() not in ("0", "false", "False", "no")

    @property
    def agent_tools_enabled(self) -> bool:
        """各部隊に道具（Web・資料読み）を持たせるか。

        off にすると全部隊が「知識だけ」で考える（速いが裏が取れない）。
        """
        return os.getenv("AP_AGENT_TOOLS", "on").strip().lower() not in ("off", "0", "false")

    @property
    def mcp_config(self) -> Optional[Path]:
        """MCPサーバー定義。ここに1行足すと全部隊の道具が増える。

        AP_MCP=off で無効化（npx の起動ぶん遅くなるため、要らないときは切る）。
        """
        if os.getenv("AP_MCP", "on").strip().lower() in ("off", "0", "false"):
            return None
        raw = os.getenv("AP_MCP_CONFIG", "mcp.json")
        path = Path(raw)
        path = path if path.is_absolute() else ROOT / path
        return path if path.exists() else None

    @property
    def mcp_tools(self) -> str:
        """許可するMCPツール。既定はmcp.jsonに書いたサーバー全部。"""
        return os.getenv("AP_MCP_TOOLS", "").strip()

    @property
    def agent_tools_all(self) -> bool:
        """AP_AGENT_TOOLS=all のとき、道具が要らない部隊にも道具を持たせる。

        質は上がりうるが、全部隊が claude CLI 固定になり体感で3〜4倍遅くなる。
        """
        return os.getenv("AP_AGENT_TOOLS", "on").strip().lower() == "all"

    @property
    def claude_web_tools(self) -> str:
        return os.getenv("AP_CLAUDE_WEB_TOOLS", "WebFetch,WebSearch")

    @property
    def claude_denied_tools(self) -> str:
        """部隊に**使わせない**道具。

        重要（実測）: `--allowedTools` は「自動承認するもの」の指定であって、
        禁止リストではない。指定しなくても Bash や Write は実行できてしまう。
        止めたいものは `--disallowedTools` で明示的に落とす必要がある。
        既定では、PCを書き換える・任意コマンドを実行する系を全部落とす。
        """
        return os.getenv(
            "AP_CLAUDE_DENIED_TOOLS",
            "Bash,Write,Edit,NotebookEdit,Agent,Task,KillShell,BashOutput")

    @property
    def claude_file_tools(self) -> str:
        return os.getenv("AP_CLAUDE_FILE_TOOLS", "Read,Glob,Grep")

    @property
    def web_timeout(self) -> int:
        # ページ取得＋検索が入るぶん、通常のLLM呼び出しより長くかかる
        return _int_env("AP_WEB_TIMEOUT", 600)

    @property
    def image_timeout(self) -> int:
        # 画像生成はテキストより時間がかかる（実測で1枚あたり数十秒〜）
        return _int_env("AP_IMAGE_TIMEOUT", 300)

    @property
    def claude_bin(self) -> Optional[str]:
        explicit = os.getenv("AP_CLAUDE_BIN", "").strip()
        if explicit and Path(explicit).exists():
            return explicit
        return shutil.which("claude")

    # --- 可用性判定 ---
    def provider_available(self, provider: str) -> bool:
        if provider == "anthropic":
            return bool(self.anthropic_key) and _module_available("anthropic")
        if provider == "claude_cli":
            return self.claude_bin is not None
        if provider == "openai":
            return bool(self.openai_key) and _module_available("openai")
        if provider == "gemini":
            return bool(self.gemini_key) and _module_available("google.genai")
        if provider == "groq":
            return bool(self.groq_key) and _module_available("requests")
        return False

    def resolve_provider(self, role: str) -> Optional[str]:
        """役割名から実際に使うプロバイダを決める。使えるものが無ければ None。"""
        override = os.getenv("AP_ROUTE_" + role.upper(), "auto").strip().lower()
        if override and override != "auto":
            return override if self.provider_available(override) else None
        for provider in PROVIDER_CHAINS.get(role, PROVIDER_CHAINS["reasoning"]):
            if self.provider_available(provider):
                return provider
        return None

    @property
    def hidden_providers(self) -> List[str]:
        """接続状況の表示から省くプロバイダ。

        既定は openai と groq。どちらもこの環境では未契約で、
        並んでいても「－」が続くだけで判断の役に立たないため。
        キーを入れれば（＝実際に使えるようになれば）自動的に表示に戻る。
        """
        raw = os.getenv("AP_HIDE_PROVIDERS", "openai,groq")
        return [x.strip() for x in raw.split(",") if x.strip()]

    def availability_report(self, include_hidden: bool = False) -> Dict[str, bool]:
        hidden = set() if include_hidden else set(self.hidden_providers)
        report = {}
        for name in PROVIDER_LABELS:
            ok = self.provider_available(name)
            if name in hidden and not ok:
                continue
            report[name] = ok
        return report


def _int_env(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)).strip())
    except (TypeError, ValueError):
        return default


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
