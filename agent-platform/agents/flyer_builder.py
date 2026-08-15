"""12 チラシ・紙面ビルダー

役割: A4のチラシ／POP／紙面を作る。スライドとは別物なので部隊を分けている。
使用: LLMがHTML+CSSを書き、Playwright（tools/flyer.py）がA4のPDF/PNGに焼く。

なぜHTMLか:
  パワポは「スライド」の道具で、紙面のレイアウト（余白・級数・段組み）を詰めるのに向かない。
  HTML+CSSならブラウザがそのまま印刷品質で組んでくれて、日本語フォントも化けない。

写真の扱い:
  アップロードされた実写真があればそれを使う。生成画像しか無いときは、
  実在の物件・商品のチラシに使うと不当表示になり得るため、その旨を警告に残す。
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Dict, List

from core.base_agent import BaseAgent, register
from core.context import JobContext
from core.io_utils import slugify, write_text

MAX_PHOTOS = 12

SYSTEM = """あなたは紙面デザイナーです。A4のチラシを**部品を並べて**組みます。

HTMLやCSSは書きません。用意された部品から選び、順番と中身を決めるだけです。
部品は検証済みなので、選んで並べれば崩れません。

守ること:
- 一番言いたいことを最初の3分の1に置く
- **渡された写真は原則すべて使う**（物件チラシは写真の点数がそのまま反響に効く）
- 条件は spec_table にする。文章に混ぜない
- 「※要確認」などの注記・免責を書かない（別に出すので不要）
- 実在しない数値・特典・キャッチコピーを作らない"""


@register
class FlyerBuilderAgent(BaseAgent):
    key = "flyer"
    name_ja = "チラシビルダー"
    role_ja = "A4のチラシ・紙面を部品を組み合わせて作る"
    icon = "📄"
    uses = "部品ライブラリ ＋ Playwright（HTML→A4 PDF）"
    # 紙面の文言と構成は成果物そのもの。ここをケチると全部が台無しになる
    llm_role = "reasoning"
    produces_deliverable = True
    # 原稿（企画構成ライター）は**要らない**。チラシの文言はここが調査結果から
    # 直接書いている。原稿を待つと、紙面に届かない工程のために60秒待つことになる。
    depends_on = ()
    # **調査は必ず待つ。** 事実と写真がここの材料なので、待たずに走ると
    # 写真0枚・条件なしの紙面ができる（実際にそうなった）。
    # 原稿（supervisor）とビジュアルは「あれば待つ」だけでよい。
    depends_if_present = ("researcher", "supervisor", "image")
    deliverable = "flyer"

    def _run(self, ctx: JobContext) -> Dict[str, Any]:
        import tools
        from core import blocks

        ok, note = tools.flyer.available()
        if not ok:
            return {"summary": "チラシを作る道具が使えません（%s）" % note, "degraded": True}

        plan = ctx.state.get("plan", {})
        deck = ctx.state.get("deck") or _deck_from_plan(plan, ctx)
        if not deck:
            return {"summary": "紙面に載せる内容がありません", "degraded": True}

        photos = self._collect_photos(ctx)
        # **写真が何の写真かを、ここで見て確かめる。**
        # 以前はビジュアル制作が判別していたが、その結果を使うのはこの部隊だけ。
        # 受け渡しを1つ減らし、LLMの往復も1回減らす（実測30秒）。
        if photos and not ctx.state.get("photo_labels"):
            ctx.state["photo_labels"] = self._label_photos(ctx, photos)
        real = sum(1 for p in photos if "input" in str(p))
        _warn_low_resolution(self, ctx, photos)
        self.log(ctx, "A4チラシを組みます（写真%d枚／うち実写真%d枚）" % (len(photos), real))

        genre = str(plan.get("genre") or "").lower()
        degraded = False
        data = {}
        template_id = ""
        if genre in ("promo", "maisoku"):
            # **物件チラシは型（レイアウト）で組む。**
            # 並べ方をLLMに毎回考えさせると出来が安定せず、良かった並びも次に活きない。
            # LLMには文言と「どの写真が外観・間取り・室内か」だけを書かせる。
            from core import layouts

            template_id = (str(plan.get("layout_template") or "").strip()
                           or layouts.choose(genre, len(photos)))
            data, result, _ = self.ask_json(
                ctx, _content_prompt(plan, deck, photos, ctx, genre),
                system=CONTENT_SYSTEM, max_tokens=3000, temperature=0.4)
            if not isinstance(data, dict) or not data.get("title"):
                self.note_degraded(ctx, result.error or "紙面の文言を受け取れませんでした")
                data = _fallback_content(deck, photos)
                degraded = True
            data["photos"] = _fix_hero_resolution(self, ctx, data.get("photos"), photos)
            data["contact"] = _contact_from_company()   # 連絡先はLLMに書かせない
            # **ビジュアル制作が判別した部屋名を紙面に渡す。**
            # 判別しておきながら渡していなかったため、「どの部屋か分からない」と
            # 最終確認で止まった。分かっている情報を捨てない。
            labels = {str(x.get("no")): str(x.get("label", ""))
                      for x in (ctx.state.get("photo_labels") or [])
                      if x.get("label")}
            if labels:
                data.setdefault("photo_captions", {}).update(labels)
            # **判別できているのに使われない、を防ぐ。**
            # 「3番＝間取り図」と分かっているのに文言生成が floorplan を落とし、
            # 間取り図の無いチラシが出た。分かっている情報は必ず紙面に回す。
            data["photos"] = _fill_photo_roles(self, ctx, data.get("photos"),
                                               labels, len(photos))
            data["photos"] = _prefer_landscape_hero(self, ctx, data["photos"],
                                                    photos, labels)
            _verify_features(self, ctx, data)
            data.update(_qr_settings(ctx))
            layout = layouts.build(template_id, data)
            ctx.state["flyer_content"] = data
            ctx.state["flyer_template"] = template_id
            self.log(ctx, "紙面の型は「%s」で組みます"
                     % (layouts.get(template_id) or {}).get("name", template_id))
        else:
            data, result, _ = self.ask_json(
                ctx, _build_prompt(plan, deck, photos, ctx), system=SYSTEM,
                max_tokens=4000, temperature=0.4)
            layout = []
            if isinstance(data, dict):
                layout = [x for x in (data.get("layout") or []) if isinstance(x, dict)]
            if not layout:
                self.note_degraded(ctx, result.error or "紙面の構成を受け取れませんでした")
                layout = _fallback_layout(deck, photos)
                degraded = True

        self.progress(ctx, "%d個の部品で紙面を組んでいます" % len(layout))
        from core import palettes

        palette = palettes.id_from_answer(str((data or {}).get("palette") or "")) \
            or palettes.guess(ctx.brief + " " + str(plan.get("title", "")), genre)
        ctx.state["flyer_palette"] = palette
        self.log(ctx, "配色は「%s」で組みます" % palettes.get(palette)["name"])

        # 書き出しは core/flyer_build に一本化している（同じ処理を写すと必ずずれる）
        from core import flyer_build

        name = slugify(deck.get("title", "")) or "flyer"
        paper = "A4"
        if genre in ("promo", "maisoku"):
            from core import layouts as _layouts

            paper = _layouts.paper_of(template_id)
        made = flyer_build.render(layout, [str(p) for p in photos],
                                  ctx.dir("slides"), stem=name, paper=paper,
                                  palette=palette)
        html_path, pdf_path, png_path = made["html"], made["pdf"], made["png"]

        ctx.state["flyer"] = ctx.rel(pdf_path)
        ctx.state["flyer_layout"] = layout
        ctx.state["flyer_photos"] = [ctx.rel(p) for p in photos]
        ctx.add_artifact("pdf", pdf_path, label="チラシ（A4・PDF）", agent=self.key)
        ctx.add_artifact("image", png_path, label="チラシ（画像）", agent=self.key)
        ctx.add_artifact("markdown", html_path, label="チラシのHTML", agent=self.key)

        warning = "" if real else "実写真が1枚もありません。物件・商品の広告には実写真が必要です"
        if warning:
            self.log(ctx, warning, level="warn")
        return {
            "summary": "A4チラシを作りました（部品%d個・写真%d枚）%s"
                       % (len(layout), len(photos), "／" + warning if warning else ""),
            "detail": ctx.rel(pdf_path),
            "data": {"pdf": ctx.rel(pdf_path), "blocks": len(layout)},
            "degraded": degraded or bool(warning),
        }

    def _label_photos(self, ctx: JobContext, photos: List[Path]) -> List[Dict[str, Any]]:
        """写真を1枚ずつ見て、何が写っているかを短い言葉にする。

        claude CLI は画像を読めるので、実際に見て判断させる。
        「間取り図」を特定できることが特に重要（依頼で名指しされることが多い）。
        """
        from core.llm import complete_json

        listing = "\n".join("%d: %s" % (i, p.name) for i, p in enumerate(photos, 1))
        prompt = (
            "次の画像ファイルを Read で1枚ずつ開いて、**何が写っているか**を短く書いてください。\n\n"
            "フォルダ: %s\n%s\n\n"
            "不動産の写真なら「外観」「玄関」「LDK」「洋室」「和室」「浴室」「洗面」"
            "「トイレ」「キッチン」「収納」「バルコニー」「駐車場」「周辺environment」"
            "「間取り図」などの区分で。**間取り図（図面）かどうかは必ず正しく判定**してください。\n\n"
            'JSONだけを返してください: {"labels": [{"no": 1, "label": "外観", '
            '"note": "赤い三角屋根の外観"}]}'
            % (ctx.dir("input"), listing))

        data, result = complete_json(
            prompt, role="tools", max_tokens=2000, temperature=0.1,
            tools={"web": False, "dirs": [ctx.dir("input"), ctx.dir("images")],
                   "mcp": False})
        labels = []
        if isinstance(data, dict):
            for item in (data.get("labels") or []):
                if not isinstance(item, dict):
                    continue
                try:
                    no = int(item.get("no", 0))
                except (TypeError, ValueError):
                    continue
                if 1 <= no <= len(photos):
                    labels.append({"no": no, "label": str(item.get("label", ""))[:12],
                                   "note": str(item.get("note", ""))[:40]})
        if labels:
            kinds = "・".join(dict.fromkeys(x["label"] for x in labels if x["label"]))
            self.log(ctx, "写真の中身を確認しました（%s）" % kinds[:60])
        else:
            self.log(ctx, "写真の中身を判別できませんでした（キャプションは付けません）",
                     level="warn")
        return labels

    def _collect_photos(self, ctx: JobContext) -> List[Path]:
        """使える写真。アップロード・Web取り込みの実写真を最優先。"""
        real, made = [], []
        seen = set()
        for path in sorted(Path(ctx.dir("input")).glob("*")):
            if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                real.append(path)
                seen.add(path.name)
        for record in ctx.state.get("images", []):
            path = ctx.root / record["path"]
            if path.exists() and path.stat().st_size and path.name not in seen:
                made.append(path)
        return (real or made)[:12]


def _build_prompt(plan, deck, photos, ctx) -> str:
    from core import blocks

    body = "\n".join("- %s: %s" % (s["title"], " / ".join(s.get("bullets", [])))
                     for s in deck.get("slides", []))
    photo_lines = "\n".join("  %d: %s" % (i, p.name) for i, p in enumerate(photos, 1)) \
        or "  （写真なし）"
    research = ctx.state.get("research", {})
    facts = "\n".join("- %s: %s" % (f.get("question", ""), str(f.get("answer", ""))[:100])
                      for f in (research.get("findings") or [])[:8]) or "（なし）"

    return """次の内容でA4チラシ（縦）を組んでください。

