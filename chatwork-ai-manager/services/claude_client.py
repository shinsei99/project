"""`claude` CLI をサブプロセス呼び出しする共通ヘルパ。

Anthropic API キーは使わず、ログイン済み Claude Code CLI（MAX 定額）を利用する。
既存アプリ（restoration-calculator/services/pdf_parser.py 等）と同じ作法:
  - claude バイナリは絶対パス解決（launchd は PATH が最小のため素の "claude" は不可）
  - env は一切フィルタしない（CLAUDECODE 等を落とすと daemon に繋がらない）
  - --output-format json でエンベロープを受け取り、model 出力から JSON を取り出す
"""
import json
import os
import re
import shutil
import subprocess
import time

DEFAULT_MODEL = "sonnet"
DEFAULT_TIMEOUT = 300


class ClaudeError(RuntimeError):
    pass


def _resolve_claude_bin() -> str:
    p = shutil.which("claude")
    if p:
        return p
    for cand in (
        "/opt/homebrew/bin/claude",
        os.path.expanduser("~/.local/bin/claude"),
        "/usr/local/bin/claude",
    ):
        if os.path.exists(cand):
            return cand
    return "claude"


CLAUDE_BIN = _resolve_claude_bin()


def run_claude(prompt: str, model: str = DEFAULT_MODEL, timeout: int = DEFAULT_TIMEOUT,
               add_dir: str = None, allow_read: bool = False) -> dict:
    """claude を呼び、CLI エンベロープ dict を返す（result/is_error/duration_ms 等）。

    add_dir: Read を許可するディレクトリ（画像OCR等でファイルを渡す場合）。
    """
    cmd = [CLAUDE_BIN, "-p", prompt, "--output-format", "json",
           "--dangerously-skip-permissions", "--model", model]
    if allow_read:
        cmd += ["--tools", "Read"]
    if add_dir:
        cmd += ["--add-dir", add_dir]
    start = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise ClaudeError("`claude` コマンドが見つかりません。Claude Code CLI を確認してください。")
    except subprocess.TimeoutExpired:
        raise ClaudeError(f"claude 応答が {timeout} 秒を超えました。")
    if proc.returncode != 0:
        raise ClaudeError(
            f"claude 失敗（code={proc.returncode}）: {proc.stderr.strip()[:500]}"
        )
    try:
        env = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise ClaudeError(f"claude 出力の JSON 解析に失敗: {proc.stdout[:500]}")
    if env.get("is_error"):
        raise ClaudeError(f"claude がエラーを返しました: {env.get('result')}")
    env["_elapsed_ms"] = int((time.time() - start) * 1000)
    return env


def run_agent(prompt: str, model: str = DEFAULT_MODEL, timeout: int = 600,
              cwd: str = None, tools: str = "Bash,Read,WebSearch,WebFetch") -> dict:
    """ツール（Bash/Read/WebSearch/WebFetch）を使える「エージェント」として claude を実行する。

    - Bash: 共通Tool層 agent_tool.py（社内RAG/TODO/Chatwork/案件/国交省API）を反復実行
    - WebSearch/WebFetch: ポータル物件検索・URL解析・一般調べもの（社内・公的で不足する最新外部情報）
    Claude Code と同様の多段検索・推論で回答させる。cwd にアプリのルートを渡す。
    """
    cmd = [CLAUDE_BIN, "-p", prompt, "--output-format", "json",
           "--dangerously-skip-permissions", "--model", model, "--tools", tools]
    if cwd:
        cmd += ["--add-dir", cwd]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    except FileNotFoundError:
        raise ClaudeError("`claude` コマンドが見つかりません。")
    except subprocess.TimeoutExpired:
        raise ClaudeError(f"claude(agent) 応答が {timeout} 秒を超えました。")
    if proc.returncode != 0:
        raise ClaudeError(f"claude(agent) 失敗（code={proc.returncode}）: {proc.stderr.strip()[:500]}")
    try:
        env = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise ClaudeError(f"claude(agent) 出力の JSON 解析に失敗: {proc.stdout[:500]}")
    if env.get("is_error"):
        raise ClaudeError(f"claude(agent) がエラーを返しました: {env.get('result')}")
    return env


def _extract_json(text: str):
    """モデル出力テキストから JSON オブジェクト/配列を取り出す（```json フェンス耐性）。"""
    m = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
    json_str = m.group(1) if m else text.strip()
    if not (json_str.startswith("{") or json_str.startswith("[")):
        m2 = re.search(r"(\{.*\}|\[.*\])", json_str, re.DOTALL)
        if m2:
            json_str = m2.group(1)
    return json.loads(json_str)


def run_json(prompt: str, model: str = DEFAULT_MODEL, timeout: int = DEFAULT_TIMEOUT,
             add_dir: str = None, allow_read: bool = False):
    """claude を呼び、モデルが返した JSON を parse して返す。

    戻り値: (parsed, envelope)。envelope はログ保存用（raw_output/_elapsed_ms を含む）。
    """
    env = run_claude(prompt, model=model, timeout=timeout, add_dir=add_dir, allow_read=allow_read)
    raw_text = env.get("result", "")
    try:
        parsed = _extract_json(raw_text)
    except json.JSONDecodeError:
        raise ClaudeError(f"モデル出力から JSON を取り出せませんでした: {raw_text[:500]}")
    return parsed, env


def run_text(prompt: str, model: str = DEFAULT_MODEL, timeout: int = DEFAULT_TIMEOUT):
    """自由文の回答（Q&A 等）を文字列で返す。戻り値: (text, envelope)。"""
    env = run_claude(prompt, model=model, timeout=timeout)
    return env.get("result", "").strip(), env
