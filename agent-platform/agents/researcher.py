"""02 リサーチャー

役割: 市場調査・ファクトチェック。アップロードされた資料（長文）も読む。
使用: Google Gemini API（長文コンテキスト）／未設定時は他のLLMへ自動フォールバック

注意: 現状はWeb検索を繋いでいないため、出典は「要確認」として扱う。
      数字を人に見せる前に必ず裏取りすること。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

from core.base_agent import BaseAgent, register
from core.config import get_settings
from core.context import JobContext
from core.io_utils import write_json, write_text
from core.llm import complete, complete_json

SYSTEM = """あなたは事業企画のリサーチャーです。
分かっていることと分かっていないことを厳密に区別し、
推測を事実として書かないでください。数値には必ず「要確認」の可否を添えます。"""

TOOL_SYSTEM = """あなたは事業企画のリサーチャーです。手元の道具を使って裏を取ります。
- 依頼文にURLがあれば WebFetch で必ず実際に開いて読むこと
- 一般的な相場・市場の数字は WebSearch で調べ、出典URLを控えること
- 渡された資料フォルダがあれば Read/Glob/Grep で中身を読むこと
自分で読んだ・検索した内容だけを verified=true にし、それ以外は false にしてください。
読めなかったURLは、その旨を正直に書いてください。推測で埋めないこと。"""

MAX_DOC_CHARS = 120_000  # 長文コンテキストに載せる上限（Geminiを想定）


@register
class ResearcherAgent(BaseAgent):
    key = "researcher"
    name_ja = "リサーチャー"
    role_ja = "市場調査・ファクトチェック・資料の読み込み"
    icon = "🔍"
    uses = "claude CLI（Web取得・検索・資料読み）／Gemini（長文）"
    llm_role = "longcontext"
    wants_tools = True   # 実際にページを開き検索する。ここが道具の主戦場
    needs_web = True
    needs_files = True
    # ブラウザ（MCP）は**既定オフ**。実測では HOME'S の物件ページは WebFetch だけで
    # 読めた（160秒）。ブラウザは npx 起動＋操作のぶん重いので、
    # 「JSで描画されて WebFetch では読めない」と司令塔が判断したときだけ
    # agent_tools で browser を足す。
    needs_mcp = False
    depends_on = ("orchestrator",)
    deliverable = "research"

    def _run(self, ctx: JobContext) -> Dict[str, Any]:
        plan = ctx.state.get("plan", {})
        questions = plan.get("key_questions") or ["市場の状況", "競合", "ターゲット", "リスク"]

        depth = str(plan.get("research_depth", "")).strip().lower()
        urls_in_brief = _find_urls(ctx.brief)
        if depth == "none" and not urls_in_brief:
            self.log(ctx, "司令塔の判断により、調査は行いません（依頼文だけで作れます）")
            data = {"summary": "調査は不要と判断しました", "findings": [],
                    "opportunities": [], "threats": [], "sources": []}
            ctx.state["research"] = data
            return {"summary": "調査は不要と判断したため行っていません", "data": data}

        docs = self._read_uploaded_documents(ctx)
        if docs:
            self.log(ctx, "アップロードされた資料 %d件 を読み込みました" % len(docs))

        data, result, used_tools = self._investigate(ctx, plan, questions, docs)

        degraded = False
        if not isinstance(data, dict):
            degraded = True
            self.note_degraded(ctx, result.error or "調査結果のJSONを解釈できませんでした")
            data = _fallback_research(questions)
        else:
            self.log_llm(ctx, result)

        findings: List[Dict[str, Any]] = data.get("findings") or []
        markdown = _to_markdown(ctx.brief, data)
        md_path = write_text(ctx.dir("research") / "research.md", markdown)
        write_json(ctx.dir("research") / "research.json", data)
        ctx.add_artifact("markdown", md_path, label="調査レポート", agent=self.key)

        data["markdown"] = markdown
        ctx.state["research"] = data

        unverified = sum(1 for f in findings if not f.get("verified"))
        sources = data.get("sources") or []
        if used_tools:
            summary = ("Webで裏取りしながら %d 項目調べました（出典 %d件・未確認 %d件）"
                       % (len(findings), len(sources), unverified))
        else:
            summary = ("知識だけで %d 項目まとめました（Web未使用のため全%d件が要確認）"
                       % (len(findings), unverified))
        return {
            "summary": summary,
            "detail": "資料 %d件 を参照" % len(docs) if docs else "",
            "data": data,
            "degraded": degraded or not used_tools,
        }

    def _read_pages(self, ctx: JobContext, urls) -> str:
        """依頼のURLを自分で読む。掲載写真もここで回収する。

        写真をここで取るのは、**同じページを2度読まないため**。
        以前はビジュアル制作が別に読み直していて、その1回に5〜8分かかっていた。
        """
        import tools as toolbox

        self.log(ctx, "依頼のURLを読みます（%d件）" % len(urls))
        text = toolbox.webread.read_many(urls)
        if not text or "取得できませんでした" in text and len(text) < 300:
            return ""
        self.log(ctx, "ページを読み込みました（%d文字）" % len(text))
        # **読んだ本文を残す。** 後の工程が「ページに書いてあったか」を
        # 突き合わせるのに使う（書いていない設備を紙面に書かせないため）
        ctx.state["page_text"] = text[:40000]

        # 掲載写真の回収。取れた写真は input/ に置き、実写真として扱う
        saved = []
        for url in urls[:3]:
            html = toolbox.webread.fetch(url)
            if not html:
                continue
            image_urls = toolbox.photos.extract_from_html(html, limit=12)
            if image_urls:
                saved += toolbox.photos.download(image_urls, ctx.dir("input"),
                                                 prefix="web")
        if saved:
            ctx.state["harvested_photos"] = [ctx.rel(x["path"]) for x in saved]
            self.log(ctx, "掲載写真を %d枚 取り込みました（後の工程で使います）"
                     % len(saved))
        else:
            self.log(ctx, "掲載写真は取り込めませんでした", level="warn")
        return text

    def _investigate(self, ctx: JobContext, plan, questions, docs):
        """道具が使えるなら実際に読みに行く。駄目なら知識だけの調査に落ちる。

        戻り値: (データ, LLMResult, 道具を使えたか)
        """
        st = get_settings()
        urls = _find_urls(ctx.brief)
        input_dir = ctx.dir("input")
        has_files = any(input_dir.iterdir())

        # **URLがあるなら、まず自分でページを読む。**
        # AI（claude CLI の WebFetch）に読ませると1回5〜8分かかり、空で返ることもある。
        # 取得そのものは1秒の仕事なので、本文を取ってプロンプトに載せ、
        # AIには「読む」のではなく「拾う」だけをさせる。
        # ついでに掲載写真も同じページから回収して、後続の部隊へ渡す。
        if urls:
            page_text = self._read_pages(ctx, urls)
            if page_text:
                data, result = complete_json(
                    _build_text_prompt(ctx.brief, plan, questions, page_text),
                    system=SYSTEM, role="longcontext", max_tokens=5000,
                    temperature=0.2)
                if isinstance(data, dict) and (data.get("findings")
                                               or data.get("facts")):
                    self.log_llm(ctx, result)
                    return data, result, True
                self.log(ctx, "ページは読めましたが、事実を取り出せませんでした",
                         level="warn")

        if st.allow_web and st.provider_available("claude_cli"):
            tools = self.toolset(ctx)
            depth = str(plan.get("research_depth", "")).strip().lower()
            if urls and depth == "urls":
                # URLを読むだけでよい。周辺調査を足すと倍の時間がかかる
                self.log(ctx, "依頼のURLを読みます（周辺調査はしません・URL %d件）" % len(urls))
                data, result = complete_json(
                    _build_url_prompt(ctx.brief, plan, urls,
                                      str(input_dir) if has_files else ""),
                    system=TOOL_SYSTEM, role="tools", max_tokens=5000,
                    temperature=0.2, tools=tools)
            elif urls:
                # URLの精読と、周辺・相場の調査は互いに独立している。
                # 直列だと合計3分かかるので同時に走らせる（実測でここが最大の待ち時間）。
                self.log(ctx, "URLの精読と周辺調査を同時に進めます（URL %d件）" % len(urls))
                data, result = self._parallel_research(ctx, plan, questions, docs,
                                                       urls, input_dir, has_files, tools)
            else:
                self.log(ctx, "Webで検索しながら調べます（%d項目）" % len(questions))
                prompt = _build_prompt(ctx.brief, plan, questions, docs,
                                       input_dir=str(input_dir) if has_files else "")
                data, result = complete_json(prompt, system=TOOL_SYSTEM, role="tools",
                                             max_tokens=6000, temperature=0.2, tools=tools)
            if isinstance(data, dict):
                self.log_llm(ctx, result)
                return data, result, True
            self.log(ctx, "Web調査が失敗したため、知識だけの調査に切り替えます", level="warn")

        self.log(ctx, "市場・競合・トレンドを調べています（%d項目）" % len(questions))
        prompt = _build_prompt(ctx.brief, plan, questions, docs)
        data, result = complete_json(prompt, system=SYSTEM, role=self.llm_role,
                                     max_tokens=4000, temperature=0.3)
        return data, result, False

    def _read_uploaded_documents(self, ctx: JobContext) -> List[Dict[str, str]]:
        """入力フォルダのテキスト系ファイルを読む（画像は画像部隊が扱う）。"""
        docs: List[Dict[str, str]] = []
        budget = MAX_DOC_CHARS
        for path in sorted(Path(ctx.dir("input")).glob("*")):
            if path.suffix.lower() not in (".txt", ".md", ".csv", ".json"):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            text = text[:budget]
            budget -= len(text)
            docs.append({"name": path.name, "text": text})
            if budget <= 0:
                break
        return docs


    def _parallel_research(self, ctx, plan, questions, docs, urls, input_dir,
                           has_files, tools):
        """URL精読と周辺調査を同時に投げ、結果を1つにまとめる。"""
        from concurrent.futures import ThreadPoolExecutor

        read_prompt = _build_url_prompt(ctx.brief, plan, urls,
                                        str(input_dir) if has_files else "")
        around_prompt = _build_prompt(ctx.brief, plan, questions, docs,
                                      input_dir="", around_only=True)

        def call(args):
            prompt, use_files = args
            return complete_json(
                prompt, system=TOOL_SYSTEM, role="tools", max_tokens=6000,
                temperature=0.2,
                tools=dict(tools, dirs=tools.get("dirs") if use_files else []))

        with ThreadPoolExecutor(max_workers=2) as pool:
            (read_data, read_res), (around_data, around_res) = list(
                pool.map(call, [(read_prompt, True), (around_prompt, False)]))

        merged = {"summary": "", "findings": [], "opportunities": [], "threats": [],
                  "sources": []}
        best = read_res if read_res.ok else around_res
        for part in (read_data, around_data):
            if not isinstance(part, dict):
                continue
            merged["summary"] = (merged["summary"] + " " + part.get("summary", "")).strip()
            for key in ("findings", "opportunities", "threats", "sources"):
                values = part.get(key) or []
                if isinstance(values, list):
                    merged[key].extend(values)
        # 出典の重複を落とす
        merged["sources"] = list(dict.fromkeys(str(s) for s in merged["sources"]))
        if not merged["findings"]:
            return None, best
        return merged, best


URL_RE = re.compile(r"https?://[^\s、。））\"']+")


def _find_urls(text: str) -> List[str]:
    return list(dict.fromkeys(URL_RE.findall(text or "")))


def _build_url_prompt(brief, plan, urls, input_dir="") -> str:
    """渡されたURLを実際に開いて、事実だけを写し取らせる。"""
    parts = ["次のURLを WebFetch で実際に開き、書いてある事実だけを写し取ってください。",
             "", "【依頼】\n%s" % brief, "", "【開くURL】"]
    parts += ["- %s" % u for u in urls]
    if input_dir:
        parts += ["", "【資料フォルダ（Read/Globで読めます）】", input_dir]
    parts += ["", """次のJSON形式で出力してください。
{
  "summary": "そのページに書いてあることの要約（3行程度）",
  "findings": [
    {"question": "項目名（例: 賃料、間取り、所在地）", "answer": "ページに書いてある値",
     "evidence": "そのURL", "verified": true, "note": ""}
  ],
  "sources": ["実際に開いたURL"]
}""",
              "",
              "findings は**最大8件**。細かく分けすぎず、成果物に使う事実に絞ってください。",
              "",
              "重要: ページに書いていないことは書かないでください。",
              "読めなかったURLは findings に verified=false で「読めなかった」と記録してください。"]
    return "\n".join(parts)


def _build_prompt(brief, plan, questions, docs, urls=None, input_dir="",
                  around_only=False) -> str:
    parts = [
        ("URLに書いてあることは別の担当が調べています。あなたは**周辺情報と相場**を"
         "WebSearchで調べてください。" if around_only else "次の企画のために調査してください。"),
        "",
        "【依頼】\n%s" % brief,
        "【タイトル】%s" % plan.get("title", ""),
        "【対象読者】%s" % plan.get("audience", ""),
        "",
        "【調べること】",
    ]
    parts += ["- %s" % q for q in questions]
    if urls:
        parts += ["", "【必ず開いて読むURL】"] + ["- %s" % u for u in urls]
    if input_dir:
        parts += ["", "【資料フォルダ（Read/Globで中身を読めます）】", input_dir]
    if docs:
        parts += ["", "【参考資料（アップロードされたもの）】"]
        for d in docs:
            parts.append("--- %s ---\n%s" % (d["name"], d["text"]))
    parts += [
        "",
        "次のJSON形式で出力してください。",
        """{
  "summary": "調査結果の要約（3行程度）",
  "findings": [
    {"question": "問い", "answer": "分かったこと",
     "evidence": "根拠（資料名・一般的な知見など）",
     "verified": true/false,
     "note": "verifiedがfalseなら、何を裏取りすべきか"}
  ],
  "opportunities": ["機会・追い風"],
  "threats": ["リスク・逆風"],
  "sources": ["参照した資料名や情報源。無ければ空配列"]
}""",
        "",
        "findings は**最大8件**に絞ってください（多いほど時間がかかるだけで、"
        "成果物の質は上がりません）。",
        "重要: 自分で読んだ・検索した内容だけ verified=true にし、"
        "sources には実際に参照したURLを入れてください。"
        "道具が使えない場合は推測を断定形で書かず、verified=false にしてください。",
    ]
    return "\n".join(parts)


def _fallback_research(questions) -> Dict[str, Any]:
    return {
        "summary": "LLM未接続のため、調査は行えていません。項目だけ立てた雛形です。",
        "findings": [
            {"question": q, "answer": "（未調査）", "evidence": "",
             "verified": False, "note": "APIキー設定後に再実行してください"}
            for q in questions
        ],
        "opportunities": [],
        "threats": ["調査未実施のまま資料を配布しないこと"],
        "sources": [],
    }


def _to_markdown(brief: str, data: Dict[str, Any]) -> str:
    lines = ["# 調査レポート", "", "**依頼**: %s" % brief, "",
             "## 要約", "", data.get("summary", ""), "", "## 調査項目", ""]
    for f in data.get("findings", []):
        mark = "✅ 確認済" if f.get("verified") else "⚠️ 要確認"
        lines += ["### %s  %s" % (f.get("question", ""), mark), "",
                  f.get("answer", ""), ""]
        if f.get("evidence"):
            lines += ["- 根拠: %s" % f["evidence"]]
        if f.get("note"):
            lines += ["- メモ: %s" % f["note"]]
        lines.append("")
    for title, key in (("機会", "opportunities"), ("リスク", "threats"), ("情報源", "sources")):
        items = data.get(key) or []
        lines += ["## %s" % title, ""] + (["- %s" % i for i in items] or ["- （なし）"]) + [""]
    return "\n".join(lines)


def _build_text_prompt(brief, plan, questions, page_text) -> str:
    """読み取ったページ本文から事実を拾わせる。

    **ページに書いていないことを書かせない。** 物件広告で数値を創作すると
    不当表示になる。分からない項目は「不明」と書かせて、紙面側で扱いを決める。
    """
    asks = "\n".join("- %s" % q for q in (questions or [])[:8]) or "- 主要な事実"
    return """次のページの中身から、依頼に必要な事実だけを写し取ってください。

【依頼】
{brief}

【知りたいこと】
{asks}

【ページの中身（実際に取得したものです）】
{page}

守ること:
- **ページに書いてあることだけ**を書く。書いていないことは "不明" とする
- 金額・面積・築年・所在地などは、書式を変えずそのまま写す
- 推測・一般論・相場感を混ぜない

次のJSON形式で返してください。
{{"findings": [{{"question": "何を調べたか", "answer": "分かった事実",
                "source": "出典URL"}}],
  "summary": "要点を3行以内で",
  "unknowns": ["ページからは分からなかったこと"]}}""".format(
        brief=brief, asks=asks, page=page_text[:30000])
