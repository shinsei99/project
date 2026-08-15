"""LLM呼び出しの共通窓口。

役割名（reasoning / longcontext / fast / light）を渡すと、
`.env` のルーティング設定と実際に使えるキーを見て、
Anthropic / Claude CLI / OpenAI / Gemini / Groq のどれかに振り分ける。

呼び出し側（各エージェント）は、どのAPIを使ったかを気にしなくてよい。
使えるプロバイダが1つも無いときは ok=False を返し、
エージェント側が縮退（雛形テキストの生成）に切り替える。
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .config import get_settings


@dataclass
class LLMResult:
    text: str = ""
    provider: str = ""
    model: str = ""
    ok: bool = False
    error: str = ""
    tried: List[str] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)  # 「provider: 失敗理由」の一覧


def complete(
    prompt: str,
    system: Optional[str] = None,
    role: str = "reasoning",
    max_tokens: int = 4000,
    temperature: float = 0.7,
    json_mode: bool = False,
    tools: Optional[Dict[str, Any]] = None,
) -> LLMResult:
    """1回の推論。失敗したら同じ役割の次の候補プロバイダへフォールバックする。

    json_mode=True のときは、対応するプロバイダでは「JSONしか返さない」モードを使う。
    """
    st = get_settings()
    from .config import PROVIDER_CHAINS

    import os

    override = os.getenv("AP_ROUTE_" + role.upper(), "auto").strip().lower()
    if override and override != "auto":
        candidates = [override]
    else:
        candidates = list(PROVIDER_CHAINS.get(role, PROVIDER_CHAINS["reasoning"]))

    result = LLMResult()
    for provider in candidates:
        if not st.provider_available(provider):
            continue
        result.tried.append(provider)
        try:
            text, model = _dispatch(provider, prompt, system, max_tokens,
                                    temperature, json_mode, tools)
            if text and text.strip():
                return LLMResult(text=text.strip(), provider=provider, model=model, ok=True,
                                 tried=result.tried, failures=result.failures)
            result.error = "%s が空の応答を返した" % provider
            result.failures.append(result.error)
        except Exception as exc:  # プロバイダ個別の失敗は次の候補で救う
            result.error = "%s: %s" % (provider, exc)
            result.failures.append(result.error[:300])
    if not result.tried:
        result.error = "利用可能なLLMプロバイダがありません（.env にキーを設定するか claude CLI を用意してください）"
    return result


def _dispatch(provider, prompt, system, max_tokens, temperature, json_mode=False,
              tools=None):
    if provider == "anthropic":
        return _call_anthropic(prompt, system, max_tokens, temperature)
    if provider == "claude_cli":
        return _call_claude_cli(prompt, system, tools)
    if provider == "openai":
        return _call_openai(prompt, system, max_tokens, temperature, json_mode)
    if provider == "gemini":
        return _call_gemini(prompt, system, max_tokens, temperature, json_mode)
    if provider == "groq":
        return _call_groq(prompt, system, max_tokens, temperature, json_mode)
    raise ValueError("未知のプロバイダ: %s" % provider)


def _quiet_genai_logs() -> None:
    """Geminiの「思考パートが含まれています」という警告を画面に出さない。

    Gemini 3.x は毎回 thought_signature を返すため、そのままだと進捗ログが
    英語の警告で埋まる。挙動には影響しないので黙らせる。
    """
    import logging

    for name in ("google_genai.types", "google_genai", "google.genai"):
        logging.getLogger(name).setLevel(logging.ERROR)


# --- 各プロバイダ ---------------------------------------------------------

def _call_anthropic(prompt, system, max_tokens, temperature):
    import anthropic  # type: ignore

    st = get_settings()
    client = anthropic.Anthropic(api_key=st.anthropic_key, timeout=float(st.llm_timeout))
    kwargs = {
        "model": st.anthropic_model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system
    msg = client.messages.create(**kwargs)
    text = "".join(getattr(block, "text", "") for block in msg.content)
    return text, st.anthropic_model


def _call_claude_cli(prompt, system, tools=None):
    """ローカルの `claude` CLI を叩く。APIキー不要のため既定の逃げ道になる。

    tools を渡すと、その部隊にだけ道具を許可する。
      {"web": True}            → WebFetch / WebSearch（URLを実際に読みに行く）
      {"dirs": [Path, ...]}    → Read / Glob / Grep ＋ --add-dir（資料フォルダを読む）

    これが無いと、各部隊はClaude Code単体より「できることが少ない」状態になる。
    マルチエージェントを単体の上位互換にするには、各部隊に同じ道具を持たせる必要がある。

    ※ --allowedTools は可変長引数。**カンマ区切りで1引数**にすること。
      スペース区切りにすると後続のプロンプトまでツール名として食われる（実際に踏んだ）。
    """
    st = get_settings()
    binary = st.claude_bin
    if not binary:
        raise RuntimeError("claude CLI が見つかりません")
    cmd = [binary, "-p", "--output-format", "text"]

    allowed = []
    uses_tools = False

    # MCP: 定義ファイルを渡すと、その中のサーバーの道具が全部使えるようになる。
    # ツール名は mcp__<サーバー名>__<ツール名>。サーバー単位で許可する。
    mcp_path = st.mcp_config
    if tools and tools.get("mcp", True) and mcp_path:
        cmd += ["--mcp-config", str(mcp_path)]
        if st.mcp_tools:
            allowed += [x for x in st.mcp_tools.split(",") if x]
        else:
            allowed += ["mcp__%s" % name for name in _mcp_server_names(mcp_path)]
        uses_tools = True

    if tools:
        if tools.get("web") and st.allow_web:
            allowed += [x for x in st.claude_web_tools.split(",") if x]
        for directory in tools.get("dirs") or []:
            cmd += ["--add-dir", str(directory)]
            uses_tools = True
        if tools.get("dirs"):
            allowed += [x for x in st.claude_file_tools.split(",") if x]
    if allowed:
        cmd += ["--allowedTools", ",".join(dict.fromkeys(allowed))]
        uses_tools = True

    # 使わせない道具は明示的に落とす（allowedTools は許可リストであって禁止ではない）
    if st.claude_denied_tools:
        cmd += ["--disallowedTools", st.claude_denied_tools]

    timeout = st.web_timeout if uses_tools else st.llm_timeout
    proc = subprocess.run(
        cmd, input=prompt, capture_output=True, text=True, timeout=timeout
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "claude CLI が異常終了").strip()[:400])
    return proc.stdout, "claude-cli"


def _mcp_server_names(path):
    """mcp.json からサーバー名を読む。読めなければ空（＝MCPは使わない）。"""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return []
    servers = data.get("mcpServers") or {}
    return [name for name, conf in servers.items()
            if isinstance(conf, dict) and not conf.get("disabled")]


def _call_openai(prompt, system, max_tokens, temperature, json_mode=False):
    from openai import OpenAI  # type: ignore

    st = get_settings()
    client = OpenAI(api_key=st.openai_key, timeout=float(st.llm_timeout))
    messages = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": prompt}
    ]
    extra = {"response_format": {"type": "json_object"}} if json_mode else {}
    resp = client.chat.completions.create(
        model=st.openai_model, messages=messages,
        max_tokens=max_tokens, temperature=temperature, **extra
    )
    return resp.choices[0].message.content or "", st.openai_model


def _call_gemini(prompt, system, max_tokens, temperature, json_mode=False):
    """新SDK `google-genai` を使う。

    旧 `google-generativeai` は提供終了。madori-tracer も新SDKで動いているので合わせた。

    重要（実測）: Gemini 3.x は「思考」にも出力トークンを使う。
    長いプロンプトで max_output_tokens が小さいと、思考で使い切って本文が空/途中で切れ、
    JSONの解釈に失敗する。JSONを求めるときは
      ・response_mime_type="application/json"（ネイティブJSONモード）
      ・思考の分を見込んで出力枠を広げる
    の2点をセットで行う。
    """
    from google import genai  # type: ignore
    from google.genai import types  # type: ignore

    _quiet_genai_logs()
    st = get_settings()
    # timeout はミリ秒。指定しないと応答が返らないとき無限に待ち続ける
    client = genai.Client(api_key=st.gemini_key,
                          http_options=types.HttpOptions(timeout=st.llm_timeout * 1000))
    budget = max(max_tokens * 3, 8000) if json_mode else max_tokens
    config = types.GenerateContentConfig(
        max_output_tokens=budget,
        temperature=temperature,
        system_instruction=system or None,
        response_mime_type="application/json" if json_mode else None,
    )
    resp = client.models.generate_content(model=st.gemini_model, contents=prompt,
                                          config=config)
    return (getattr(resp, "text", "") or ""), st.gemini_model


def _call_groq(prompt, system, max_tokens, temperature, json_mode=False):
    """Groq は OpenAI 互換のREST。SDKを増やさず requests で直接叩く。"""
    import requests  # type: ignore

    st = get_settings()
    messages = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": prompt}
    ]
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": "Bearer %s" % st.groq_key,
                 "Content-Type": "application/json"},
        json=dict({"model": st.groq_model, "messages": messages,
                   "max_tokens": max_tokens, "temperature": temperature},
                  **({"response_format": {"type": "json_object"}} if json_mode else {})),
        timeout=st.llm_timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"], st.groq_model


# --- JSON応答の取り出し ---------------------------------------------------

def extract_json(text: str) -> Optional[Any]:
    """LLMの返答から JSON を取り出す。

    前置き・```json フェンス・末尾の解説が付いてくることが常なので、
    素の json.loads だけに頼らず、最初の { か [ から対応する括弧までを切り出す。
    """
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    candidates = []
    if fenced:
        candidates.append(fenced.group(1).strip())
    candidates.append(text.strip())
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except ValueError:
            pass
        start = min([i for i in (candidate.find("{"), candidate.find("[")) if i >= 0] or [-1])
        if start < 0:
            continue
        opening = candidate[start]
        closing = "}" if opening == "{" else "]"
        depth = 0
        in_string = False
        escaped = False
        for idx in range(start, len(candidate)):
            ch = candidate[idx]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == opening:
                depth += 1
            elif ch == closing:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(candidate[start:idx + 1])
                    except ValueError:
                        break
    return None


def complete_json(prompt: str, system: Optional[str] = None, role: str = "reasoning",
                  max_tokens: int = 4000, temperature: float = 0.4,
                  tools: Optional[Dict[str, Any]] = None):
    """JSONで返させる版。(データ, LLMResult) を返す。取り出せなければデータは None。"""
    guard = "\n\n必ず有効なJSONのみを出力すること。前置き・後書き・コードフェンスは不要。"
    result = complete(prompt + guard, system=system, role=role,
                      max_tokens=max_tokens, temperature=temperature, json_mode=True,
                      tools=tools)
    if not result.ok:
        return None, result
    return extract_json(result.text), result
