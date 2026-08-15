"""司令塔（最終確認）— 依頼どおりにできているかを見て判定する

なぜ要るか:
  検品部隊が見ているのは「ファイルが存在するか・空でないか」だけで、
  **中身が依頼を満たしているか**は誰も見ていなかった。
  実際、レイアウト指示がそのまま印刷された紙面が「不足0件」で合格していた。

  指示を出したのは司令塔なので、受け取り検査も司令塔がやる。

やること:
  1. 最初の依頼文と、自分が立てた計画を読み直す
  2. **出来上がった成果物を実際に見る**（claude CLI は画像を読めるので、
     PNGを開いて紙面を目で確認できる）
  3. 依頼を満たしているか判定し、足りない点と直し方を申し送る

ここで不合格になっても処理は止めない。人が判断するための材料を出すのが役目。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from core.base_agent import BaseAgent, register
from core.context import JobContext
from core.io_utils import write_json, write_text

SYSTEM = """あなたは制作の責任者です。出来上がった成果物を受け取り検査します。
身内に甘い判定をしないでください。依頼した人の立場で見て、
「これをそのまま使えるか」だけを基準に判断します。

成果物の画像ファイルが渡されたら、**必ず Read で開いて実際に見てから**判断してください。
ファイルがあるかどうかではなく、中身が依頼を満たしているかを見ます。"""

VERDICTS = {"ok": "✅ 依頼どおり", "needs_fix": "⚠️ 直しが必要", "failed": "❌ 使えない"}


@register
class AcceptanceAgent(BaseAgent):
    key = "acceptance"
    name_ja = "司令塔（最終確認）"
    role_ja = "出来上がった物を見て、依頼どおりか判定する"
    icon = "🧭"
    uses = "Claude（画像を実際に見て確認）"
    llm_role = "reasoning"
    wants_tools = True
    needs_web = False
    needs_files = True
    needs_mcp = False

    def toolset(self, ctx: JobContext) -> Dict[str, Any]:
        # 成果物そのものを読ませる必要があるので、ジョブフォルダ全体を渡す
        return {"web": False, "dirs": [ctx.root], "mcp": False}

    def _repair(self, ctx: JobContext, report) -> bool:
        """指摘を自分で反映して、紙面を組み直す。直せたら True。"""
        from core import flyer_build, layouts

        content = dict(ctx.state.get("flyer_content") or {})
        template_id = str(ctx.state.get("flyer_template") or "")
        photos = [ctx.root / x for x in (ctx.state.get("flyer_photos") or [])]
        photos = [p for p in photos if p.exists()]
        if not content or not photos:
            return False

        genre = plan_genre(ctx)
        templates = layouts.all_templates(genre if genre in ("promo", "maisoku")
                                          else "promo")
        self.log(ctx, "指摘を自分で直します（差し戻さずここで組み直します）")
        # **道具は使わない。** 直しに要るのは指摘の文章と今の中身だけで、
        # ファイルを読み直す必要が無い。道具つきで呼ぶと claude CLI が
        # Read/Glob を回してしまい、数分待たされる（実測3分で止まって見えた）。
        from core.llm import complete_json

        data, result = complete_json(
            _repair_prompt(content, template_id, report, photos,
                           content.get("photo_captions") or {}, templates),
            system=REPAIR_SYSTEM, role="reasoning", max_tokens=3000,
            temperature=0.3)
        if not isinstance(data, dict) or not data.get("title"):
            self.log(ctx, "直しの内容を受け取れませんでした", level="warn")
            return False

        new_id = str(data.pop("template_id", "") or template_id)
        dropped = [x for x in (data.pop("drop_photos", []) or [])
                   if isinstance(x, int)]
        if dropped:
            picked = data.get("photos") or {}
            picked["rooms"] = [x for x in (picked.get("rooms") or [])
                               if x not in dropped]
            for key in ("hero", "floorplan"):
                if picked.get(key) in dropped:
                    picked[key] = None
            data["photos"] = picked
            self.log(ctx, "使えない写真を外しました: %s番"
                     % "・".join(str(x) for x in dropped), level="warn")
        fixed = [str(x) for x in (data.pop("fixed", []) or [])]
        not_fixed = [str(x) for x in (data.pop("not_fixed", []) or [])]
        data["contact"] = content.get("contact") or {}
        for key in ("qr_on", "qr", "qr_label"):
            data.setdefault(key, content.get(key))

        layout = layouts.build(new_id, data)
        if not layout:
            return False
        try:
            from core import palettes

            palette = (palettes.id_from_answer(str(data.get("palette") or ""))
                       or ctx.state.get("flyer_palette") or palettes.DEFAULT)
            flyer_build.write_all(ctx, layout, [str(p) for p in photos],
                                  paper=layouts.paper_of(new_id), palette=palette)
            ctx.state["flyer_palette"] = palette
        except Exception as exc:
            self.log(ctx, "組み直しに失敗しました（%s）" % exc, level="warn")
            return False

        ctx.state["flyer_content"] = data
        ctx.state["flyer_template"] = new_id
        ctx.state["flyer_layout"] = layout
        for line in fixed[:4]:
            self.progress(ctx, "直しました: %s" % line)
        for line in not_fixed[:2]:
            self.log(ctx, "直せなかった点: %s" % line, level="warn")
        report["repaired_notes"] = fixed
        report["not_fixed"] = not_fixed
        self.log(ctx, "紙面を組み直しました（型: %s）"
                 % (layouts.get(new_id) or {}).get("name", new_id))
        return True

    def _run(self, ctx: JobContext) -> Dict[str, Any]:
        artifacts = _reviewable(ctx)
        if not artifacts:
            return {"summary": "確認できる成果物がありません", "degraded": True}

        broken = _broken_files(ctx)
        if broken:
            self.log(ctx, "ファイルに問題があります: %s" % "・".join(broken[:3]), level="warn")
        self.log(ctx, "出来上がった%d点を実際に見て、依頼どおりか確認します" % len(artifacts))
        data, result, used_tools = self.ask_json(
            ctx, _build_prompt(ctx, artifacts), system=SYSTEM,
            max_tokens=3000, temperature=0.1)

        degraded = False
        if not isinstance(data, dict) or not data.get("verdict"):
            degraded = True
            self.note_degraded(ctx, result.error or "判定を解釈できませんでした")
            data = {"verdict": "unknown", "meets": [], "gaps": ["確認できませんでした"],
                    "fix_instructions": ""}
        if not used_tools:
            self.log(ctx, "画像を開けない経路で判定したため、見た目の確認はできていません",
                     level="warn")
            degraded = True

        verdict = str(data.get("verdict", "unknown"))
        if broken:
            data.setdefault("gaps", [])
            data["gaps"] = list(data.get("gaps") or []) + broken
            if verdict == "ok":
                verdict = "needs_fix"
        report = {
            "verdict": verdict,
            "meets": [str(x) for x in (data.get("meets") or [])][:6],
            "gaps": [str(x) for x in (data.get("gaps") or [])][:6],
            "fix_instructions": str(data.get("fix_instructions", "")),
            "checked": [ctx.rel(p) for p in artifacts],
            "saw_images": used_tools,
        }
        # 見つけた不良を覚える。次のジョブから制作部隊がこれを読んで作る
        # （これが無いと、同じ不良を毎回作り直すことになる）
        from core.memory import record, record_success

        genre = plan_genre(ctx)
        learned = record(genre, report["gaps"], report.get("fix_instructions", ""))
        # 効いていた点も残す。失敗だけ溜めると「やってはいけないこと」ばかりになり、
        # 良い作り方が次に伝わらない
        kept = 0
        if verdict in ("ok", "needs_fix"):
            kept = record_success(genre, report["meets"])
        if learned or kept:
            self.log(ctx, "申し送りに追加しました（効いた点 %d件・避ける点 %d件）"
                     % (kept, learned))
        report["learned"] = learned
        report["kept"] = kept
        ctx.state["acceptance"] = report
        write_json(ctx.dir("reports") / "acceptance.json", report)
        path = write_text(ctx.dir("reports") / "acceptance.md", _to_markdown(ctx, report))
        ctx.add_artifact("markdown", path, label="司令塔の最終確認", agent=self.key)

        gaps = report["gaps"]
        # **自分で直す。** 差し戻すと制作部隊が最初から作り直すことになり、
        # 時間がかかるうえ、指摘が反映されないまま同じ紙面が出てきた（実際に2回続いた）。
        # 型で組んでいる紙面なら、文言・写真の割り当て・型そのものを
        # ここで書き換えて組み直せる。直せたら判定を ok に上げる。
        if verdict in ("needs_fix", "failed") and ctx.state.get("flyer_content"):
            if self._repair(ctx, report):
                # **直せなかった重大な指摘が残っているなら「直った」と言わない。**
                # 直した項目と残った指摘を混ぜて「✅ 依頼どおり：【重大】…配布不可」と
                # 出してしまい、何が正しいのか読めなくなった。
                left = [g for g in (report.get("not_fixed") or [])
                        if any(word in str(g) for word in ("重大", "致命"))]
                report["repaired"] = True
                verdict = report["verdict"] = "needs_fix" if left else "ok"
                report["gaps"] = report.get("not_fixed") or []
                gaps = report["gaps"]
                write_json(ctx.dir("reports") / "acceptance.json", report)

        if verdict == "ok" and not gaps:
            summary = "確認しました。依頼どおりにできています"
        else:
            summary = "%s：%s" % (VERDICTS.get(verdict, "確認"),
                                 gaps[0] if gaps else "要確認")
        for gap in gaps[:3]:
            self.progress(ctx, "不足: %s" % gap)

        return {"summary": summary,
                "detail": report["fix_instructions"][:200],
                "data": report,
                "degraded": degraded or verdict != "ok"}


REPAIR_SYSTEM = """あなたは紙面の最終責任者です。指摘を**自分で直します**。

