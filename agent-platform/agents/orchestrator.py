"""01 司令塔 / オーケストレーター

役割: ユーザーの抽象的な指示（「企画からパワポ、音声、動画、SNS告知まで全部作って」）を
      読み解き、各部隊が使える具体的な作業計画（JSON）に落とす。
使用: Claude（Anthropic API もしくは claude CLI）
"""
from __future__ import annotations

from typing import Any, Dict

from core.base_agent import BaseAgent, register
from core.config import get_settings
from core.context import JobContext
from core.io_utils import write_json
from core.llm import complete_json

CLARIFY_SYSTEM = """あなたは制作プロジェクトの司令塔です。
依頼を受けた最初の打ち合わせで、成果物の方向が大きく変わってしまう点だけを確認します。
細かいことは聞かず、自分で判断してください。聞くのは最大3つまで。
確認しなくても妥当な成果物が作れるなら、質問は0件で構いません。"""

CLARIFY_TEMPLATE = """次の依頼を受けました。制作に入る前に、確認すべきことがあれば挙げてください。

【依頼】
{brief}

【添付資料】
{files}

確認する価値があるのは「答えによって成果物が変わる」ことだけです。
例) 何を作るか（チラシ / スライド / 動画）が読み取れない、誰に見せるかで内容が変わる、
    社外に出すかどうかで表現の慎重さが変わる、など。
聞かなくていい例) 色の好み、フォント、細かい枚数（こちらで決める）。

次のJSON形式で出力してください。質問が不要なら questions は空配列。
{{
  "questions": [
    {{"id": "target", "question": "誰に見せるものですか？",
      "options": ["社内の役員", "既存の顧客", "新規のお客様"],
      "why": "答えによって言葉づかいと構成が変わるため"}}
  ],
  "assumption": "質問しない場合にこちらが置く前提（1行）"
}}

options は選びやすい候補を2〜4個。自由記述で答えたい場合もあるので、候補は目安で構いません。"""

SYSTEM = """あなたは制作プロジェクトの司令塔です。
依頼文から「何を作るのか」を具体化し、後続の制作部隊が迷わない作業指示に変換します。
日本のビジネス文脈に合った、地に足のついた計画を立ててください。"""