【タイトル】{title}
【対象】{audience}
【目的】{goal}
【載せる内容】
{body}

【調べて確定している事実】
{facts}

**この事実は、そのまま数値で紙面に書いてください。**
「____円/月」「物件名____」のような記入欄にしてはいけません。
分かっているのに空欄にしたチラシは配れません。
記入欄にしてよいのは、発行者情報（会社名・電話・免許番号）が未登録のときだけです。

【使える写真（番号で指定。**実際に見て確認した中身**です）】
{photos}

写真のキャプションは、上の内容と**必ず一致させてください**。
外観の写真に「LDK」と付けるような取り違えは重大な不良です。
依頼で名指しされた写真（間取り図など）が一覧に無い場合は、
無いものを有るように書かず、その旨を成果物に反映しないでください。

{catalog}

次のJSON形式で返してください。
{{"accent": "#c1272d",
  "layout": [
    {{"block": "header_band", "title": "…", "sub": "…"}},
    {{"block": "photo_hero", "photo": 1, "height": 74}},
    {{"block": "price", "main": "5.9", "unit": "万円", "note": "…"}},
    {{"block": "photo_grid", "photos": [2,3,4,5,6], "cols": 3, "height": 30}},
    {{"block": "spec_table", "rows": [["間取り","3LDK"]]}},
    {{"block": "contact", "title": "お問い合わせ", "lines": ["…"]}}
  ]}}

