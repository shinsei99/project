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
              cwd: str = None, tools: str = "Bash,Read,WebSearch,WebFetch",
              env_extra: dict = None) -> dict:
    """ツール（Bash/Read/WebSearch/WebFetch）を使える「エージェント」として claude を実行する。

    - Bash: 共通Tool層 agent_tool.py（社内RAG/TODO/Chatwork/案件/国交省API）を反復実行
    - WebSearch/WebFetch: ポータル物件検索・URL解析・一般調べもの（社内・公的で不足する最新外部情報）
    Claude Code と同様の多段検索・推論で回答させる。cwd にアプリのルートを渡す。

    env_extra: 子プロセスへ**追加**する環境変数（依頼の入口情報など）。
      既存のenvは絶対にフィルタしない（CLAUDECODE等が要る）。追加のみ。
    --strict-mcp-config: 業務QAは MCP を一切使わない（ブラウザ等の追加ツールで
      コンテキストと枠を消費しない）。Visual Agent は開発エージェント側で明示的に読む。
    """
    cmd = [CLAUDE_BIN, "-p", prompt, "--output-format", "json",
           "--dangerously-skip-permissions", "--model", model, "--tools", tools,
           "--strict-mcp-config"]
    if cwd:
        cmd += ["--add-dir", cwd]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd,
                              env=_child_env(env_extra))
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


def _child_env(env_extra: dict = None) -> dict:
    """子プロセスの環境変数。**既存envは丸ごと引き継ぎ、追加だけ行う。**

    （env をフィルタすると CLAUDECODE 等が落ちて claude が daemon に繋がらない。既知の罠）
    """
    env = os.environ.copy()
    # launchd の PATH は最小（/usr/bin:/bin:/usr/sbin:/sbin）で npx / node が見えない。
    # Visual Agent（Playwright MCP）は npx で起動するため、無ければ足す（消さない・並べ替えない）。
    path = env.get("PATH", "")
    for d in ("/usr/local/bin", "/opt/homebrew/bin", os.path.expanduser("~/.local/bin")):
        if os.path.isdir(d) and d not in path.split(":"):
            path = f"{path}:{d}" if path else d
    env["PATH"] = path
    for k, v in (env_extra or {}).items():
        if v is not None:
            env[str(k)] = str(v)
    return env


class ClaudeSessionError(ClaudeError):
    """指定したセッションを再開できなかった（存在しない/壊れている）。"""


def _tail(path: str, n: int = 20) -> str:
    """エラー原因を拾うためにログの末尾だけ読む（stderrをファイルへ流しているため）。"""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-n:])[:800]
    except OSError:
        return ""


def run_dev_agent(prompt: str, cwd: str, model: str = DEFAULT_MODEL, timeout: int = 3600,
                  mcp_config: str = None, session_id: str = None, resume: bool = False,
                  log_path: str = None, env_extra: dict = None) -> dict:
    """開発エージェント（DEVELOPMENT + VISUAL_AGENT）として claude を実行する。

    QA用の run_agent との違いは3点だけで、既存の呼び出しには一切影響しない:
      1. ツールを制限しない（--tools default）＝ Write/Edit/Glob/Grep/Task 等が使える
      2. mcp_config を渡す＝ 共通Visual Agent（Playwright MCP）でブラウザを見て操作できる
      3. セッションIDを**呼ぶ側が決めて**渡す（`--session-id`）。DBに先に保存しておけるので、
         途中でworkerごと落ちても `resume=True` で**同じセッションの続き**として再開できる
         （最初からやり直さない）。INTERRUPT後の再開も同じ仕組み。

    戻り値: claude CLI のエンベロープ dict（result / session_id / is_error …）。
    stderr は log_path へ流す（長時間タスクの実況を残すため）。
    """
    cmd = [CLAUDE_BIN, "-p", prompt, "--output-format", "json",
           "--dangerously-skip-permissions", "--model", model, "--tools", "default"]
    if session_id:
        cmd += (["--resume", session_id] if resume else ["--session-id", session_id])
    if mcp_config and os.path.exists(mcp_config):
        # 共通Visual Agent の定義はこの1ファイルだけを見る（他のMCP設定は読まない＝再現性）
        cmd += ["--mcp-config", mcp_config, "--strict-mcp-config"]
    if cwd:
        cmd += ["--add-dir", cwd]
    err_fh = None
    try:
        if log_path:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            err_fh = open(log_path, "a", encoding="utf-8")
            err_fh.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} claude 起動 "
                         f"(model={model} "
                         f"session={'再開' if resume else '新規'}:{session_id or '-'}) =====\n")
            err_fh.flush()
        proc = subprocess.run(cmd, stdout=subprocess.PIPE,
                              stderr=(err_fh or subprocess.PIPE),
                              text=True, timeout=timeout, cwd=cwd,
                              env=_child_env(env_extra))
    except FileNotFoundError:
        raise ClaudeError("`claude` コマンドが見つかりません。")
    except subprocess.TimeoutExpired:
        raise ClaudeError(f"開発エージェントの応答が {timeout} 秒を超えました。")
    finally:
        if err_fh:
            err_fh.close()
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "")[:500]
        if log_path and not proc.stderr:
            detail = _tail(log_path)
        low = detail.lower()
        if session_id and ("session" in low and ("not found" in low or "no conversation" in low
                                                 or "already in use" in low or "exists" in low)):
            raise ClaudeSessionError(f"セッションを再開できません: {detail}")
        raise ClaudeError(f"開発エージェント失敗（code={proc.returncode}）: {detail}")
    try:
        env = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise ClaudeError(f"開発エージェント出力の JSON 解析に失敗: {proc.stdout[:500]}")
    if env.get("is_error"):
        raise ClaudeError(f"開発エージェントがエラーを返しました: {str(env.get('result'))[:500]}")
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
