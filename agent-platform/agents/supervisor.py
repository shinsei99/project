"""01b 司令塔（中間レビューと調整）

役割: 高速チェッカーと法務監査の指摘を突き合わせ、**制作に入る前に原稿を直す**。
使用: Claude（Anthropic API / claude CLI）

なぜ要るか:
  司令塔が最初の計画だけ立てて後は口を出さないと、レビューや法務の指摘が
  「レポートに書かれただけ」で終わり、指摘を含んだままの原稿から画像・音声・動画が
  作られてしまう。作り直しのコストが一番大きいのは動画なので、その手前で直す。

ここで `deck` を書き換えると、以降の画像・パワポ・音声・動画・SNSすべてに反映される。
"""
from __future__ import annotations

from typing import Any, Dict, List

from core.base_agent import BaseAgent, register
from core.context import JobContext
from core.io_utils import write_json, write_text
from core.llm import complete_json

SYSTEM = """あなたは制作チームの責任者です。
レビューと法務の指摘を読み、原稿のどこをどう直すかを決めて、直した原稿を返します。

**絶対の制約: 成果物に但し書きを書き込まないこと。**
「※要確認」「※詳細はお問い合わせください」「※法令により～」のような注記・免責・
確認事項を本文や箇条書きに足してはいけません。読み手に配る物が注記だらけになり、
そのまま使えなくなるためです。

直し方は「表現そのものを直す」ことだけです。
  良い例: 「必ず儲かる」→「収益が見込めます」／根拠の無い数値は**削る**
  悪い例: 「必ず儲かる（※要確認）」のように注記を付け足す
根拠の無い数値・断定は、注記を付けるのではなく**書かない**でください。
法務の指摘は担当者への申し送りとして別に残るので、原稿に書き写す必要はありません。"""


@register
class SupervisorAgent(BaseAgent):
    key = "supervisor"
    name_ja = "司令塔（中間調整）"
    role_ja = "レビューと法務の指摘を突き合わせ、制作前に原稿を直す"
    icon = "🧭"
    uses = "Claude (Anthropic API / claude CLI)"
    llm_role = "reasoning"
    depends_on = ()
    depends_if_present = ("reviewer", "legal")

    def _run(self, ctx: JobContext) -> Dict[str, Any]:
        deck = ctx.state.get("deck")
        if not deck:
            return {"summary": "原稿がまだ無いため、調整はしていません", "degraded": True}

        issues = [i for i in (ctx.state.get("review", {}).get("issues") or [])
                  if i.get("severity") == "major"]
        # 法務は「表現そのものが違法・不当になる」重大なものだけ原稿に反映する。
        # 要注意・軽微は成果物に書き込まず、担当者へのコメントとして別に出す
        # （そうしないと配布物が注記だらけになる）。
        # 重大だけでなく**要注意も拾う**。免許番号の欠落のような法定表示は
        # 「要注意」で上がってくることがあり、重大だけ見ていると素通りする
        # （実際に免許番号なしの紙面が最終確認まで通った）。
        risks = [r for r in (ctx.state.get("legal", {}).get("risks") or [])
                 if r.get("severity") in ("critical", "major")]

        if not issues and not risks:
            self.log(ctx, "指摘が無いため、原稿はそのまま制作に回します")
            return {"summary": "指摘なし。原稿をそのまま制作へ回しました",
                    "data": {"revised": 0, "issues": 0, "risks": 0}}

        self.log(ctx, "レビュー%d件・法務%d件の指摘を読んで、原稿を直します"
                 % (len(issues), len(risks)))

        data, result, used_tools = self.ask_json(
            ctx, _build_prompt(deck, issues, risks), system=SYSTEM,
            max_tokens=6000, temperature=0.3)
        degraded = False
        revised_numbers: List[int] = []

        if isinstance(data, dict) and isinstance(data.get("slides"), list):
            self.log_llm(ctx, result)
            by_no = {s["no"]: s for s in deck["slides"]}
            for item in data["slides"]:
                if not isinstance(item, dict):
                    continue
                no = item.get("no")
                target = by_no.get(no)
                if not target:
                    continue
                changed = False
                for field in ("title", "bullets", "narration"):
                    value = item.get(field)
                    if value and value != target.get(field):
                        target[field] = value
                        changed = True
                if changed:
                    revised_numbers.append(no)
        else:
            degraded = True
            self.note_degraded(ctx, result.error or "修正案のJSONを解釈できませんでした")

        decision = {
            "issues": len(issues),
            "risks": len(risks),
            "revised_slides": sorted(revised_numbers),
            "note": (data or {}).get("note", "") if isinstance(data, dict) else "",
            "unresolved": (data or {}).get("unresolved", []) if isinstance(data, dict) else [],
        }
        # 原稿の文字では直せない指摘（「免許番号を入れる」など）は、
        # **制作部隊への申し送り**として残す。全部隊のプロンプト先頭に入る
        notes = [str(x) for x in (decision.get("unresolved") or []) if str(x).strip()]
        notes += [str(r.get("fix") or r.get("issue") or "")
                  for r in risks if r.get("fix") or r.get("issue")]
        if notes:
            ctx.state["production_notes"] = notes[:6]
            self.log(ctx, "原稿では直せない%d件は、制作部隊への申し送りにしました"
                     % len(notes[:6]))
        ctx.state["supervision"] = decision
        write_json(ctx.dir("plan") / "deck.json", deck)
        write_json(ctx.dir("reports") / "supervision.json", decision)
        path = write_text(ctx.dir("reports") / "supervision.md", _to_markdown(decision))
        ctx.add_artifact("markdown", path, label="司令塔の調整記録", agent=self.key)

        if revised_numbers:
            for no in revised_numbers:
                self.progress(ctx, "%d枚目の原稿を指摘に沿って直しました" % no)
            summary = "指摘%d件を反映し、%d枚の原稿を直してから制作に回しました" % (
                len(issues) + len(risks), len(revised_numbers))
        else:
            summary = "指摘%d件を確認しましたが、原稿の自動修正はできませんでした" % (
                len(issues) + len(risks))
            degraded = True

        return {"summary": summary, "detail": decision.get("note", ""),
                "data": decision, "degraded": degraded}