**あなたにできることは、次の4つだけです。**
  1. 型（レイアウト）を変える
  2. 配色を変える
  3. 文言を書き換える
  4. どの写真をどこに置くかを変える／**使わない写真を外す**（drop_photos）

**できないこと**（やったと書いてはいけません）:
  - 写真そのものの回転・切り抜き・明るさ調整・合成
  - 写真に写っていないものを足す
写真が上下反転している、内容が違う、といった指摘は**その写真を外す**か、
目立たない位置へ回すことで対処します。**直したと嘘を書かないこと。**

守ること:
- 指摘された点を**必ず直す**。直せない指摘は not_fixed に理由を書く
- 事実（賃料・面積・築年など）を作らない。分からない項目は空にする
- 写真は渡された番号の中からだけ選ぶ"""


def _repair_prompt(content, template_id, report, photos, captions, templates) -> str:
    import json as _json

    gaps = "\n".join("- %s" % g for g in (report.get("gaps") or [])[:6])
    photo_lines = "\n".join(
        "  %d: %s" % (i, captions.get(str(i), captions.get(i, "内容不明")))
        for i in range(1, len(photos) + 1)) or "  （写真なし）"
    choices = "\n".join("- %s（%s）… %s" % (t["id"], t["name"], t["summary"])
                         for t in templates)
    return """いま出来ている紙面に、次の指摘が出ました。**あなたが直してください。**