TEMPLATE = """次の依頼を、制作チーム向けの作業計画に落としてください。

【依頼】
{brief}

【前提】
- スライド枚数: {slides}
- 作れるもの: pptx(スライド) / images(画像) / mp3(ナレーション音声) / mp4(解説動画) / sns(告知文) / research(調査)

【調査の深さ（research_depth）】
調査は1回あたり2〜4分かかります。要らない調査はしないでください。
  - none … 依頼文だけで作れる（社内の掲示物、決まった様式の書類、既知の内容）
  - urls … 依頼文にURLがある。そのページを読めば足りる
  - full … 相場・競合・市場など、外を調べないと書けないことがある
迷ったら none か urls を選んでください。full は本当に必要なときだけです。

【成果物の型（genre）を必ず決めること】
型が違うと作り方が根本から変わります。後続の部隊はこの型に従って動きます。
  - signage … 掲示物・貼り紙・案内表示（駐輪禁止、ゴミ出しルール、工事のお知らせ等）
      **遠くから一目で分かること**が全て。極太の見出し＋記号＋最小限の文だけ。
      写真も箇条書きの説明文も要らない。調査もほぼ不要
  - promo   … **お客様に訴えるPRチラシ**（入居者募集、商品、イベント）
      写真を大きく、キャッチは暮らしの情景。情報を絞って感情に訴え、問い合わせを取る
  - maisoku … **業者・ポータル向けの物件概要（マイソク）**
      情報の網羅と正確さ。外観＋間取り図を大きく、条件を密に。感情訴求は不要
      ※「チラシ」と言われたら通常は promo。「マイソク」「物件概要」と明示されたときだけ maisoku
  - deck    … 提案・報告のスライド（社内提案、説明資料）
      見出し＋箇条書き＋ナレーション
  - report  … 文章主体の報告書

【いま手元にある素材（assets フォルダ）】
{assets}

【素材が足りないときの調達先（人がダウンロードして assets に置きます）】
{sources}

手元に無いが「これがあると成果物が良くなる」という素材があれば、needed_assets に
「何が欲しいか」と「どのサイトから取れるか」を書いてください。人が用意します。
無ければ空配列で構いません。手元にある素材だけで作れるなら、それが一番早いです。

【使える道具（アイテム）】
{items}

道具は「成果物に効くもの」だけ選んでください。使えば使うほど良いわけではなく、
1つ使うごとに時間がかかります。選んだ道具は担当部隊に申し送りされます。

【部隊ごとの道具のオン・オフ（agent_tools）】
道具を持たせた部隊は「調べながら考える」ので質は上がりますが、**1回あたり数十秒**遅くなります。
持たせない部隊は速いモデルで数秒で返します。依頼に応じて必要な部隊にだけ持たせてください。
  - 指定できる部隊: researcher（調査）/ legal（法務）/ planner（構成）/ reviewer（チェック）/
                    supervisor（中間調整）/ flyer（チラシ）/ publisher（SNS）
  - 指定できる道具: web（ページ取得・検索）/ files（添付資料を読む）/
                    browser（実ブラウザ操作。JSで描画されるページ用。一番重い）/ none（道具なし）
  判断の目安:
   - browser は最後の手段。通常のページは web（取得）だけで読める。
     ログインが要る・スクロールしないと出ない等、明確に必要なときだけ足す
   - 依頼にURLが無く、添付資料も無いなら researcher は none でよい
   - 社内限りの資料なら legal は none でよい（社外広告なら web を持たせる）
   - 事実確認が要らない部隊（reviewer / supervisor / flyer / publisher）は原則 none

【重要】deliverables には「この依頼に本当に必要なものだけ」を入れてください。
例) チラシ1枚が目的なら pptx と images だけでよく、音声・動画・SNSは不要。
    社内提案で口頭説明するだけなら pptx のみ。動画配信が目的なら mp4 まで。
不要なものを入れると、その分だけ時間と費用が無駄になります。

{answers}

次のJSON形式で出力してください。
{{
  "title": "成果物の正式タイトル",
  "subtitle": "サブタイトル（無ければ空文字）",
  "audience": "誰に向けたものか",
  "goal": "この成果物で達成したいこと",
  "tone": "文体・トーン（例: 落ち着いた説明調）",
  "key_questions": ["リサーチで明らかにすべき問い", "..."],
  "slide_count": 実際に作るスライド枚数(整数。上の指示が「おまかせ」なら内容に合う枚数を自分で決める),
  "video_seconds": 想定動画尺の秒数(整数),
  "visual_direction": "画像・スライドのビジュアル方針",
  "deliverables": ["この依頼に本当に必要なものだけを次から選ぶ: flyer(チラシ・紙面) / pptx(スライド) / images(画像のみ) / mp3(音声) / mp4(解説動画) / sns(告知文) / research(調査)"],
  "research_depth": "調査の深さを1つ: none(調査不要) / urls(依頼文のURLを読むだけ) / full(周辺も検索)",
  "genre": "成果物の型を1つ選ぶ: signage(掲示物・貼り紙) / promo(お客様向けPRチラシ) / maisoku(業者向け物件概要) / deck(提案スライド) / report(報告書)",
  "tools": [{{"name": "上の道具一覧のカッコ内の名前", "why": "この成果物にどう効くか"}}],
  "needed_assets": [{{"what": "欲しい素材（例: 自転車のイラスト）", "where": "調達先サイト名",
                      "why": "何に使うか"}}],
  "agent_tools": {{
    "researcher": ["web", "files"],
    "legal": ["web"],
    "planner": ["none"]
  }},
  "risks": ["この企画で注意すべき点"]
}}"""


