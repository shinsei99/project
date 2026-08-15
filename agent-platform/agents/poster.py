"""掲示物制作（貼り紙・案内表示）— 文言・記号・紙面を1部隊で通す

なぜ1部隊にまとめたか:
  最初は「構成ライター → ビジュアル制作 → チラシビルダー」の3部隊に分けていた。
  その結果、構成ライターが書いた**レイアウト指示**（「上部に極太ゴシックで『駐輪禁止』」）を
  ビジュアル部隊がカード画像にし、チラシ部隊がそれを紙面に貼り付けて、
  **指示書がそのまま印刷された**。受け渡しのたびに意図が失われた典型例。

  1枚ものは、文言・記号・レイアウトが不可分。分業する利益より、
  受け渡しで壊れる損失の方が大きい。だから1部隊が通しで持つ。

作り方:
  文言はLLMに決めさせるが、**紙面は固定テンプレート**で組む。
  掲示物は様式がほぼ決まっており、レイアウトをLLMに任せる利点が無い。
  固定にすることで「毎回同じ品質」「失敗しようがない」を取る。
"""
from __future__ import annotations

from typing import Any, Dict

from core.base_agent import BaseAgent, register
from core.context import JobContext
from core.io_utils import write_json, write_text

# 紙面の型。Claude Code 単体で作ったものと見比べて、良かった方をこちらへ移植した。
# 効いていた要素:
#   ・撤去などの運用を「1→2→3」の段階図で見せる（文章より圧が伝わり、根拠にもなる）
#   ・記入欄に「撤去予定日」まで用意する（掲示した時点で期限が決まる）
#   ・英中韓の併記（マンションでは実際に効く）
TEMPLATE = """<style>
{fontface}
@page{{margin:0}} *{{box-sizing:border-box}}
body{{margin:0;width:210mm;height:297mm;font-family:{fontstack};color:#15181d;background:#fff;
 display:flex;flex-direction:column}}
.band{{background:{accent};color:#fff;padding:11mm 10mm 8mm;text-align:center}}
.band h1{{margin:0;font-size:{h1}pt;font-weight:900;line-height:1;letter-spacing:{ls}em;
 text-indent:{ls}em;word-break:auto-phrase;text-wrap:balance}}
.band .en{{margin-top:5mm;font-size:{sub}pt;letter-spacing:.2em;opacity:.95}}
.main{{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;
 padding:5mm 14mm 2mm}}
.pict{{display:flex;gap:14mm;align-items:center;justify-content:center;margin-bottom:7mm}}
.lead{{font-size:{msg}pt;font-weight:900;color:{accent};text-align:center;line-height:1.4;
 word-break:auto-phrase;text-wrap:balance;line-break:strict;max-width:160mm}}
.reason{{margin-top:5mm;font-size:{note}pt;text-align:center;color:#444b55;line-height:1.85;
 word-break:auto-phrase;line-break:strict}}
.flow{{margin-top:7mm;width:100%;background:#f5f6f8;border-radius:4mm;padding:7mm 6mm 6mm}}
.flow .cap{{text-align:center;font-size:13pt;font-weight:700;color:{accent};
 letter-spacing:.08em;margin-bottom:5mm}}
.steps{{display:flex;align-items:flex-start;justify-content:space-between}}
.step{{flex:1;text-align:center;position:relative;padding:0 3mm}}
.step .n{{display:inline-block;width:12mm;height:12mm;line-height:12mm;border-radius:50%;
 background:{accent};color:#fff;font-size:16pt;font-weight:900}}
.step .t{{margin-top:3mm;font-size:14pt;font-weight:700;line-height:1.5;
 word-break:auto-phrase}}
.step:not(:last-child):after{{content:"";position:absolute;right:-2mm;top:5mm;
 width:0;height:0;border-left:3.5mm solid #b9bec6;
 border-top:2.4mm solid transparent;border-bottom:2.4mm solid transparent}}
.foot{{border-top:4px solid {accent};padding:5mm 14mm 6mm}}
.owner{{font-size:13pt;color:#3d434c;line-height:2.3}}
.blank{{display:inline-block;border-bottom:1px solid #98a0aa;min-width:44mm}}
.multi{{margin-top:4mm;font-size:11pt;color:#79808a;text-align:center;letter-spacing:.03em}}
</style>
<div class="band">
  <h1>{headline}</h1>
  {en_html}
</div>
<div class="main">
  <div class="pict">{picto}</div>
  <div class="lead">{message}</div>
  {reason_html}
  {flow_html}
</div>
<div class="foot">
  <div class="owner">{foot}</div>
  {multi_html}
</div>"""


