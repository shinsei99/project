"""03 企画・プレゼン構成ライター

役割: 調査結果をもとに、スライド構成・ナレーション原稿・画像指示（コンテ）を書く。
使用: 高精度推論モデル（Claude / GPT-4o）

ここで作る `deck` が、以降の画像・パワポ・音声・動画・SNSすべての原本になる。
"""
from __future__ import annotations

from typing import Any, Dict, List

from core.base_agent import BaseAgent, register
from core.context import JobContext
from core.io_utils import write_json, write_text
from core.llm import complete_json

SIGNAGE_SYSTEM = """あなたは掲示物（貼り紙・案内表示）の文言を決める担当です。
出すのは**印刷される文字そのもの**だけ。レイアウトの指示や作り方の説明は書きません。
言葉は短く、命令ではなく事実と依頼で書きます。遠くから読めることが最優先です。"""

SYSTEM = """あなたは説得力のあるプレゼンを設計する構成ライターです。
1枚のスライドで主張は1つ。箇条書きは短く、ナレーションは話し言葉で書きます。
ナレーションはスライドの文字を読み上げるのではなく、意味を補って語ってください。
- **「※要確認」「※詳細はお問い合わせください」のような注記・免責を書かない**
  （法務のコメントは別に出すので、成果物には入れない）"""


@register
class PresentationPlannerAgent(BaseAgent):
    key = "planner"
    name_ja = "企画・構成ライター"
    role_ja = "スライド構成・ナレーション原稿・画像コンテの執筆"
    icon = "📝"
    uses = "高精度推論モデル（Claude / GPT-4o）"
    llm_role = "reasoning"
    produces_deliverable = True
    depends_on = ("orchestrator", "researcher")

    def _run(self, ctx: JobContext) -> Dict[str, Any]:
        plan = ctx.state.get("plan", {})
        if plan.get("genre") == "signage":
            return self._run_signage(ctx, plan)
        research = ctx.state.get("research", {})
        count = int(plan.get("slide_count") or 8)

        self.log(ctx, "スライド%d枚の構成とナレーション原稿を書いています" % count)

        prompt = _build_prompt(ctx.brief, plan, research, count)
        data, result, used_tools = self.ask_json(
            ctx, prompt, system=SYSTEM, max_tokens=8000, temperature=0.6,
            tool_system=SYSTEM + "\n不明な点があれば WebSearch/WebFetch で確かめ、"
                                 "資料フォルダの写真や数字も見てから書いてください。")

        degraded = False
        if not isinstance(data, dict) or not data.get("slides"):
            degraded = True
            self.note_degraded(ctx, result.error or "構成のJSONを解釈できませんでした")
            data = _fallback_deck(plan, count)
        else:
            self.log_llm(ctx, result)

        slides = _normalize_slides(data.get("slides", []), plan)
        deck = {
            "title": data.get("title") or plan.get("title", "無題"),
            "subtitle": data.get("subtitle") or plan.get("subtitle", ""),
            "slides": slides,
        }
        ctx.state["deck"] = deck

        write_json(ctx.dir("plan") / "deck.json", deck)
        script_path = write_text(ctx.dir("plan") / "narration.md", _to_script(deck))
        ctx.add_artifact("markdown", script_path, label="ナレーション原稿", agent=self.key)

        chars = sum(len(s["narration"]) for s in slides)
        return {
            "summary": "%d枚の構成とナレーション（合計%d文字・読み上げ約%d秒）を書きました"
                       % (len(slides), chars, chars / 5.5),
            "detail": " / ".join(s["title"] for s in slides[:5]),
            "data": {"slide_count": len(slides), "chars": chars},
            "degraded": degraded,
        }


    def _run_signage(self, ctx: JobContext, plan) -> Dict[str, Any]:
        """掲示物は「紙に載る文言」だけを書く。

        スライド構成（見出し＋箇条書き＋ナレーション）を作ってはいけない。
        以前それをやった結果、「上部に極太ゴシックで『駐輪禁止』」という
        **レイアウト指示がそのまま紙面に印刷された**。
        ここで出すのは、印刷される文字そのものだけ。
        """
        self.log(ctx, "掲示物に載せる文言を決めます（レイアウト指示は書きません）")
        data, result, _ = self.ask_json(
            ctx, _build_signage_prompt(ctx.brief, plan), system=SIGNAGE_SYSTEM,
            max_tokens=2000, temperature=0.3)

        degraded = False
        if not isinstance(data, dict) or not data.get("headline"):
            degraded = True
            self.note_degraded(ctx, result.error or "文言のJSONを解釈できませんでした")
            data = _fallback_signage(ctx.brief, plan)

        notes = [str(x) for x in (data.get("notes") or []) if str(x).strip()][:4]
        signage = {
            "headline": str(data.get("headline", ""))[:12],
            "sub": str(data.get("sub", ""))[:24],
            "message": str(data.get("message", ""))[:40],
            "notes": notes,
            "contact": str(data.get("contact", ""))[:60],
            "english": str(data.get("english", ""))[:40],
            "pictogram": str(data.get("pictogram", "")).strip(),
        }
        ctx.state["signage"] = signage
        # 後続（法務・チェック）が読めるよう、最小限の deck も残す
        ctx.state["deck"] = {
            "title": signage["headline"], "subtitle": signage["sub"],
            "slides": [{"no": 1, "title": signage["headline"],
                        "bullets": [signage["message"]] + notes,
                        "narration": "", "image_prompt": ""}]}

        write_json(ctx.dir("plan") / "signage.json", signage)
        path = write_text(ctx.dir("plan") / "signage.md",
                          "# 掲示物の文言\n\n- 見出し: %s\n- 補助: %s\n- 本文: %s\n- 注記: %s\n- 連絡先: %s\n"
                          % (signage["headline"], signage["sub"], signage["message"],
                             " / ".join(notes) or "なし", signage["contact"] or "なし"))
        ctx.add_artifact("markdown", path, label="掲示物の文言", agent=self.key)

        return {
            "summary": "掲示物の文言を決めました（見出し「%s」）" % signage["headline"],
            "detail": signage["message"],
            "data": signage,
            "degraded": degraded,
        }


