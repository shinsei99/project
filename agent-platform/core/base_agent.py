"""全エージェントの共通土台。

各部隊は `_run()` だけを実装する。時間計測・例外の握りつぶし・
進捗イベントの発行（日本語）はここで共通処理する。

進捗メッセージの方針:
  - 画面に出るのは「日本語の説明文」だけ。スタックトレース等の技術情報は
    level="debug" で出し、UI では既定で隠す。
"""
from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .context import JobContext


@dataclass
class AgentResult:
    key: str
    name_ja: str
    ok: bool = True
    degraded: bool = False          # 縮退（キー無しでダミー生成）で通ったか
    summary: str = ""               # 画面に出す1行の結果（日本語）
    detail: str = ""                # 補足（複数行可）
    data: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    elapsed: float = 0.0


class BaseAgent:
    key = "agent"
    name_ja = "エージェント"
    role_ja = ""
    icon = "•"
    uses = ""              # 使用API・技術（画面表示用）
    # llm_role の決め方 = 「速さ」ではなく「失敗したときの損失」で決める。
    #   reasoning … 成果物そのものを作る部隊（司令塔・構成・掲示物・チラシ・法務・最終確認）
    #               ここをケチると成果物の質が直接落ちる
    #   fast/light … 機械的な検査・短文生成（チェッカー・SNS）
    # 一度すべてを速いモデルに寄せたところ、誘導文も理由も無い威圧的な貼り紙が出た。
    llm_role = "reasoning"

    # --- 実行制御 ---
    # depends_on: この部隊が待つ相手。ここが空なら他と同時に走れる。
    #             一列に並べるのをやめ、依存関係だけを宣言して並列実行させるため。
    depends_on: tuple = ()
    # depends_if_present: ここに挙げた相手のうち「今回動くもの」を待つ。
    # 成果物の型によって前工程が入れ替わる場合に使う
    # （掲示物では構成ライターが動かず、代わりに掲示物制作が原稿を作る）。
    # これが無いと、待つ相手がいない＝即実行になり、制作前に法務や検品が走る。
    depends_if_present: tuple = ()
    # deliverable: この部隊が作る成果物の種類。司令塔が「今回は要らない」と
    #              判断した成果物の部隊は最初から起動しない（チラシ1枚に動画部隊は不要）。
    #              None は常時実行（司令塔・構成・チェック・検品など）。
    deliverable: Optional[str] = None

    # --- 各部隊が実装する ---
    def _run(self, ctx: JobContext) -> Dict[str, Any]:
        """戻り値: {"summary": str, "detail": str, "data": dict, "degraded": bool}"""
        raise NotImplementedError

    # --- 共通処理 ---
    def run(self, ctx: JobContext) -> AgentResult:
        started = time.time()
        ctx.emit({"type": "agent_start", "agent": self.key,
                  "name_ja": self.name_ja, "icon": self.icon, "uses": self.uses,
                  "message": "%s を開始しました" % self.name_ja})
        try:
            payload = self._run(ctx) or {}
            result = AgentResult(
                key=self.key,
                name_ja=self.name_ja,
                ok=True,
                degraded=bool(payload.get("degraded")),
                summary=payload.get("summary", "完了しました"),
                detail=payload.get("detail", ""),
                data=payload.get("data", {}) or {},
                elapsed=time.time() - started,
            )
        except Exception as exc:
            result = AgentResult(
                key=self.key, name_ja=self.name_ja, ok=False,
                summary="%s でエラーが発生したため、この工程を飛ばしました" % self.name_ja,
                error="%s: %s" % (type(exc).__name__, exc),
                elapsed=time.time() - started,
            )
            self.log(ctx, traceback.format_exc(), level="debug")
        ctx.emit({
            "type": "agent_end", "agent": self.key, "name_ja": self.name_ja,
            "ok": result.ok, "degraded": result.degraded, "elapsed": result.elapsed,
            "message": result.summary,
            "level": "error" if not result.ok else ("warn" if result.degraded else "success"),
        })
        return result

    # --- 道具つきでLLMに聞く（全部隊の共通入口） ---
    # wants_tools=True の部隊だけが、claude CLI の道具（Web取得・検索・資料読み）を持つ。
    #
    # 重要（実測）: 道具を使う経路は claude CLI 固定になる。claude CLI は質が高い代わりに
    # 1回 40〜100秒かかり、同じ仕事を Gemini は 25秒で返す（法務チェックの実測で3.4倍差）。
    # 全部隊を道具つきにしていた頃は「高速チェッカー」が70秒かかっていた。
    # → 道具が要る部隊（URLを読む・規制を調べる）だけ True にし、
    #   それ以外は速いモデルに回す。`.env` の AP_AGENT_TOOLS=all で全部隊に戻せる。
    wants_tools = False
    use_tools = True   # 互換のため残す（False にすると道具を一切使わない）

    # produces_deliverable=True の部隊は、成果物の品質基準を自動でプロンプトに受け取る。
    # 型（テンプレート）を増やすより、**判断の基準を共有する**方があらゆる成果物に効く。
    produces_deliverable = False

    # 部隊ごとに持たせる道具。要らない道具を渡すと、その分だけ遅くなる。
    #   needs_web   … WebFetch / WebSearch
    #   needs_files … 資料フォルダの Read / Glob / Grep
    #   needs_mcp   … MCPサーバー（ブラウザ操作など）。npx起動のぶん一番重い
    needs_web = True
    needs_files = True
    needs_mcp = False

    def tool_policy(self, ctx: JobContext):
        """司令塔が決めたこの部隊の道具。決めていなければ None（＝クラス既定）。

        依頼によって要る道具は変わる（URLが無ければブラウザは無駄、社内資料なら
        法務のWeb検索も要らない）。道具を1つ渡すごとに claude CLI 固定になって
        数十秒かかるので、司令塔に「今回どの部隊に何を持たせるか」を決めさせる。

        語彙: web（取得・検索）/ files（資料読み）/ browser（MCPブラウザ）/ none
        """
        plan = ctx.state.get("plan") or {}
        raw = (plan.get("agent_tools") or {}).get(self.key)
        if raw is None:
            return None
        if isinstance(raw, str):
            raw = [raw]
        names = {str(x).strip().lower() for x in raw}
        if not names or "none" in names or "なし" in names:
            return {"web": False, "files": False, "mcp": False, "any": False}
        return {"web": bool(names & {"web", "search", "webfetch", "websearch"}),
                "files": "files" in names or "資料" in names,
                "mcp": bool(names & {"browser", "mcp", "playwright"}),
                "any": True}

    def toolset(self, ctx: JobContext) -> Dict[str, Any]:
        """この部隊に渡す道具。

        Bash / Write / Edit は渡さない（`--disallowedTools` で明示的に禁止）。
        部隊が勝手にコマンドを実行したりPCを書き換えるのは事故のもとで、
        成果物の生成には要らないため。必要なら .env で外せる。
        """
        policy = self.tool_policy(ctx)
        needs_web = policy["web"] if policy else self.needs_web
        needs_files = policy["files"] if policy else self.needs_files
        needs_mcp = policy["mcp"] if policy else self.needs_mcp

        dirs = []
        if needs_files:
            input_dir = ctx.dir("input")
            try:
                if any(input_dir.iterdir()):
                    dirs.append(input_dir)
            except OSError:
                pass
        return {"web": needs_web, "dirs": dirs, "mcp": needs_mcp}

    def ask_json(self, ctx: JobContext, prompt: str, system: Optional[str] = None,
                 role: Optional[str] = None, max_tokens: int = 4000,
                 temperature: float = 0.4, tool_system: Optional[str] = None):
        """JSONで答えさせる。道具が使えるなら道具つきで、駄目なら通常経路で。

        戻り値は (データ or None, LLMResult, 道具を使ったか)。
        """
        from .config import get_settings
        from .llm import complete_json

        prompt = _with_design_rules(self, ctx, prompt)
        prompt = _with_revision(ctx, prompt)
        st = get_settings()
        policy = self.tool_policy(ctx)
        wants = policy["any"] if policy else (self.wants_tools or st.agent_tools_all)
        want_tools = self.use_tools and st.agent_tools_enabled and wants
        if want_tools and st.provider_available("claude_cli"):
            data, result = complete_json(
                prompt, system=tool_system or system, role="tools",
                max_tokens=max_tokens, temperature=temperature,
                tools=self.toolset(ctx))
            if data is not None:
                self.log(ctx, "道具（Web・資料）を使って考えました", level="debug")
                return data, result, True
            self.log(ctx, "道具つきの応答が読めなかったため、通常の経路で考え直します",
                     level="debug")

        data, result = complete_json(prompt, system=system,
                                     role=role or self.llm_role,
                                     max_tokens=max_tokens, temperature=temperature)
        return data, result, False

    # --- 進捗の書き出し ---
    def log(self, ctx: JobContext, message: str, level: str = "info") -> None:
        ctx.log(message, level=level, agent=self.key)

    def progress(self, ctx: JobContext, message: str, current: Optional[int] = None,
                 total: Optional[int] = None) -> None:
        """「3/8 枚目のスライド画像を生成中です」のような途中経過。"""
        ctx.emit({"type": "progress", "agent": self.key, "name_ja": self.name_ja,
                  "message": message, "current": current, "total": total,
                  "level": "info"})

    # --- LLMが使えないときの共通フォールバック ---
    def note_degraded(self, ctx: JobContext, reason: str) -> None:
        self.log(ctx, "APIが使えないため簡易生成に切り替えました（%s）" % reason, level="warn")

    def log_llm(self, ctx: JobContext, result) -> None:
        """どのAIが答えたか／途中でどれが落ちたかを残す。

        フォールバックは黙って起きるので、記録しないと「なぜ遅いのか」
        「なぜGeminiを設定したのに使われないのか」が後から追えない。
        """
        for failure in getattr(result, "failures", []):
            self.log(ctx, "先に試したAIが応答しませんでした（%s）" % failure, level="debug")
        if getattr(result, "ok", False):
            self.log(ctx, "%s が応答しました（%s）"
                     % (result.provider, result.model), level="debug")