【指摘】
{gaps}
【直し方の方針】
{fix}

【いまの型】{template}
【選べる型】
{choices}

【いまの中身（この形式で返してください）】
{content}

【使える写真（番号：中身）】
{photos}

直したものを、**同じ形式のJSONに template_id を足して**返してください。
{{"template_id": "選んだ型", "palette": "配色（変えないなら今のまま）",
  "kicker": "…", "catch": "…", "title": "…",
  "sub": "…", "price": "…", "unit": "円 / 月", "lead": "…",
  "badges": [...], "icons": [...], "appeals": [{{"title": "…", "text": "…"}}],
  "spec_rows": [["項目", "値"]],
  "photos": {{"hero": 1, "floorplan": 2, "rooms": [3, 4, 5]}},
  "drop_photos": [使わない写真の番号。反転・内容違いなど。無ければ空配列],
  "photo_captions": {{"3": "LDK", "4": "洋室"}},
  "fixed": ["直した点を1行ずつ"], "not_fixed": ["直せなかった点と理由"]}}""".format(
        gaps=gaps or "- （指摘なし）", fix=report.get("fix_instructions", ""),
        template=template_id, choices=choices,
        content=_json.dumps(content, ensure_ascii=False, indent=1)[:4000],
        photos=photo_lines)


def plan_genre(ctx: JobContext) -> str:
    return (ctx.state.get("plan") or {}).get("genre", "") or "共通"


def _broken_files(ctx: JobContext) -> List[str]:
    """機械的に分かる不良（ファイルが無い・中身が空）だけ先に拾う。

    旧「テスト・QA部隊」がやっていたのはこれだけだったので、ここに畳み込んだ。
    """
    problems = []
    for art in ctx.artifacts:
        path = ctx.root / art.path
        if not path.exists():
            problems.append("%s のファイルがありません" % (art.label or art.path))
        elif path.stat().st_size == 0:
            problems.append("%s の中身が空です" % (art.label or art.path))
    return problems


def _reviewable(ctx: JobContext) -> List[Path]:
    """見て確認できる成果物（画像・PDF）を集める。画像を優先。"""
    images, others = [], []
    for art in ctx.artifacts:
        path = ctx.root / art.path
        if not path.exists() or path.stat().st_size == 0:
            continue
        if path.suffix.lower() in (".png", ".jpg", ".jpeg"):
            if path.parent.name in ("slides", "video"):
                images.append(path)
        elif path.suffix.lower() in (".pdf", ".pptx", ".mp4"):
            others.append(path)
    return (images + others)[:6]


def _build_prompt(ctx: JobContext, artifacts: List[Path]) -> str:
    from core.design import review_checklist

    plan = ctx.state.get("plan", {})
    files = "\n".join("- %s" % p for p in artifacts)
    return """出来上がった成果物が、依頼どおりかを確認してください。