def _build_signage_prompt(brief, plan) -> str:
    return """次の掲示物に**印刷する文字**を決めてください。

【依頼】
{brief}
【貼る場所・読む人】{audience}

掲示物は遠くから一目で伝わることが全てです。文字数は少ないほど良い。

ただし**禁止するだけの貼り紙にしないこと**。読む人が次にどうすればよいか分からず、
ただ威圧されたと感じるだけになります。必ず
  ・代わりにどうすればよいか（正しい置き場所・正しいやり方）
  ・なぜそうしてほしいのか（避難経路、通行の妨げ、安全）
を短く添えてください。

**撤去・処分など段階的な対応がある場合は steps に分けて書いてください。**
文章で「放置車両は撤去します」と書くより、「①警告札を貼付 →②7日間お待ちします
→③撤去・保管します」と段階で示す方が伝わり、実際に撤去するときの根拠にもなります。

**外国語の併記はしません。** 日本語だけで書いてください。

次のJSON形式で、**紙に印刷される文字そのもの**を出してください。
{{
  "headline": "一番大きく出す言葉（4〜8文字。例: 駐輪禁止）",
  "sub": "見出しの下に小さく添える英字など（無ければ空文字。例: NO BICYCLE PARKING）",
  "message": "次に大きい一文（20文字以内。例: 無断駐輪は撤去します）",
  "reason": "なぜそうしてほしいか（30文字以内。例: 通路・避難経路の確保のため、ご協力をお願いします）",
  "steps": ["違反した場合の対応を段階で。2〜4個。各12文字以内。「／」で改行できる",
            "例: 警告札を／貼付します", "例: 7日間／お待ちします", "例: 撤去・保管／します"],
  "steps_caption": "段階の見出し（例: 放置された場合の対応）。stepsが無ければ空文字",
  "deadline_label": "記入欄に置く期限の名前（例: 撤去予定日）。不要なら空文字",
  "notes": ["補足があれば。無ければ空配列"],
  "contact": "問い合わせ先の行（例: 管理会社 〇〇 TEL 000-000-0000）",
  "pictograms": ["no_bicycle / no_motorcycle / no_parking / no_entry / no_trash / no_smoking / quiet から1〜2個。",
                 "対象が複数あるなら必ず複数選ぶ（自転車とバイクの両方が対象なら2つ）"]
}}

**禁止事項**:
- 「上部に極太ゴシックで」のようなレイアウトの指示を書かない。**印刷される文字だけ**
- 「※要確認」などの注記を足さない
- 連絡先が依頼文に無ければ contact は空文字にする（勝手に電話番号を作らない）""".format(
        brief=brief, audience=plan.get("audience", ""))


