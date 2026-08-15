"""08 高速チェッカー・壁打ち役

役割: 構成原稿とナレーションの、事実の飛躍・論理の破綻・誤字・冗長を高速で洗う。
使用: Groq API（Llama系・超高速推論）／未設定時は他のLLM、それも無ければ機械的チェック

LLMが使えない場合でも空振りにしないため、文字数・空要素・禁則といった
機械的に判定できる項目はローカルで必ずチェックする。
"""
from __future__ import annotations

from typing import Any, Dict, List

from core.base_agent import BaseAgent, register
from core.context import JobContext
from core.io_utils import write_json, write_text
from core.llm import complete_json

SYSTEM = """あなたは容赦のないレビュアーです。速度優先で、直すべき点だけを指摘します。
褒める必要はありません。指摘は具体的に、どのスライドの何をどう直すかまで書いてください。"""

NARRATION_MAX = 260   # 1枚あたりの読み上げ文字数の上限（約45秒）
BULLET_MAX = 34       # 箇条書き1行の文字数上限（スライドで折り返さない目安）


@register
class SpeedReviewerAgent(BaseAgent):
    key = "reviewer"
    name_ja = "高速チェッカー"
    role_ja = "原稿の誤り・論理破綻・冗長を高速に検証する"
    icon = "⚡"
    uses = "Groq API（Llama系・超高速推論）"
    llm_role = "fast"    # 名前のとおり速さ優先。Geminiで7秒（claude CLIだと70秒）
    depends_on = ()
    depends_if_present = ("planner", "poster")

    def _run(self, ctx: JobContext) -> Dict[str, Any]:
        deck = ctx.state.get("deck")
        if not deck:
            return {"summary": "構成がまだ無いため、チェックはしていません", "degraded": True}

        self.log(ctx, "原稿を機械チェックしています（文字数・空欄・重複）")
        issues: List[Dict[str, Any]] = _mechanical_checks(deck)

        self.log(ctx, "AIで論理と表現をチェックしています")
        data, result = complete_json(_build_prompt(deck), system=SYSTEM,
                                     role=self.llm_role, max_tokens=3000, temperature=0.2)
        degraded = False
        if isinstance(data, dict) and isinstance(data.get("issues"), list):
            for item in data["issues"]:
                if isinstance(item, dict):
                    issues.append({
                        "slide": item.get("slide", 0),
                        "severity": item.get("severity", "minor"),
                        "type": item.get("type", "内容"),
                        "message": item.get("message", ""),
                        "fix": item.get("fix", ""),
                        "source": result.provider or "llm",
                    })
            self.log_llm(ctx, result)
        else:
            degraded = True
            self.note_degraded(ctx, result.error or "指摘のJSONを解釈できませんでした")

        review = {"issues": issues,
                  "major": sum(1 for i in issues if i.get("severity") == "major")}
        ctx.state["review"] = review
        write_json(ctx.dir("reports") / "review.json", review)
        path = write_text(ctx.dir("reports") / "review.md", _to_markdown(issues))
        ctx.add_artifact("markdown", path, label="レビュー指摘一覧", agent=self.key)

        if not issues:
            return {"summary": "指摘はありませんでした", "data": review, "degraded": degraded}
        return {
            "summary": "指摘 %d件（うち要対応 %d件）を洗い出しました"
                       % (len(issues), review["major"]),
            "detail": "; ".join(i["message"] for i in issues[:3]),
            "data": review,
            "degraded": degraded,
        }


def _mechanical_checks(deck: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues = []
    seen_titles = {}
    for s in deck.get("slides", []):
        no = s.get("no")
        if not s.get("bullets"):
            issues.append({"slide": no, "severity": "major", "type": "空欄",
                           "message": "%d枚目に箇条書きがありません" % no,
                           "fix": "要点を3つ書く", "source": "mechanical"})
        for b in s.get("bullets", []):
            if len(b) > BULLET_MAX:
                issues.append({"slide": no, "severity": "minor", "type": "文字数",
                               "message": "%d枚目の箇条書きが%d文字と長すぎます（目安%d文字）"
                                          % (no, len(b), BULLET_MAX),
                               "fix": "2行に分けるか短くする", "source": "mechanical"})
        narration = s.get("narration", "")
        if len(narration) > NARRATION_MAX:
            issues.append({"slide": no, "severity": "minor", "type": "尺",
                           "message": "%d枚目のナレーションが%d文字（約%d秒）と長めです"
                                      % (no, len(narration), len(narration) / 5.5),
                           "fix": "1枚を2枚に分割する", "source": "mechanical"})
        if not narration.strip():
            issues.append({"slide": no, "severity": "major", "type": "空欄",
                           "message": "%d枚目のナレーションが空です" % no,
                           "fix": "原稿を書く", "source": "mechanical"})
        title = s.get("title", "")
        if title in seen_titles:
            issues.append({"slide": no, "severity": "minor", "type": "重複",
                           "message": "%d枚目の見出しが%d枚目と同じです（%s）"
                                      % (no, seen_titles[title], title),
                           "fix": "見出しを書き分ける", "source": "mechanical"})
        seen_titles[title] = no
    return issues


def _build_prompt(deck: Dict[str, Any]) -> str:
    body = []
    for s in deck.get("slides", []):
        body.append("[%d] %s\n  箇条書き: %s\n  ナレーション: %s"
                    % (s.get("no"), s.get("title"),
                       " / ".join(s.get("bullets", [])), s.get("narration", "")))
    return """次のプレゼン原稿をレビューし、直すべき点だけを挙げてください。

%s

観点: 事実の飛躍／論理の飛び／数字の根拠不明／言い過ぎ／冗長／誤字。
次のJSON形式で出力してください（指摘が無ければ issues は空配列）。
{"issues": [{"slide": 1, "severity": "major|minor", "type": "種別",
             "message": "何が問題か", "fix": "どう直すか"}]}""" % "\n".join(body)


def _to_markdown(issues: List[Dict[str, Any]]) -> str:
    if not issues:
        return "# レビュー結果\n\n指摘はありません。\n"
    lines = ["# レビュー結果", "", "| スライド | 重要度 | 種別 | 指摘 | 直し方 |",
             "|---|---|---|---|---|"]
    for i in issues:
        lines.append("| %s | %s | %s | %s | %s |" % (
            i.get("slide", "-"),
            "要対応" if i.get("severity") == "major" else "軽微",
            i.get("type", ""), i.get("message", ""), i.get("fix", "")))
    return "\n".join(lines) + "\n"