@register
class PosterAgent(BaseAgent):
    key = "poster"
    name_ja = "掲示物制作"
    role_ja = "貼り紙・案内表示を、文言から紙面まで通しで作る"
    icon = "🚫"
    uses = "固定テンプレート ＋ SVGピクトグラム（無料）"
    # 紙に印刷される文字を決める＝成果物の質そのもの。速さより質を取る。
    # （速いモデルに回していたとき、誘導文も理由も無い威圧的な貼り紙になった）
    llm_role = "reasoning"
    deliverable = "signage"
    produces_deliverable = True
    depends_on = ("orchestrator",)
    wants_tools = False

    def _run(self, ctx: JobContext) -> Dict[str, Any]:
        import tools
        from agents.planner import (SIGNAGE_SYSTEM, _build_signage_prompt,
                                    _fallback_signage)

        ok, note = tools.flyer.available()
        if not ok:
            return {"summary": "紙面を出力する道具が使えません（%s）" % note, "degraded": True}

        plan = ctx.state.get("plan", {})
        self.log(ctx, "掲示物に印刷する文言を決めます")

        data, result, _ = self.ask_json(
            ctx, _build_signage_prompt(ctx.brief, plan), system=SIGNAGE_SYSTEM,
            max_tokens=1500, temperature=0.3)
        degraded = False
        if not isinstance(data, dict) or not str(data.get("headline", "")).strip():
            degraded = True
            self.note_degraded(ctx, result.error or "文言のJSONを解釈できませんでした")
            data = _fallback_signage(ctx.brief, plan)

        signage = _normalize(data, ctx.brief)
        ctx.state["signage"] = signage
        # 法務・検品が読めるよう最小限の deck も置く
        ctx.state["deck"] = {
            "title": signage["headline"], "subtitle": signage["sub"],
            "slides": [{"no": 1, "title": signage["headline"],
                        "bullets": [signage["message"]] + signage["notes"],
                        "narration": "", "image_prompt": ""}]}

        illustration = _find_illustration(ctx, signage)
        if illustration:
            self.log(ctx, "素材フォルダのイラストを使います: %s" % illustration.name)
        self.progress(ctx, "「%s」の紙面を組んでいます（記号: %s）"
                      % (signage["headline"], "・".join(signage["pictograms"])))
        from core import signage_templates

        template_id = (str(plan.get("layout_template") or "").strip()
                       or signage_templates.choose(ctx.brief, signage))
        if not signage_templates.get(template_id):
            template_id = signage_templates.choose(ctx.brief, signage)
        self.log(ctx, "掲示物の型は「%s」で組みます"
                 % signage_templates.get(template_id)["name"])
        ctx.state["signage_template"] = template_id
        paper = _paper_for(ctx, plan)
        if paper != "A4":
            self.log(ctx, "用紙は %s で作ります"
                     % signage_templates.PAPERS[paper]["label"])
        html = _build_html(signage, illustration, template_id, paper)

        name = "signage"
        html_path = write_text(ctx.dir("slides") / ("%s.html" % name), html)
        pdf_path = ctx.dir("slides") / ("%s.pdf" % name)
        png_path = ctx.dir("slides") / ("%s.png" % name)
        tools.flyer.render(html, pdf_path, fmt="pdf", paper=paper)
        tools.flyer.render(html, png_path, fmt="png", paper=paper)

        ctx.state["flyer"] = ctx.rel(pdf_path)
        ctx.state["signage_paper"] = paper
        ctx.add_artifact("pdf", pdf_path, agent=self.key,
                         label="掲示物（%s・PDF）"
                               % signage_templates.PAPERS[paper]["label"])
        ctx.add_artifact("image", png_path, label="掲示物（画像）", agent=self.key)
        ctx.add_artifact("markdown", html_path, label="掲示物のHTML", agent=self.key)
        write_json(ctx.dir("plan") / "signage.json", signage)

        return {
            "summary": "A4の掲示物を作りました（見出し「%s」）" % signage["headline"],
            "detail": ctx.rel(pdf_path),
            "data": signage,
            "degraded": degraded,
        }