def _build_prompt(deck, issues, risks) -> str:
    slides = "\n".join(
        "[%d] %s\n  箇条書き: %s\n  ナレーション: %s"
        % (s["no"], s["title"], " / ".join(s.get("bullets", [])), s.get("narration", ""))
        for s in deck["slides"]
    )
    review_lines = "\n".join(
        "- [%s枚目] %s → %s" % (i.get("slide", "-"), i.get("message", ""), i.get("fix", ""))
        for i in issues) or "（なし）"
    legal_lines = "\n".join(
        "- [%s] %s → %s" % (r.get("law", ""), r.get("message", ""), r.get("fix", ""))
        for r in risks) or "（なし）"
    return """次の原稿を、指摘に沿って直してください。

--- 現在の原稿 ---
%s

--- レビューの指摘（要対応） ---
%s

--- 法務の指摘（表現を直すべき重大なものだけ。注記の追加はしないこと） ---
%s

直したスライドだけを次のJSON形式で返してください（直す必要がないスライドは含めない）。
{"slides": [{"no": 1, "title": "直した見出し",
             "bullets": ["直した箇条書き"], "narration": "直したナレーション"}],
 "note": "どういう方針で直したか（1〜2行）",
 "unresolved": ["原稿の修正では解決できず、人の判断が要る指摘"]}

制約:
- **「※要確認」などの注記・但し書きを足さない**（別途コメントとして出すので不要）
- 指摘に無い箇所は変えない
- 新しい事実・数値を作らない（根拠が無いものは削るか「要確認」と書く）
- ナレーションは話し言葉のまま、長さも大きく変えない""" % (slides, review_lines, legal_lines)


def _to_markdown(decision: Dict[str, Any]) -> str:
    lines = ["# 司令塔の調整記録", "",
             "- 反映したレビュー指摘: %d件" % decision.get("issues", 0),
             "- 反映した法務指摘: %d件" % decision.get("risks", 0),
             "- 直したスライド: %s" % (", ".join("%d枚目" % n for n in decision.get("revised_slides", []))
                                       or "なし"),
             ""]
    if decision.get("note"):
        lines += ["## 方針", "", decision["note"], ""]
    unresolved = decision.get("unresolved") or []
    lines += ["## 人の判断が必要な残り", ""]
    lines += ["- %s" % u for u in unresolved] or ["- （なし）"]
    return "\n".join(lines) + "\n"