部品は8〜12個。A4に収まる量にしてください（写真を大きくするなら点数を減らす）。""".format(
        title=deck.get("title", ""), audience=plan.get("audience", ""),
        goal=plan.get("goal", ""), body=body, facts=facts, photos=photo_lines,
        catalog=blocks.describe_for_prompt())


def _fallback_layout(deck, photos):
    """LLMが構成を返さなかったときの最低限。空手で帰らないため。"""
    layout = [{"block": "header_band", "title": deck.get("title", "ご案内"),
               "sub": deck.get("subtitle", "")}]
    if photos:
        layout.append({"block": "photo_hero", "photo": 1, "height": 78})
    if len(photos) > 1:
        layout.append({"block": "photo_grid",
                       "photos": list(range(2, min(len(photos), 7) + 1)),
                       "cols": 3, "height": 30})
    for slide in deck.get("slides", [])[:3]:
        layout.append({"block": "bullets", "title": slide.get("title", ""),
                       "items": slide.get("bullets", [])})
    return layout


def _embed_images(html: str, images) -> str:
    """<img src="img1"> を実ファイルの data URI に差し替える。

    相対パスのままだとブラウザが読めないため、base64で埋め込む。
    """
    for item in images:
        try:
            raw = Path(item["path"]).read_bytes()
        except OSError:
            continue
        uri = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
        html = html.replace('src="%s"' % item["id"], 'src="%s"' % uri)
        html = html.replace("src='%s'" % item["id"], 'src="%s"' % uri)
    return html


def _fallback_html(plan, deck, images) -> str:
    """LLMがHTMLを返さなかったときの最低限の紙面。空手で帰らないため。"""
    rows = "".join("<li>%s</li>" % s.get("title", "") for s in deck.get("slides", []))
    hero = ('<img src="%s" style="width:100%%;height:110mm;object-fit:cover">' % images[0]["id"]
            if images else "")
    return """<style>@page{margin:0}