【依頼された内容（原文）】
{brief}

【立てた計画】
- 成果物の型: {genre}
- タイトル: {title}
- 対象: {audience}
- 目的: {goal}
- 作ると決めたもの: {deliverables}

【出来上がったファイル（Readで開いて実際に見てください）】
{files}

画像を開いて、次の基準で確認してください。
制作側にも同じ基準を渡してあるので、これを満たしていない成果物は不合格です。

{checklist}

次のJSON形式で出力してください。
{{
  "verdict": "ok / needs_fix / failed のいずれか",
  "meets": ["依頼を満たしている点"],
  "gaps": ["足りない点・おかしい点。無ければ空配列"],
  "fix_instructions": "次に直すなら何をどうするか（1〜3行）"
}}

身内に甘い判定をしないでください。そのまま使えないなら needs_fix か failed です。""".format(
        brief=ctx.brief, genre=plan.get("genre", "-"), title=plan.get("title", "-"),
        audience=plan.get("audience", "-"), goal=plan.get("goal", "-"),
        deliverables="・".join(str(x) for x in (plan.get("deliverables") or [])) or "-",
        files=files, checklist=review_checklist(plan.get("genre", "")))


def _to_markdown(ctx: JobContext, report: Dict[str, Any]) -> str:
    lines = ["# 司令塔の最終確認", "",
             "**判定**: %s" % VERDICTS.get(report["verdict"], report["verdict"]), "",
             "**依頼**: %s" % ctx.brief, ""]
    if not report.get("saw_images"):
        lines += ["> 画像を開けない経路で判定したため、見た目の確認はできていません。", ""]
    lines += ["## 満たしている点", ""]
    lines += ["- %s" % x for x in report["meets"]] or ["- （記載なし）"]
    lines += ["", "## 足りない点・おかしい点", ""]
    lines += ["- %s" % x for x in report["gaps"]] or ["- （なし）"]
    if report.get("fix_instructions"):
        lines += ["", "## 次に直すなら", "", report["fix_instructions"]]
    return "\n".join(lines) + "\n"
