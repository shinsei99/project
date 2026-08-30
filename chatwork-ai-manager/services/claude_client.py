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
import threading
import time

DEFAULT_MODEL = "sonnet"
DEFAULT_TIMEOUT = 300


class ClaudeError(RuntimeError):
    pass


class ClaudeStalledError(ClaudeError):
    """claude が「API と会話を始める前」で止まっている（＝認証・接続の詰まり）。

    2026-08-19 の障害で判明した現象。claude CLI の OAuth トークン更新がハングすると、
    最初の API 往復に入る前で固まり、こちらからは無応答にしか見えない。
    トークンは全プロセス共通の Keychain にあるため、**1本詰まると全員詰まる**。

    通常の ClaudeError（モデルがエラーを返した・JSONが壊れている等）と区別する理由:
      - フォールバックを打っても同じ理由で必ず失敗するので、打たずに即座に諦めたい
      - 依頼を捨てずにキューへ回し、復旧後に自動で実行し直したい
    詳しい切り分け手順は README「処理中にエラーが発生しました…」節にある。
    """


# 最初の assistant イベント（＝API往復が成った証拠）をどれだけ待つか。
# 実測（2026-08-19・正常時）: system/init 0.4秒 → assistant 10.5秒。90秒は9倍の余裕。
# ここを過ぎても assistant が来なければ「詰まり」と判定する。
# ※ assistant が来た後は打ち切らない（正常な長時間処理を切らないため）。
FIRST_RESPONSE_GRACE = 90


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
        # 満了しても何も返らないのは、実質「詰まり」と区別できない（2026-08-19の障害では
        # 300秒の解析も180秒の一発RAGも揃って無言のまま満了した）。詰まり扱いにして
        # 呼び出し側がキューへ回せるようにする。
        raise ClaudeStalledError(f"claude 応答が {timeout} 秒を超えました。")
    if proc.returncode != 0:
        # ★2026-08-30: **理由は stdout の JSON に入る**（stderr は空のことが多い）。
        #   stderr だけを出していたため、夜間OCRのログが3晩続けて
        #   「claude 失敗（code=1）: 」と理由なしで残り、原因を特定できなかった。
        #   実測: 環境を絞って呼ぶと exit 1・stderr 空・stdout に
        #   {"result":"Not logged in · Please run /login","terminal_reason":"api_error"}。
        #   利用上限や API 側のエラーも同じ形で stdout に入る。
        detail = (proc.stderr or "").strip()
        out = (proc.stdout or "").strip()
        if out:
            try:
                env0 = json.loads(out)
                detail = "%s / result=%s / terminal_reason=%s / api_error_status=%s" % (
                    detail or "(stderr なし)",
                    str(env0.get("result"))[:300],
                    env0.get("terminal_reason"),
                    env0.get("api_error_status"),
                )
            except json.JSONDecodeError:
                detail = (detail or "(stderr なし)") + " / stdout=" + out[:300]
        raise ClaudeError(f"claude 失敗（code={proc.returncode}）: {detail[:600]}")
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
              env_extra: dict = None, first_response_grace: int = FIRST_RESPONSE_GRACE) -> dict:
    """ツール（Bash/Read/WebSearch/WebFetch）を使える「エージェント」として claude を実行する。

    - Bash: 共通Tool層 agent_tool.py（社内RAG/TODO/Chatwork/案件/国交省API）を反復実行
    - WebSearch/WebFetch: ポータル物件検索・URL解析・一般調べもの（社内・公的で不足する最新外部情報）
    Claude Code と同様の多段検索・推論で回答させる。cwd にアプリのルートを渡す。

    env_extra: 子プロセスへ**追加**する環境変数（依頼の入口情報など）。
      既存のenvは絶対にフィルタしない（CLAUDECODE等が要る）。追加のみ。
    --strict-mcp-config: 業務QAは MCP を一切使わない（ブラウザ等の追加ツールで
      コンテキストと枠を消費しない）。Visual Agent は開発エージェント側で明示的に読む。
    """
    # stream-json にしているのは「詰まりを早く見抜く」ため（2026-08-19の障害対応）。
    # 一発の json だと最後まで何も届かず、600秒経つまで詰まりに気づけなかった。
    cmd = [CLAUDE_BIN, "-p", prompt, "--output-format", "stream-json", "--verbose",
           "--dangerously-skip-permissions", "--model", model, "--tools", tools,
           "--strict-mcp-config"]
    if cwd:
        cmd += ["--add-dir", cwd]
    return _run_streaming(cmd, cwd=cwd, env_extra=env_extra, timeout=timeout,
                          grace=first_response_grace, label="claude(agent)")


def _run_streaming(cmd, cwd, env_extra, timeout: int, grace: int, label: str) -> dict:
    """stream-json を1行ずつ読み、最後の result エンベロープを返す。

    2つの見張りを別々に持つ:
      - grace  : 最初の `assistant`（＝API往復が成った証拠）が来るまでの上限。
                 超えたら ClaudeStalledError（＝認証・接続の詰まり）。
      - timeout: 全体の上限。assistant が来た後はこちらだけで見る
                 （正常な長時間処理を途中で切らないため）。
    """
    start = time.time()
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, bufsize=1, cwd=cwd, env=_child_env(env_extra))
    except FileNotFoundError:
        raise ClaudeError("`claude` コマンドが見つかりません。")

    envelope = None
    saw_response = False
    stalled = False
    timed_out = False

    def _watchdog():
        """別スレッドで見張る（stdout の readline は止められないため kill で解除する）。"""
        nonlocal stalled, timed_out
        while proc.poll() is None:
            elapsed = time.time() - start
            if not saw_response and elapsed > grace:
                stalled = True
                proc.kill()
                return
            if elapsed > timeout:
                timed_out = True
                proc.kill()
                return
            time.sleep(0.5)

    t = threading.Thread(target=_watchdog, daemon=True)
    t.start()
    try:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue          # 進捗行が壊れていても本処理は止めない
            kind = d.get("type")
            if kind == "assistant":
                saw_response = True      # ここで grace の見張りは無効になる
            elif kind == "result":
                envelope = d
    finally:
        try:
            proc.stdout.close()
        except Exception:
            pass
        stderr = ""
        try:
            stderr = (proc.stderr.read() or "")[:500]
            proc.stderr.close()
        except Exception:
            pass
        proc.wait()

    if stalled:
        raise ClaudeStalledError(
            f"{label} が {grace} 秒経っても応答を始めませんでした"
            "（claudeの認証・接続が詰まっている可能性）。")
    if timed_out:
        raise ClaudeStalledError(f"{label} 応答が {timeout} 秒を超えました。")
    if envelope is None:
        # 応答は始まったのに result が来ない＝異常終了。詰まりとは区別する。
        raise ClaudeError(f"{label} が結果を返しませんでした（code={proc.returncode}）: {stderr.strip()}")
    if envelope.get("is_error"):
        raise ClaudeError(f"{label} がエラーを返しました: {envelope.get('result')}")
    envelope["_elapsed_ms"] = int((time.time() - start) * 1000)
    return envelope


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