def _normalize(data: Dict[str, Any], brief: str) -> Dict[str, Any]:
    """LLMの出力を紙面に載る形に整える。長すぎる文字は紙面が壊れるので切る。"""
    import tools

    raw = data.get("pictograms") or data.get("pictogram") or []
    if isinstance(raw, str):
        raw = [raw]
    pictos = [str(x).strip() for x in raw if str(x).strip() in tools.pictograms.PICTOGRAMS]
    if not pictos:
        pictos = tools.pictograms.guess_all(brief)
    notes = [str(x).strip() for x in (data.get("notes") or []) if str(x).strip()][:3]
    # **文字を途中で切らないこと。** 以前 36文字で機械的に切った結果、
    # 「NO BICYCLE / MOPED / MOTORCYCLE PARKING」が「…PARK」になり、
    # 掲示物に不完全な英単語が大書きされた。長い場合は切らずに級数を落とす。
    steps = [str(x).strip() for x in (data.get("steps") or []) if str(x).strip()][:4]
    reason = str(data.get("reason", "")).strip() or (notes[1] if len(notes) > 1 else "")
    return {
        "headline": str(data.get("headline", "")).strip()[:14] or "お知らせ",
        "sub": str(data.get("sub", "")).strip(),
        "message": str(data.get("message", "")).strip(),
        "reason": reason,
        "notes": notes,
        "steps": steps,
        "steps_caption": str(data.get("steps_caption", "")).strip(),
        "deadline_label": str(data.get("deadline_label", "")).strip(),
        "contact": str(data.get("contact", "")).strip()[:60],
        "pictograms": pictos[:2],
    }


def _find_illustration(ctx: JobContext, signage: Dict[str, Any]):
    """assets/ に合う素材があれば使う。

    人が いらすとや や ソコスト から落として置いた素材を、部隊が自分で見つけて使う。
    無ければ記号（ピクトグラム）だけで組む。
    """
    try:
        import tools

        words = [signage["headline"], signage["message"]] + signage["notes"]
        words += [w for w in ("自転車", "バイク", "駐輪", "ゴミ", "たばこ", "騒音")
                  if any(w in x for x in words)]
        found = tools.assets_lib.find(words, limit=8)
        if not found:
            return None
        # 掲示物なので「ピクト」「アイコン」フォルダの素材を優先する
        # （JIS Z8210 の公式図記号を置いてもらうのがここ）
        priority = [p for p in found
                    if any(k in str(p.parent).lower() for k in ("ピクト", "アイコン", "picto", "icon"))]
        return (priority or found)[0]
    except Exception:
        return None


def _embed(path) -> str:
    """画像をdata URIで埋め込む（相対パスはブラウザが読めないため）。"""
    import base64

    suffix = Path(path).suffix.lower()
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "svg": "image/svg+xml",
            "webp": "image/webp"}.get(suffix.lstrip("."), "image/png")
    return "data:%s;base64,%s" % (mime,
                                  base64.b64encode(Path(path).read_bytes()).decode("ascii"))