body{margin:0;font-family:'Hiragino Sans','Yu Gothic',sans-serif;width:210mm;height:297mm}
h1{font-size:30pt;margin:0 0 6mm}.wrap{padding:14mm}ul{font-size:13pt;line-height:1.9}</style>
%s<div class="wrap"><h1>%s</h1><ul>%s</ul></div>""" % (
        hero, deck.get("title", ""), rows)


CONTENT_SYSTEM = """あなたは不動産チラシのコピーライターです。
紙面のレイアウトは決まっているので、**中に入る文言と、写真の役割だけ**を決めます。

守ること:
- キャッチは暮らしの情景を1行で。「〇〇な毎日を。」のような空疎な決まり文句は書かない
- 条件（賃料・面積・築年など）は spec_rows に入れる。文章に混ぜない
- spec_rows の**最後は必ず「備考」**にする。他の項目に収まらないこと
  （更新料・入居時期・相談可の条件・現況など）をここにまとめる。
  書くことが無ければ備考の行は入れない（空欄の「備考」を作らない）
- 分かっている数値は必ず数値で書く。「____円」のような空欄にしない
- **調べた事実に出てこない設備・特典・数値は、絶対に書かない**
  （オートロック、追焚き、南向きなどを「ありそうだから」で足すのは不当表示になる）
- 設備は、上の事実に**その言葉が出てくるものだけ**を icons / badges に入れる
- 「※要確認」などの注記・免責は書かない（別に出すので不要）"""


def _content_prompt(plan, deck, photos, ctx, genre) -> str:
    body = "\n".join("- %s: %s" % (s.get("title", ""), " / ".join(s.get("bullets", [])))
                     for s in deck.get("slides", []))
    photo_lines = "\n".join("  %d: %s" % (i, p.name) for i, p in enumerate(photos, 1)) \
        or "  （写真なし）"
    research = ctx.state.get("research", {})
    facts = "\n".join("- %s: %s" % (f.get("question", ""), str(f.get("answer", ""))[:120])
                      for f in (research.get("findings") or [])[:10]) or "（なし）"
    tone = ("業者向けの物件概要です。感情に訴える表現は不要で、条件の網羅と正確さを優先。"
            if genre == "maisoku" else
            "お客様に見せるPRチラシです。写真と1行のキャッチで気持ちを動かします。")

    try:
        from tools import feature_icons

        icons_text = feature_icons.describe_for_prompt()
    except Exception:
        icons_text = ""

    try:
        from core import palettes

        palette_text = palettes.describe_for_prompt()
    except Exception:
        palette_text = ""

    return """次の物件でA4チラシ（縦）の**文言**を決めてください。

