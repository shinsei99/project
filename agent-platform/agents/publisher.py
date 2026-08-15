"""09 SNS・メディア発信部隊

役割: 成果物をもとに、X（旧Twitter）投稿文、YouTube概要欄、ブログ告知文を書く。
使用: 各種軽量LLM（Groq / Gemini など。無ければ原稿から機械的に組み立てる）

投稿そのものは行わない。人が内容を確認してから出す運用にしている
（誤情報や法務指摘が残ったまま外部発信されるのを避けるため）。
"""
from __future__ import annotations

from typing import Any, Dict

from core.base_agent import BaseAgent, register
from core.context import JobContext
from core.io_utils import write_json, write_text
from core.llm import complete_json

SYSTEM = """あなたはSNS運用担当です。誇張せず、事実に基づいた告知文を書きます。
Xは140字以内、YouTube概要欄は章立てつき、ブログ告知は見出しつきで書いてください。"""


@register
class ContentPublisherAgent(BaseAgent):
    key = "publisher"
    name_ja = "SNS発信部隊"
    role_ja = "X・YouTube概要欄・ブログ告知文の作成"
    icon = "📣"
    uses = "軽量LLM（Groq / Gemini など）"
    llm_role = "light"   # 短文生成。速い相手で十分
    depends_on = ("supervisor",)
    deliverable = "sns"

    def _run(self, ctx: JobContext) -> Dict[str, Any]:
        deck = ctx.state.get("deck")
        if not deck:
            return {"summary": "元になる原稿が無いため、告知文は作っていません", "degraded": True}

        self.log(ctx, "X・YouTube・ブログ用の告知文を書いています")
        data, result, used_tools = self.ask_json(
            ctx, _build_prompt(ctx, deck), system=SYSTEM,
            max_tokens=2500, temperature=0.7)
        degraded = False
        if not isinstance(data, dict) or not data.get("x_post"):
            degraded = True
            self.note_degraded(ctx, result.error or "告知文のJSONを解釈できませんでした")
            data = _fallback_posts(deck)
        else:
            self.log_llm(ctx, result)

        # Xの文字数だけは機械的に担保する
        if len(data.get("x_post", "")) > 140:
            data["x_post"] = data["x_post"][:137] + "…"
            self.log(ctx, "X投稿文が140字を超えていたため短縮しました", level="warn")

        ctx.state["social"] = data
        write_json(ctx.dir("social") / "social.json", data)
        path = write_text(ctx.dir("social") / "social.md", _to_markdown(data))
        ctx.add_artifact("markdown", path, label="SNS告知文", agent=self.key)

        return {
            "summary": "告知文を3種類（X・YouTube概要欄・ブログ）用意しました",
            "detail": data.get("x_post", "")[:60],
            "data": data,
            "degraded": degraded,
        }


def _build_prompt(ctx: JobContext, deck: Dict[str, Any]) -> str:
    outline = "\n".join("%d. %s: %s" % (s["no"], s["title"], " / ".join(s.get("bullets", [])))
                        for s in deck.get("slides", []))
    has_video = bool(ctx.state.get("video"))
    return """次の資料を告知する文章を書いてください。

【タイトル】{title}
【構成】
{outline}

【動画】{video}

次のJSON形式で出力してください。
{{
  "x_post": "X投稿文（140字以内・ハッシュタグ2〜3個込み）",
  "hashtags": ["#タグ"],
  "youtube_title": "YouTube動画タイトル（40字以内）",
  "youtube_description": "YouTube概要欄（章立て・タイムスタンプの雛形込み）",
  "blog_title": "ブログ記事タイトル",
  "blog_body": "ブログ告知本文（Markdown・400字程度）"
}}""".format(title=deck.get("title", ""), outline=outline,
             video="あり（解説動画を公開予定）" if has_video else "なし")


def _fallback_posts(deck: Dict[str, Any]) -> Dict[str, Any]:
    title = deck.get("title", "資料")
    heads = [s["title"] for s in deck.get("slides", [])][:5]
    return {
        "x_post": ("【%s】資料を作成しました。%s ほか。詳細はスライドをご覧ください。"
                   % (title, "・".join(heads[:2])))[:140],
        "hashtags": ["#資料公開"],
        "youtube_title": title[:40],
        "youtube_description": "\n".join(["■ 内容"] + ["・%s" % h for h in heads]),
        "blog_title": "%s について" % title,
        "blog_body": "\n".join(["## %s" % title, ""] + ["- %s" % h for h in heads]),
    }


def _to_markdown(data: Dict[str, Any]) -> str:
    return "\n".join([
        "# SNS・メディア告知文",
        "",
        "> そのまま投稿せず、内容を確認してから使ってください。",
        "",
        "## X（旧Twitter）",
        "",
        data.get("x_post", ""),
        "",
        "ハッシュタグ: %s" % " ".join(data.get("hashtags", []) or []),
        "",
        "## YouTube",
        "",
        "**タイトル**: %s" % data.get("youtube_title", ""),
        "",
        "```",
        data.get("youtube_description", ""),
        "```",
        "",
        "## ブログ",
        "",
        "**タイトル**: %s" % data.get("blog_title", ""),
        "",
        data.get("blog_body", ""),
        "",
    ])