@register
class OrchestratorAgent(BaseAgent):
    key = "orchestrator"
    name_ja = "司令塔"
    role_ja = "指示を読み解き、全部隊への作業計画に分解する"
    icon = "🧭"
    uses = "Claude (Anthropic API / claude CLI)"
    llm_role = "reasoning"
    # 依頼文にURLがある／資料が添付されている場合だけ道具を持つ。
    # 道具を持つと claude CLI 固定になり、実測で40〜70秒かかる。
    # URLも資料も無い依頼（社内掲示など）では読むものが無いので、
    # 速いモデルで数秒に済ませる。
    wants_tools = True
    needs_web = True
    needs_files = True
    needs_mcp = False

    def tool_policy(self, ctx):
        policy = super().tool_policy(ctx)
        if policy is not None:
            return policy
        import re

        has_url = bool(re.search(r"https?://", ctx.brief or ""))
        has_files = False
        try:
            has_files = any(ctx.dir("input").iterdir())
        except OSError:
            pass
        if has_url or has_files:
            return None      # クラス既定（道具あり）
        return {"web": False, "files": False, "mcp": False, "any": False}

    def _run(self, ctx: JobContext) -> Dict[str, Any]:
        st = get_settings()
        requested = ctx.options.get("slide_count")
        slides_text = ("%d枚（指定あり・これに従う）" % int(requested)) if requested \
            else "おまかせ（内容に合う枚数を決める。3〜12枚が目安）"
        self.log(ctx, "依頼内容を読み解いて、作業計画を組み立てています")

        answers = _format_answers(ctx.options.get("answers"))
        if answers:
            self.log(ctx, "確認への回答を計画に反映します")
        assets_text, sources_text = _assets_text()
        prompt = TEMPLATE.format(brief=ctx.brief, slides=slides_text, answers=answers,
                                 items=_item_catalog_text(), assets=assets_text,
                                 sources=sources_text)
        data, result, used_tools = self.ask_json(
            ctx, prompt, system=SYSTEM, max_tokens=2500, temperature=0.4,
            tool_system=SYSTEM + "\n依頼文にURLがあれば WebFetch で開いて中身を確認し、"
                                 "資料フォルダがあれば読んでから計画を立ててください。")
        degraded = False
        if not isinstance(data, dict):
            degraded = True
            self.note_degraded(ctx, result.error or "計画のJSONを解釈できませんでした")
            data = _fallback_plan(ctx.brief, int(requested or st.default_slides))
        else:
            self.log_llm(ctx, result)

        data.setdefault("title", ctx.brief[:30])
        data["slide_count"] = int(requested or data.get("slide_count")
                                  or st.default_slides)
        data["video_seconds"] = int(data.get("video_seconds") or data["slide_count"] * 12)

        data["genre"] = str(data.get("genre") or "").strip().lower() or _guess_genre(ctx.brief)
        if data["genre"] not in ("signage", "promo", "maisoku", "deck", "report"):
            data["genre"] = _guess_genre(ctx.brief)
        data["layout_template"] = _layout_from_answers(ctx, data["genre"])
        if data["layout_template"]:
            self.log(ctx, "紙面の型は「%s」で進めます" % data["layout_template"])
        self.log(ctx, "成果物の型は「%s」と判断しました（%s）"
                 % (data["genre"], GENRE_LABELS.get(data["genre"], "")))
        wanted = [x for x in (data.get("needed_assets") or []) if isinstance(x, dict)]
        if wanted:
            self.log(ctx, "あると良い素材: %s"
                     % "・".join(str(x.get("what", "")) for x in wanted[:3]), level="warn")
        chosen = [x for x in (data.get("tools") or []) if isinstance(x, dict)]
        if chosen:
            self.log(ctx, "使う道具を決めました: %s"
                     % "・".join(str(x.get("name", "")) for x in chosen))
        ctx.state["plan"] = data
        path = write_json(ctx.dir("plan") / "job_plan.json", data)
        ctx.add_artifact("json", path, label="作業計画", agent=self.key)

        return {
            "summary": "「%s」を、%s として作ります（%d枚構成）"
                       % (data["title"], _deliverable_text(data.get("deliverables")),
                          data["slide_count"]),
            "detail": "対象: %s ／ 目的: %s" % (data.get("audience", "-"), data.get("goal", "-")),
            "data": data,
            "degraded": degraded,
        }


GENRE_LABELS = {"signage": "掲示物・貼り紙", "promo": "PR・募集チラシ",
                "maisoku": "業者向け物件概要（マイソク）",
                "deck": "提案スライド", "report": "報告書"}

# 依頼文から型を当てる保険。LLMが答えを外しても、明らかな語があれば拾う
GENRE_KEYWORDS = [
    (("貼り紙", "張り紙", "掲示", "禁止", "お願い", "注意喚起", "案内表示", "ポスター"),
     "signage"),
    (("マイソク", "物件概要", "業者向け"), "maisoku"),
    (("チラシ", "募集", "PR", "宣伝", "広告"), "promo"),
    (("提案", "稟議", "説明資料", "スライド", "プレゼン"), "deck"),
]


def _guess_genre(brief: str) -> str:
    for words, genre in GENRE_KEYWORDS:
        if any(w in (brief or "") for w in words):
            return genre
    return "deck"


def _assets_text():
    """手元の素材と、足りないときの調達先を文章にする。"""
    try:
        import tools

        return (tools.assets_lib.describe_for_prompt(),
                tools.assets_lib.sources_for_prompt())
    except Exception:
        return "（素材の一覧を取得できませんでした）", ""


def _item_catalog_text() -> str:
    """いま実際に使えるアイテムだけを司令塔に見せる。

    使えない道具を前提にした計画を立てさせないため、availableなものに限る。
    """
    try:
        import tools as tool_pack

        lines = []
        for item in tool_pack.catalog():
            if item["available"]:
                lines.append("- %s（%s）: %s"
                             % (item["label"], item["name"], item["description"]))
        return "\n".join(lines) or "（使える道具はありません）"
    except Exception:
        return "（道具の一覧を取得できませんでした）"


DELIVERABLE_LABELS = {"flyer": "チラシ", "pptx": "スライド", "images": "画像", "mp3": "ナレーション音声",
                      "audio": "ナレーション音声", "mp4": "解説動画", "video": "解説動画",
                      "sns": "SNS告知文", "research": "調査レポート"}