def _build_html(signage: Dict[str, Any], illustration=None,
                template_id: str = "", paper: str = "A4") -> str:
    """掲示物の紙面を組む。**型（禁止／お知らせ／お願い／案内）で並びが変わる。**

    型を分けた理由は core/signage_templates.py に書いてある。
    要点は「禁止の様式でお願いを書くと威圧的になり、逆は守られない」。
    """
    import tools
    from core import signage_templates

    template = (signage_templates.get(template_id)
                or signage_templates.get("sign_ban"))
    accent = template["accent"]
    # 用紙（A4/A3・縦横）で級数と余白を丸ごと伸縮させる。
    # 紙だけ大きくして級数を据え置くと、余白が増えるだけで掲示物にならない
    size = signage_templates.metrics(paper)
    k = size["k"]
    headline = signage["headline"]
    length = len(headline)
    h1 = 92 if length <= 4 else (74 if length <= 6 else (56 if length <= 8 else 44))
    letter_spacing = 0.09 if length <= 6 else 0.03

    # 文字は切らず、長さに応じて級数を落として収める
    message = signage["message"]
    msg = 33 if len(message) <= 16 else (28 if len(message) <= 26 else 23)
    sub_text = signage["sub"]
    sub_size = 13.5 if len(sub_text) <= 34 else (11.5 if len(sub_text) <= 48 else 10)
    note_size = 15.5 if len(signage.get("reason", "")) <= 30 else 13.5

    try:
        fontface = tools.fonts_lib.face_css("Noto Sans JP")
        fontstack = tools.fonts_lib.stack("Noto Sans JP")
    except Exception:
        fontface, fontstack = "", "'Hiragino Sans','Yu Gothic',sans-serif"

    en_html = '<div class="en">%s</div>' % _escape(sub_text) if sub_text else ""
    reason_html = ('<div class="reason">%s</div>' % _escape(signage["reason"])
                   if signage.get("reason") else "")

    # 段階的な対応（警告→猶予→撤去など）。文章で書くより伝わり、根拠にもなる
    flow_html = ""
    steps = signage.get("steps") or []
    if len(steps) >= 2:
        cells = "".join(
            '<div class="step"><span class="n">%d</span><div class="t">%s</div></div>'
            % (i, _escape(s).replace("／", "<br>"))
            for i, s in enumerate(steps[:4], start=1))
        flow_html = ('<div class="flow"><div class="cap">%s</div>'
                     '<div class="steps">%s</div></div>'
                     % (_escape(signage.get("steps_caption") or "対応の流れ"), cells))

    wide = size["pw"] > size["ph"]
    # 記号は紙に合わせて伸縮。横向きは左半分が空くので、もとの寸法も大きく作る
    # （CSSの上限だけ広げても、元のSVGが小さいままだと大きくならない）
    picto_px = int(205 * k * (1.9 if wide else 1.0))
    if illustration is not None:
        picto = ('<img src="%s" style="height:%smm">'
                 % (_embed(illustration),
                    size["pictowide"] if wide else size["pictoh"]))
    else:
        names = signage["pictograms"]
        if template_id in ("sign_ban", "sign_security"):
            # 禁止の紙面に素の記号を混ぜない（「自転車OK」に読めてしまう）
            names = tools.pictograms.to_prohibition(names)
        picto = tools.pictograms.svg_group(names, size=picto_px, color=accent)

    if template_id == "sign_recruit" and signage.get("contact"):
        # 応募先は色帯で大きく出している。締め帯で同じ番号を繰り返さない
        foot = "<b>%s</b>" % _escape(signage.get("company") or "")
    elif signage["contact"]:
        parts_ = signage["contact"].split("　", 1)
        foot = ("<b>%s</b>%s" % (_escape(parts_[0]),
                                 "　" + _escape(parts_[1]) if len(parts_) > 1 else ""))
    else:
        # 連絡先が分からないときは作らず、手書きの記入欄にする。
        # 撤去予定日まで置くと、掲示した時点で期限が決まって運用しやすい
        foot = ('管理会社 <span class="blank"></span>　'
                'TEL <span class="blank" style="min-width:40mm"></span><br>'
                '掲示日 <span class="blank" style="min-width:34mm"></span>　'
                '%s <span class="blank" style="min-width:34mm"></span>'
                % _escape(signage.get("deadline_label") or "撤去予定日"))

    # 多言語の併記はしない。管理物件の掲示は日本語だけで通す方針
    multi_html = ""

    # お知らせ型の表（日時・場所・内容）。notes に「項目：値」で来たものを拾う
    table_html = ""
    rows = []
    for note in signage.get("notes") or []:
        for sep in ("：", ":"):
            if sep in note:
                label, value = note.split(sep, 1)
                rows.append((label.strip(), value.strip()))
                break
    if rows:
        table_html = ('<table class="infotable">%s</table>'
                      % "".join("<tr><th>%s</th><td>%s</td></tr>"
                                % (_escape(a), _escape(b)) for a, b in rows[:5]))

    # お願い型のカード。項目を並べるだけで、番号は振らない（順序が無いため）
    cards_html = ""
    items = [x for x in (signage.get("notes") or []) if x]
    if items:
        cards_html = ('<div class="cards">%s</div>'
                      % "".join('<div class="card">%s</div>' % _escape(x)
                                for x in items[:3]))

    # 案内型の矢印。向きが分からなければ右（最も多い）
    arrow = signage_templates.arrow_svg(signage.get("arrow", "right"), accent)
    dist_html = ('<div class="dist">%s</div>' % _escape(signage["reason"])
                 if signage.get("reason") else "")

    # 行き先は1〜2行に収める。長い文言を大きいままにすると1文字だけ次行に落ちる
    dest_size = 52 if len(message) <= 8 else (42 if len(message) <= 12 else 34)
    # 料金表（項目と金額）。表の行は notes の「項目：値」から作る
    price_html = ("<table class=\"pricelist\">%s</table>"
                  % "".join("<tr><td>%s</td><td>%s</td></tr>"
                            % (_escape(a), _escape(b)) for a, b in rows[:8])) if rows else ""
    hours_html = ('<div class="hours">%s</div>' % _escape(signage["reason"])
                  if signage.get("reason") else "")

    # 募集（条件の項目立て）＋応募先の色帯
    recruit_html = ("<table class=\"recruit\">%s</table>"
                    % "".join("<tr><th>%s</th><td>%s</td></tr>"
                              % (_escape(a), _escape(b))
                              for a, b in rows[:6])) if rows else ""
    apply_html = ""
    if signage.get("contact"):
        apply_html = ('<div class="apply"><div class="t">ご応募・お問い合わせ</div>'
                      '<div class="v">%s</div></div>' % _escape(signage["contact"]))

    # 配布用の文書（拝啓〜記〜以上）。掲示物と違い、体裁が決まっている
    kaki_html = ""
    if rows:
        kaki_html = ('<div class="doc-kaki"><div class="cap">記</div><table>%s</table></div>'
                     % "".join("<tr><th>%s</th><td>%s</td></tr>"
                               % (_escape(a), _escape(b)) for a, b in rows[:6]))
    doc_body = signage.get("message", "")
    if signage.get("reason"):
        doc_body = (doc_body + "\n" + signage["reason"]).strip()
    # 「敬具」は右寄せが決まり。左に置くと素人の文書に見える
    doc_body = _escape(doc_body).replace(
        "敬具", '<span style="display:block;text-align:right">敬具</span>')

    scale = lambda v: round(v * k, 1)
    css = signage_templates.BASE_CSS.format(
        fontface=fontface, fontstack=fontstack, accent=accent,
        h1=scale(h1), ls=letter_spacing, sub=scale(sub_size), msg=scale(msg),
        note=scale(note_size), dest=scale(dest_size), doc=scale(12),
        capf=scale(12), stepnf=scale(16), steptf=scale(14), periodwide=scale(26),
        **{key: value for key, value in size.items() if key != "k"})
    body = template["build"]({
        "headline": _escape(headline), "en": en_html, "picto": picto,
        "message": _escape(message).replace("／", "<br>"),
        "reason": reason_html, "flow": flow_html, "foot": foot, "multi": multi_html,
        "table": table_html, "cards": cards_html, "arrow": arrow, "dist": dist_html,
        "price": price_html, "hours": hours_html,
        "recruit": recruit_html, "apply": apply_html,
        # 横長の紙かどうか。型はこれを見て左右に振り分ける
        "wide": wide,
        "date": _escape(signage.get("date", "")), "to": _escape(signage.get("to", "")),
        "from_": _escape(signage.get("contact", "")).replace("　", "<br>"),
        "body": doc_body, "kaki": kaki_html,
    })
    return "<style>%s</style>%s" % (css, body)


def _escape(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _paper_for(ctx: JobContext, plan: Dict[str, Any]) -> str:
    """用紙を決める。依頼文の指定が最優先、無ければA4縦。

    掲示板に貼るものはA3が要る（実物の掲示物にB4・A3がある）。
    指定が無いのに大きくすると印刷できない事務所があるので、既定はA4のまま。
    """
    from core import signage_templates

    text = "%s %s" % (ctx.brief or "", plan.get("paper", ""))
    landscape = any(word in text for word in ("横向き", "横長", "横で", "ヨコ", "landscape"))
    if "A3" in text.upper():
        return "A3_LANDSCAPE" if landscape else "A3"
    if "B4" in text.upper():
        # B4の指定はA3に寄せる（B4はコピー機で扱えない事務所が多い）
        return "A3_LANDSCAPE" if landscape else "A3"
    chosen = str(ctx.options.get("paper") or "").upper()
    if chosen in signage_templates.PAPERS:
        return chosen
    return "A4_LANDSCAPE" if landscape else "A4"