def _fallback_signage(brief, plan):
    import tools

    picto = tools.pictograms.guess(brief)
    heads = {"no_bicycle": ("駐輪禁止", "NO BICYCLE PARKING", "無断駐輪は撤去します"),
             "no_parking": ("駐車禁止", "NO PARKING", "無断駐車は撤去します"),
             "no_trash": ("ゴミ出し厳守", "", "決められた日時にお願いします"),
             "no_smoking": ("禁煙", "NO SMOKING", "館内は全面禁煙です"),
             "quiet": ("お静かに", "", "夜間の騒音にご配慮ください"),
             "no_entry": ("立入禁止", "NO ENTRY", "関係者以外の立入を禁じます")}
    head, sub, msg = heads.get(picto, heads["no_entry"])
    return {"headline": head, "sub": sub, "message": msg, "notes": [],
            "contact": "", "pictograms": tools.pictograms.guess_all(brief)}


def _build_prompt(brief, plan, research, count) -> str:
    findings = research.get("findings", [])
    facts = "\n".join(
        "- %s → %s%s" % (f.get("question", ""), f.get("answer", ""),
                         "" if f.get("verified") else "（要確認）")
        for f in findings[:12]
    ) or "（調査結果なし）"
    return """次の企画で、スライド{count}枚のプレゼンを構成してください。

【依頼】
{brief}

【タイトル】{title}
【対象】{audience}
【目的】{goal}
【トーン】{tone}
【ビジュアル方針】{visual}

【調査で分かっていること】
{facts}

次のJSON形式で出力してください。slides はちょうど{count}件。
{{
  "title": "表紙タイトル",
  "subtitle": "サブタイトル",
  "slides": [
    {{
      "no": 1,
      "title": "スライド見出し（20文字以内）",
      "bullets": ["箇条書き（1行30文字以内）", "3〜4項目"],
      "narration": "このスライドで話す原稿（120〜200文字・話し言葉）",
      "image_prompt": "このスライドの背景画像を生成するための英語プロンプト（人物の顔・実在ロゴ・文字は入れない）"
    }}
  ]
}}""".format(
        count=count, brief=brief, title=plan.get("title", ""),
        audience=plan.get("audience", ""), goal=plan.get("goal", ""),
        tone=plan.get("tone", "説明調"), visual=plan.get("visual_direction", "ビジネス調"),
        facts=facts,
    )


def _normalize_slides(raw: List[Any], plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """LLMの出力ゆれ（型違い・キー欠け）を吸収して後続が安心して使える形にする。"""
    slides = []
    for i, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            continue
        bullets = item.get("bullets") or []
        if isinstance(bullets, str):
            bullets = [b.strip() for b in bullets.splitlines() if b.strip()]
        slides.append({
            "no": i,
            "title": str(item.get("title") or "スライド%d" % i)[:40],
            "bullets": [str(b)[:60] for b in bullets][:6],
            "narration": str(item.get("narration") or item.get("title") or ""),
            "image_prompt": str(item.get("image_prompt")
                                or plan.get("visual_direction", "clean business background")),
        })
    return slides


def _fallback_deck(plan: Dict[str, Any], count: int) -> Dict[str, Any]:
    titles = ["はじめに", "現状の課題", "市場の状況", "提案の全体像",
              "具体的な進め方", "期待できる効果", "リスクと対策", "まとめ"]
    slides = []
    for i in range(count):
        title = titles[i] if i < len(titles) else "補足%d" % (i - len(titles) + 1)
        slides.append({
            "no": i + 1,
            "title": title,
            "bullets": ["（内容未生成）", "APIキー設定後に再実行してください"],
            "narration": "%sについて説明します。" % title,
            "image_prompt": "clean abstract business background, blue tones, no text",
        })
    return {"title": plan.get("title", "無題"), "subtitle": plan.get("subtitle", ""),
            "slides": slides}


def _to_script(deck: Dict[str, Any]) -> str:
    lines = ["# ナレーション原稿 — %s" % deck["title"], ""]
    for s in deck["slides"]:
        lines += ["## %d. %s" % (s["no"], s["title"]), ""]
        lines += ["- %s" % b for b in s["bullets"]]
        lines += ["", "> %s" % s["narration"], ""]
    return "\n".join(lines)