def _with_design_rules(agent, ctx: JobContext, prompt: str) -> str:
    """成果物を作る部隊に、全部隊共通の品質基準を渡す。

    同じ基準を最終確認も使うので、「作る側と見る側の物差しが違う」ことが起きない。
    """
    if not getattr(agent, "produces_deliverable", False):
        return prompt
    from .company import describe_for_prompt as company_info
    from .design import producing_rules
    from .memory import describe_for_prompt

    genre = (ctx.state.get("plan") or {}).get("genre", "")
    parts = [producing_rules(genre), company_info()]
    lessons = describe_for_prompt(genre)
    if lessons:
        parts.append(lessons)
    parts.append(prompt)
    return "\n\n---\n".join(parts)


def _with_revision(ctx: JobContext, prompt: str) -> str:
    """人からの修正指示があれば、全部隊のプロンプトの先頭に差し込む。

    作り直しのたびに各部隊へ手で伝えるのは現実的でないので、
    ここ1か所で全部隊に効くようにしている。
    """
    parts = []
    # 司令塔（中間調整）が制作に回した申し送り。原稿の文字だけでは直せない
    # 「免許番号を必ず入れる」のような**構造の指示**がここに来る
    notes = [str(x).strip() for x in (ctx.state.get("production_notes") or [])
             if str(x).strip()]
    if notes:
        parts.append("【司令塔からの申し送り（必ず守ること）】\n"
                     + "\n".join("- %s" % x for x in notes[:6]))
    revision = (ctx.options.get("revision") or "").strip()
    if revision:
        parts.append("【前回の成果物への修正指示（最優先で反映すること）】\n%s" % revision)
    if not parts:
        return prompt
    return "\n\n".join(parts) + "\n\n---\n" + prompt


AGENT_REGISTRY: List[type] = []


def register(cls):
    """デコレータ。定義したエージェントをレジストリへ登録する。"""
    AGENT_REGISTRY.append(cls)
    return cls