【この紙面の性格】{tone}
【タイトル】{title}
【対象】{audience}
【載せる内容】
{body}

【調べて確定している事実（そのまま数値で書く）】
{facts}

【使える写真（番号で指定。中身は実際に見て確認したものです）】
{photos}

{palettes}

{icons}
アイコンは**この一覧にある名前だけ**を icons に入れてください。
一覧に無い設備はアイコンにできないので、badges（文字のタグ）に回してください。
物件に無い設備を書いてはいけません。

写真の役割を必ず決めてください。
  hero      … 一番目立つ1枚（通常は外観。室内が売りなら室内でもよい）
  floorplan … 間取り図・図面（**写真ではないもの**。無ければ null）
  rooms     … 残りの室内・設備。良い順に並べる

次のJSON形式で返してください。
{{"palette": "配色の名前（上の一覧から1つ）",
  "kicker": "所在地や種別など、キャッチの上に小さく出す1行",
  "catch": "大きく出すキャッチ1行（20字前後）",
  "title": "物件名・種別・間取り",
  "sub": "敷金・礼金などの補足1行",
  "price": "59,000", "unit": "円 / 月",
  "lead": "紙面に1〜2行で入れる説明文",
  "badges": ["設備・条件を短く", "6個まで"],
  "icons": ["下の一覧にある名前だけを6個まで。無ければ空配列"],
  "appeals": [{{"title": "推しの見出し", "text": "10字程度の説明"}}],
  "spec_rows": [["間取り", "3LDK"], ["専有面積", "62.73㎡"], ["備考", "更新料なし／即入居可"]],
  "photos": {{"hero": 1, "floorplan": 2, "rooms": [3, 4, 5]}}
}}""".format(tone=tone, title=deck.get("title", ""), audience=plan.get("audience", ""),
             body=body, facts=facts, photos=photo_lines, icons=icons_text, palettes=palette_text)


def _contact_from_company():
    """連絡先は登録済みの発行者情報から入れる。**LLMには書かせない**。

    過去に架空の電話番号を書いた事故があった。印刷物に出る情報なので、
    人が登録した値だけを使う。
    """
    try:
        from core import company

        data = company.load()
    except Exception:
        return {}
    return {"label": "ご見学・お問い合わせ", "tel": data.get("tel", ""),
            "company": data.get("name", ""),
            # 宅建業法で表示が要る。登録済みならそのまま印字する
            "license": data.get("license", ""),
            "address": " ".join(x for x in (data.get("zip", ""),
                                            data.get("address", "")) if x)}


def _fallback_content(deck, photos):
    """LLMが文言を返さなかったときの最低限。空手で帰らないため。"""
    rooms = list(range(3, min(len(photos), 9) + 1))
    return {"kicker": deck.get("subtitle", ""), "catch": deck.get("title", ""),
            "title": deck.get("title", ""), "sub": "", "price": "", "unit": "円 / 月",
            "lead": "", "badges": [], "appeals": [],
            "spec_rows": [[s.get("title", ""), " / ".join(s.get("bullets", []))]
                          for s in deck.get("slides", [])[:8]],
            "photos": {"hero": 1 if photos else None,
                       "floorplan": 2 if len(photos) > 1 else None, "rooms": rooms}}


def _qr_settings(ctx):
    """QRを入れるかどうかと、その中身。

    入れる指定なのに中身が空なら、発行者情報のサイトを使う。
    それも無ければ**QRは出さない**（読み込めないQRを刷ると信用に関わる）。
    """
    on = bool(ctx.options.get("qr_on"))
    url = str(ctx.options.get("qr") or "").strip()
    if on and not url:
        try:
            from core import company

            url = str(company.load().get("website") or "").strip()
        except Exception:
            url = ""
    return {"qr_on": bool(on and url), "qr": url,
            "qr_label": str(ctx.options.get("qr_label") or "").strip()
            or "詳しくはこちら"}


def _deck_from_plan(plan, ctx):
    """原稿部隊を通さないときの、最低限の中身。

    チラシの文言はこの部隊が調査結果から直接書くので、
    スライド原稿は本来要らない。ここでは題名と調べた事実だけを渡す。
    """
    title = str(plan.get("title") or "").strip()
    if not title:
        return None
    findings = (ctx.state.get("research") or {}).get("findings") or []
    bullets = [str(f.get("answer", ""))[:120] for f in findings[:6]]
    return {"title": title, "subtitle": str(plan.get("subtitle") or ""),
            "slides": [{"no": 1, "title": title, "bullets": bullets,
                        "narration": "", "image_prompt": ""}]}


# メイン写真に必要な画素数。A4全幅（210mm）で最低150dpiを確保できる幅
HERO_MIN_WIDTH = 1240


def _pixel_width(path) -> int:
    """紙面での使いでを表す画素数＝**長辺**。

    幅だけで見ると縦長の写真を不当に低く評価する（室内は縦位置で撮ることが多い）。
    """
    try:
        from PIL import Image

        with Image.open(path) as img:
            return max(img.size)
    except Exception:
        return 0


def _warn_low_resolution(agent, ctx, photos) -> None:
    """紙面に使うには小さすぎる写真を知らせる。

    印刷して初めて気づくと刷り直しになるので、作る時点で言う。
    """
    small = [(p, _pixel_width(p)) for p in photos]
    small = [(p, w) for p, w in small if 0 < w < 800]
    if small:
        agent.log(ctx, "画素の小さい写真が%d枚あります（%s）。大きく使うと粗くなります"
                  % (len(small), "・".join("%s %dpx" % (Path(p).name, w)
                                           for p, w in small[:3])), level="warn")


def _pixel_shape(path):
    try:
        from PIL import Image

        with Image.open(path) as img:
            return img.size
    except Exception:
        return (0, 0)


def _prefer_landscape_hero(agent, ctx, picked, photos, labels):
    """メイン写真は**横長を優先**する。

    メインは紙面の幅いっぱいの帯に入る。縦long長の写真をそこに入れると
    上下が大きく切られ、建物の一部しか映らない（実際に外観が判別できず、
    最終確認に「上下反転している」とまで誤読された）。
    """
    picked = dict(picked or {})
    try:
        hero = int(picked.get("hero"))
    except (TypeError, ValueError):
        return picked
    if not (1 <= hero <= len(photos)):
        return picked
    width, height = _pixel_shape(photos[hero - 1])
    if not height or width >= height:
        return picked          # すでに横長なら触らない

    plan_no = picked.get("floorplan")

    def is_outside(no):
        return "外観" in str(labels.get(str(no), labels.get(no, "")))

    wide = [i for i, p in enumerate(photos, 1)
            if i not in (hero, plan_no) and _pixel_shape(p)[0] > _pixel_shape(p)[1]]
    wide.sort(key=lambda i: (not is_outside(i), -_pixel_shape(photos[i - 1])[0]))
    if not wide:
        return picked
    best = wide[0]
    rooms = [x for x in (picked.get("rooms") or []) if x != best]
    if hero not in rooms:
        rooms.insert(0, hero)
    picked["hero"], picked["rooms"] = best, rooms
    agent.log(ctx, "メイン写真を横長の%d番に差し替えました（縦長は幅いっぱいの帯で"
              "上下が大きく切れるため）" % best)
    return picked


def _fix_hero_resolution(agent, ctx, picked, photos):
    """メイン写真が小さすぎるときは、**一番大きい写真と入れ替える**。

    254x169 のサムネイルがメインに選ばれ、A4全幅に引き伸ばされて実効30dpiになった。
    見た目の良し悪し以前に、印刷物として成立しない。
    """
    picked = dict(picked or {})
    try:
        hero = int(picked.get("hero"))
    except (TypeError, ValueError):
        return picked
    if not (1 <= hero <= len(photos)):
        return picked
    width = _pixel_width(photos[hero - 1])
    if width >= HERO_MIN_WIDTH or width == 0:
        return picked

    plan_no = picked.get("floorplan")
    candidates = [(i, _pixel_width(p)) for i, p in enumerate(photos, 1)
                  if i != plan_no]
    candidates.sort(key=lambda x: -x[1])
    if not candidates or candidates[0][1] <= width:
        agent.log(ctx, "メインに使える大きな写真がありません（最大%dpx）。粗く出ます"
                  % (candidates[0][1] if candidates else 0), level="warn")
        return picked

    best = candidates[0][0]
    rooms = [x for x in (picked.get("rooms") or []) if x != best]
    if hero not in rooms:
        rooms.append(hero)
    picked["hero"], picked["rooms"] = best, rooms
    agent.log(ctx, "メイン写真が小さすぎたため（%dpx）、大きい%d番（%dpx）に差し替えました"
              % (width, best, candidates[0][1]), level="warn")
    return picked


PLAN_WORDS = ("間取", "図面", "平面図")


def _fill_photo_roles(agent, ctx, picked, labels, count):
    """写真の役割の抜けを、判別結果から埋める。

    文言生成は本文づくりが主で、写真の割り当ては落ちることがある。
    ここで機械的に補う（判別済みの事実なので、AIに任せる必要が無い）。
    """
    picked = dict(picked or {})
    numbers = {int(k) for k in labels if str(k).isdigit()}

    def label_of(no):
        return str(labels.get(str(no), labels.get(no, "")))

    plan_no = picked.get("floorplan")
    if not plan_no:
        for no in sorted(numbers):
            if any(word in label_of(no) for word in PLAN_WORDS):
                picked["floorplan"] = plan_no = no
                agent.log(ctx, "間取り図（%d番）を紙面に入れます" % no)
                break

    hero = picked.get("hero")
    if not hero or hero == plan_no:
        outside = [no for no in sorted(numbers) if "外観" in label_of(no)
                   and no != plan_no]
        picked["hero"] = hero = (outside or [n for n in range(1, count + 1)
                                             if n != plan_no] or [1])[0]

    rooms = [x for x in (picked.get("rooms") or [])
             if isinstance(x, int) and x not in (hero, plan_no)]
    if not rooms:
        rooms = [n for n in range(1, count + 1) if n not in (hero, plan_no)]
    picked["rooms"] = rooms
    return picked


def _source_text(ctx) -> str:
    """紙面の内容を突き合わせる元になる文章（ページ本文＋調査結果＋依頼文）。"""
    parts = [str(ctx.brief or ""), str(ctx.state.get("page_text") or "")]
    for item in ((ctx.state.get("research") or {}).get("findings") or []):
        parts.append("%s %s" % (item.get("question", ""), item.get("answer", "")))
    deck = ctx.state.get("deck") or {}
    for slide in deck.get("slides", []):
        parts.append(" ".join(str(x) for x in (slide.get("bullets") or [])))
    return _normalize_text(" ".join(parts))


def _normalize_text(text: str) -> str:
    """突き合わせ用に、区切り文字と全半角の揺れをならす。"""
    import re
    import unicodedata

    text = unicodedata.normalize("NFKC", str(text or ""))
    return re.sub(r"[\s・･,、／/｜|]+", "", text).lower()


def _verify_features(agent, ctx, data) -> None:
    """**元データに無い設備を紙面から外す。**

    実際に「オートロック」のアイコンが勝手に入った。物件に無い設備を広告に
    載せるのは不当表示（景表法）で、印刷して配ると取り返しがつかない。
    ページ本文と調査結果に**その言葉が出てこない設備は落とす**。
    言い換え（宅配ボックス＝宅配BOX 等）は照合してから判定する。
    """
    source = _source_text(ctx)
    if len(source) < 60:
        return          # 突き合わせる材料が無いときは触らない

    try:
        from tools import feature_icons

        aliases = feature_icons.ALIASES
    except Exception:
        aliases = {}

    def supported(word: str) -> bool:
        name = str(word).strip()
        if not name:
            return False
        candidates = [name, name.rstrip("有可付き"), name.replace("有", "")]
        candidates += list(aliases.get(name, ()))
        for key, alts in aliases.items():
            if name == key or name in alts:
                candidates += [key] + list(alts)
        for candidate in candidates:
            candidate = _normalize_text(candidate)
            if len(candidate) >= 2 and candidate in source:
                return True
        return False

    for key in ("icons", "badges"):
        items = [str(x).strip() for x in (data.get(key) or []) if str(x).strip()]
        kept = [x for x in items if supported(x)]
        dropped = [x for x in items if x not in kept]
        if dropped:
            agent.log(ctx, "元データに無い%sを外しました: %s"
                      % ("設備アイコン" if key == "icons" else "特徴タグ",
                         "・".join(dropped)), level="warn")
        data[key] = kept