def _deliverable_text(deliverables) -> str:
    labels = [DELIVERABLE_LABELS.get(str(d).lower(), str(d)) for d in (deliverables or [])]
    return "・".join(dict.fromkeys(labels)) or "資料一式"


def _format_answers(answers) -> str:
    """画面や端末で受け取った確認の回答を、プロンプトに差し込める形にする。"""
    if not answers:
        return ""
    lines = ["【依頼者への確認と回答】"]
    for item in answers:
        if isinstance(item, dict) and item.get("answer"):
            lines.append("- %s → %s" % (item.get("question", ""), item["answer"]))
    return "\n".join(lines) if len(lines) > 1 else ""


def clarify(brief: str, file_names=None, timeout_note: str = "") -> Dict[str, Any]:
    """制作前に司令塔が聞くべきことを1回だけ問い合わせる。

    UI・CLIの両方から呼ぶ。LLMが使えなければ質問なしで進む（止めない）。
    戻り値: {"questions": [{"id","question","options","why"}], "assumption": "..."}
    """
    files = "\n".join("- %s" % n for n in (file_names or [])) or "（なし）"
    data, result = complete_json(
        CLARIFY_TEMPLATE.format(brief=brief, files=files),
        system=CLARIFY_SYSTEM, role="fast", max_tokens=1500, temperature=0.3)
    if not isinstance(data, dict):
        return {"questions": [], "assumption": "", "error": result.error}
    questions = [q for q in (data.get("questions") or []) if isinstance(q, dict)][:3]
    for i, q in enumerate(questions):
        q.setdefault("id", "q%d" % (i + 1))
        q["options"] = [str(o) for o in (q.get("options") or [])][:4]
    questions = _add_layout_question(brief, questions)
    return {"questions": questions, "assumption": data.get("assumption", "")}


def _add_layout_question(brief: str, questions):
    """チラシなら「紙面の型」を必ず聞く。

    LLMの判断に任せると聞いたり聞かなかったりする。型は出来上がりが根本から
    変わるところなので、**依頼者に選んでもらう**のが確実で、しかも速い。
    先頭に置くのは、これが一番大きい分かれ道だから。
    """
    genre = _guess_genre(brief)
    if genre == "signage":
        # 掲示物も型で出来が決まる。禁止の様式でお願いを書くと威圧的になる
        try:
            from core import signage_templates

            options = signage_templates.options_for_question()
        except Exception:
            return questions
        item = {"id": "layout", "question": "掲示物の型はどれにしますか？",
                "options": options,
                "why": "型によって強さ・配色・並びが変わるため"}
        return ([item] + questions)[:4]
    if genre not in ("promo", "maisoku"):
        return questions
    if any(str(q.get("id")) == "layout" for q in questions):
        return questions
    try:
        from core import layouts

        options = layouts.options_for_question(genre)
    except Exception:
        return questions
    if len(options) < 2:
        return questions
    item = {"id": "layout", "question": "紙面の型（レイアウト）はどれにしますか？",
            "options": options,
            "why": "型によって写真の大きさ・枚数・情報量が変わるため"}
    return ([item] + questions)[:4]


def _layout_from_answers(ctx, genre: str) -> str:
    """ヒアリングの回答から紙面の型を決める。無回答なら空（後で自動で決める）。"""
    answer = ""
    for item in (ctx.options.get("answers") or []):
        if isinstance(item, dict) and str(item.get("id")) == "layout":
            answer = str(item.get("answer", ""))
    if not answer:
        return ""
    try:
        if genre == "signage":
            from core import signage_templates

            return signage_templates.id_from_answer(answer)
        if genre in ("promo", "maisoku"):
            from core import layouts

            return layouts.id_from_answer(answer, genre)
    except Exception:
        return ""
    return ""


def _fallback_plan(brief: str, slides: int) -> Dict[str, Any]:
    """LLMが使えないときの最低限の計画。処理を止めないためのもの。"""
    title = brief.strip().splitlines()[0][:40] or "無題の企画"
    return {
        "title": title,
        "subtitle": "",
        "audience": "社内の意思決定者",
        "goal": "依頼内容の要点を伝える",
        "tone": "落ち着いた説明調",
        "key_questions": ["市場の状況は", "競合は", "収益の見込みは"],
        "slide_count": slides,
        "video_seconds": slides * 12,
        "visual_direction": "清潔感のあるビジネス調（青系）",
        "deliverables": ["pptx", "mp3", "mp4", "sns"],
        "risks": ["LLM未接続のため、内容は雛形です。実データで作り直してください"],
    }
