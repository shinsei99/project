"""自然文の検索依頼を、DB検索の条件に変換する（Claude CLI を使う）。

例: 「1年以内くらいで水道局と質疑調整したメール」
 → {"keywords_all":["水道局"], "keywords_any":["質疑","調整","協議","打合せ","問い合わせ"],
    "date_from":"2025-08-27", "date_to":"", "sender":"", "direction":"all",
    "explain":"水道局 と（質疑/調整/協議/…）を含む・2025-08-27以降"}

Streamlit（launchd常駐）から claude を呼ぶときの作法は
[[feedback_claude_subprocess]] に従う（env を絞らない・絶対パス・/usr/bin/python3 で起動）。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import date
from typing import Any, Dict

CLAUDE_BIN = shutil.which("claude") or "/opt/homebrew/bin/claude"
CLAUDE_TIMEOUT = 60

_PROMPT = """あなたは日本語のメール検索アシスタントです。ユーザーの依頼を、メール全文検索の\
条件に変換してください。今日は {today} です。

出力は**JSONだけ**（前後に説明やコードフェンスを付けない）。フィールド:
- "keywords_all": 必ず全て含む語のリスト（AND）。固有名詞・組織名・件名の核。
- "keywords_any": どれか含めばよい同義語・言い換えのリスト（OR）。依頼の動作/話題を広げる。
- "date_from": "YYYY-MM-DD" または ""（「1年以内」なら今日から1年前）
- "date_to": "YYYY-MM-DD" または ""
- "sender": 差出人で絞るなら文字列、なければ ""
- "direction": "received"（受信）/ "sent"（送信）/ "all"
- "explain": どう解釈したかを日本語1行で

注意:
- 全文検索は trigram（部分一致）なので**2文字以下の語は入れない**（3文字以上に）。
- keywords_any は**短い語幹**を優先（「質疑応答」より「質疑」、「協議事項」より「協議」）。
  短い方が部分一致で広く拾える。長い複合語だけにしない。
- keywords は多すぎると絞りすぎる。all は1〜2個、any は3〜6個を目安。
- 「〜について」「〜のメール」等の定型語は除く。

ユーザーの依頼: {query}
"""


def _extract_json(s: str) -> str:
    """前後に散文やコードフェンスが混じっていても JSON 本体を取り出す。

    claude が指示に反して「〜ですね。```json {...} ```」のように返すことがあるため、
    ①```json フェンス内 → ②最初の { から対応する } まで、の順で拾う。
    """
    s = (s or "").strip()
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", s, re.DOTALL)
    if m:
        return m.group(1)
    # 最初の { から、括弧の対応が取れる位置まで
    start = s.find("{")
    if start == -1:
        return s
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return s[start:i + 1]
    return s[start:]


def parse_query(query: str, today: str = "") -> Dict[str, Any]:
    """自然文 → 条件dict。失敗したら RuntimeError。"""
    today = today or date.today().strftime("%Y-%m-%d")
    prompt = _PROMPT.format(today=today, query=query.strip())
    cmd = [CLAUDE_BIN, "-p", prompt, "--output-format", "json",
           "--dangerously-skip-permissions", "--model", "sonnet"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=CLAUDE_TIMEOUT)
    except FileNotFoundError:
        raise RuntimeError("`claude` コマンドが見つかりません（Claude Code CLI を確認）。")
    except subprocess.TimeoutExpired:
        raise RuntimeError("AI検索が{}秒を超えたため中断しました。".format(CLAUDE_TIMEOUT))
    if proc.returncode != 0:
        raise RuntimeError("claude が失敗しました（code {}）\n{}".format(
            proc.returncode, (proc.stderr or "").strip()[:300]))

    outer = json.loads(proc.stdout)
    if outer.get("is_error"):
        raise RuntimeError("Claude がエラーを返しました: {}".format(outer.get("result")))
    text = _extract_json(outer.get("result", ""))
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise RuntimeError("AIの返答をJSONとして読めませんでした:\n{}".format(text[:300]))

    # 正規化（欠けても落ちないように）
    def _as_list(v):
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, str) and v.strip():
            return [v.strip()]
        return []

    all_kw = [k for k in _as_list(data.get("keywords_all")) if len(k) >= 3]
    any_kw = [k for k in _as_list(data.get("keywords_any")) if len(k) >= 3]
    direction = data.get("direction") or "all"
    if direction not in ("all", "received", "sent"):
        direction = "all"
    return {
        "keywords_all": all_kw,
        "keywords_any": any_kw,
        "date_from": (data.get("date_from") or "").strip(),
        "date_to": (data.get("date_to") or "").strip(),
        "sender": (data.get("sender") or "").strip(),
        "direction": direction,
        "explain": (data.get("explain") or "").strip(),
    }


def build_fts_expr(keywords_all, keywords_any) -> str:
    """FTS5 の MATCH 式を組む: "水道局" AND ("質疑" OR "協議" OR ...)。"""
    def q(term: str) -> str:
        return '"' + term.replace('"', '""') + '"'

    parts = []
    for k in keywords_all:
        parts.append(q(k))
    if keywords_any:
        parts.append("(" + " OR ".join(q(k) for k in keywords_any) + ")")
    return " AND ".join(parts)
