"""04 ビジュアル制作（画像の用意）

役割: スライド・動画・チラシに使う画像を用意する。
方針: **全部無料の範囲で作る。**

  1. アップロードされた実写真があれば、それを使う（最優先）
  2. 足りない分は **HTML+CSS で組んだカードを Playwright で画像化**する
     （見出し・数字・箇条書きが入った図版。文字が崩れず、1枚2秒、無料）
  3. Playwright も無い場合だけ Pillow の簡易画像

AI画像生成（DALL-E / Gemini画像 / Stability）は**使わない**。理由は3つ:
  - どれも有料で、無料枠が無い（2026-08-14 確認）
  - 日本語の文字が崩れる
  - 実在の物件・商品の広告に生成画像を使うと不当表示になり得る
どうしても使う場合は `.env` で AP_ALLOW_PAID=1 かつ AP_IMAGE_BACKEND を明示する。
"""
from __future__ import annotations

import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List

from core.base_agent import BaseAgent, register
from core.config import get_settings
from core.context import JobContext
from core.fonts import load_font
from core.io_utils import write_json

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")
MAX_PARALLEL = 4

# カードの配色。スライドごとに変えて単調さを避ける
PALETTES = [
    ("#0f2b46", "#2f89b8", "#ffd166"),
    ("#14332b", "#2e8b70", "#ffe08a"),
    ("#331f3f", "#7b4f9d", "#ffc2e2"),
    ("#3a2617", "#a8703c", "#ffd9a0"),
    ("#1b2340", "#4159a6", "#9fd0ff"),
]

CARD_HTML = """<style>
@page{{margin:0}} *{{box-sizing:border-box}}
body{{margin:0;width:{w}px;height:{h}px;overflow:hidden;
 font-family:'Hiragino Sans','Yu Gothic',sans-serif;color:#fff;
 background:linear-gradient(135deg,{c1} 0%,{c2} 100%);position:relative}}
.grid{{position:absolute;inset:0;opacity:.09;
 background-image:linear-gradient(#fff 1px,transparent 1px),
                  linear-gradient(90deg,#fff 1px,transparent 1px);
 background-size:{grid}px {grid}px}}
.blob{{position:absolute;border-radius:50%;background:#fff;opacity:.07}}
.b1{{width:{blob}px;height:{blob}px;right:-{blob2}px;top:-{blob2}px}}
.wrap{{position:relative;padding:{pad}px {pad}px {pad}px {pad}px;height:100%;
 display:flex;flex-direction:column;justify-content:center}}
.no{{font-size:{small}px;letter-spacing:.3em;opacity:.7}}
h1{{font-size:{title}px;line-height:1.2;margin:{gap}px 0 0;letter-spacing:.01em}}
.rule{{width:{rule}px;height:{ruleh}px;background:{accent};border-radius:3px;
 margin:{gap}px 0}}
ul{{margin:0;padding:0;list-style:none;font-size:{body}px;line-height:1.85;opacity:.94}}
li{{padding-left:{body}px;position:relative}}
li:before{{content:"";position:absolute;left:0;top:{dot}px;width:{dotw}px;height:{dotw}px;
 border-radius:50%;background:{accent}}}
</style>
<div class="grid"></div><div class="blob b1"></div>
<div class="wrap">
  <div class="no">{no}</div>
  <h1>{title_text}</h1>
  <div class="rule"></div>
  <ul>{items}</ul>
</div>"""


@register
class VisualsAgent(BaseAgent):
    key = "image"
    name_ja = "ビジュアル制作"
    role_ja = "実写真の割り当てと、文字入りカードの作図"
    icon = "🎨"
    uses = "実写真 ＋ HTML/CSS作図（Playwright・無料）"
    deliverable = "images"
    # 原稿を待たない。写真の判別に原稿は要らない
    depends_on = ()
    depends_if_present = ("supervisor",)
    wants_tools = False
    use_tools = False   # 作図に外部の知恵は要らない

    def _run(self, ctx: JobContext) -> Dict[str, Any]:
        st = get_settings()
        deck = ctx.state.get("deck")
        if not deck:
            return {"summary": "構成がまだ無いため、画像は用意していません", "degraded": True}

        slides = deck["slides"]
        photos = _uploaded_photos(ctx)
        if not photos:
            photos = self._fetch_from_pdf(ctx)
        if not photos:
            photos = self._fetch_from_web(ctx)
        # **手元に素材が無ければ、テーマからフリー写真を探す。**
        # ここが無いと、どのテーマでも文字だけの単調な面になる（実際にそうなった）。
        if len(photos) < len(slides):
            photos += self._fetch_free_photos(ctx, slides, len(slides) - len(photos))
        out_dir = ctx.dir("images")

        if photos:
            self.log(ctx, "アップロードされた写真 %d枚 を先に使います" % len(photos))
        if len(photos) < len(slides):
            self.log(ctx, "写真が足りない%d枚分は、文字入りカードを作図します（無料）"
                     % (len(slides) - len(photos)))

        width, height = st.video_size

        def build(item):
            index, slide = item
            dest = out_dir / ("slide_%02d.png" % slide["no"])
            self.progress(ctx, "%d枚目「%s」を用意しています" % (slide["no"], slide["title"]),
                          current=index + 1, total=len(slides))
            if index < len(photos):
                shutil.copyfile(photos[index], dest)
                return {"slide_no": slide["no"], "path": ctx.rel(dest),
                        "backend": "uploaded"}
            if _render_card(slide, index, dest, width, height):
                return {"slide_no": slide["no"], "path": ctx.rel(dest), "backend": "card"}
            _pillow_card(dest, slide, index, (width, height))
            return {"slide_no": slide["no"], "path": ctx.rel(dest), "backend": "stub"}

        workers = min(MAX_PARALLEL, max(1, len(slides)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            records = list(pool.map(build, list(enumerate(slides))))
        records.sort(key=lambda r: r["slide_no"])

        for record in records:
            ctx.add_artifact("image", ctx.root / record["path"],
                             label="%d枚目の画像" % record["slide_no"], agent=self.key,
                             backend=record["backend"])
        ctx.state["images"] = records
        # **写真が何の写真かを見て記録する。**
        # これが無いと、後工程はファイル名しか手掛かりが無く、
        # 外観に「LDK」、和室に「水回り」といった取り違えが起きる（実際に起きた）。
        if photos:
            ctx.state["photo_labels"] = self._label_photos(ctx, photos)

        used = {"uploaded": 0, "card": 0, "stub": 0}
        for record in records:
            used[record["backend"]] = used.get(record["backend"], 0) + 1
        detail = ""
        if not photos:
            detail = "実写真が1枚もありません。物件・商品の広告には実写真が必要です"
            self.log(ctx, detail, level="warn")

        return {
            "summary": "画像 %d枚 を用意しました（実写真 %d / 作図 %d / 簡易 %d）"
                       % (len(records), used["uploaded"], used["card"], used["stub"]),
            "detail": detail,
            "data": {"images": records},
            "degraded": bool(detail),
        }


    def _label_photos(self, ctx: JobContext, photos: List[Path]):
        """写真の判別は**チラシビルダーに移した**（使うのがそこだけだったため）。

        動画・パワポ用にこの部隊が動くときも、紙面と同じ判別が要ることがあるので、
        処理はチラシビルダーのものを借りる。同じコードを2つ持たない。
        """
        from agents.flyer_builder import FlyerBuilderAgent

        return FlyerBuilderAgent._label_photos(self, ctx, photos)

    def _fetch_free_photos(self, ctx: JobContext, slides, need: int) -> List[Path]:
        """スライドの見出しから言葉を作って、フリー写真を探す。

        探す言葉は**英語**にする。Openverse は日本語の収録が薄く、
        「商店街」で海外の中華街が出た。英語なら狙ったものが出る。
        """
        import tools

        ok, note = tools.free_photos.available()
        if not ok or need <= 0:
            return []
        plan = ctx.state.get("plan") or {}
        queries = self._photo_queries(ctx, slides, plan)
        if not queries:
            return []
        self.log(ctx, "フリー写真を探します（%s）" % "／".join(queries[:3]))
        found: List[Path] = []
        credits = []
        for query in queries:
            got = tools.free_photos.fetch(query, ctx.dir("input"), count=2,
                                          orientation="wide")
            found += [Path(x["path"]) for x in got]
            credits += [x for x in got if tools.free_photos.credit(x)]
            if len(found) >= need:
                break
        if credits:
            ctx.state["photo_credits"] = [tools.free_photos.credit(x) for x in credits]
            self.log(ctx, "出典表示が要る写真が%d枚あります（credits.json に記録）"
                     % len(credits), level="warn")
        if found:
            self.log(ctx, "フリー写真を %d枚 取り込みました" % len(found))
        return found[:need]

    def _photo_queries(self, ctx: JobContext, slides, plan) -> List[str]:
        """探す言葉（英語）を決める。見出しから機械的に作らず、AIに短く訳させる。"""
        from core.llm import complete_json

        titles = "／".join(str(s.get("title", "")) for s in slides[:8])
        prompt = ("次のスライドに合う写真を、写真素材サイトで探します。\n"
                  "**英語の検索語**を3〜5個作ってください。\n\n"
                  "【題名】%s\n【各面の見出し】%s\n\n"
                  "- 具体的な被写体にする（例: japanese shopping street at night）\n"
                  "- 抽象語だけにしない（例: success, growth は不可）\n"
                  '- JSONだけ: {"queries": ["...", "..."]}'
                  % (plan.get("title", ""), titles))
        data, _ = complete_json(prompt, role="fast", max_tokens=400, temperature=0.3)
        if isinstance(data, dict):
            return [str(x).strip() for x in (data.get("queries") or [])
                    if str(x).strip()][:5]
        return []

    def _fetch_from_pdf(self, ctx: JobContext) -> List[Path]:
        """添付・取得したPDFから写真と図版を取り出す。

        既存資料をPDFで渡されたとき、**中の図版が一番の素材**になる。
        取り出せないと文字カードだけの単調な動画・スライドになる（実際になった）。
        """
        import tools

        ok, _ = tools.pdf_images.available()
        if not ok:
            return []
        found = tools.pdf_images.extract_all(ctx.dir("input"), ctx.dir("input"))
        if found:
            self.log(ctx, "資料PDFから図版・写真を %d点 取り出しました" % len(found))
            ctx.state["pdf_images"] = [ctx.rel(x["path"]) for x in found]
        return [Path(x["path"]) for x in found]

    def _fetch_from_web(self, ctx: JobContext) -> List[Path]:
        """依頼文のURLから掲載写真を取り込む。

        チラシは実写真が主役。アップロードが無くてもURLがあるなら、
        そこから回収する（これが無いと作図カードだけの紙面になる）。
        **権利は依頼者が持っている前提**。出典URLを記録して後から確認できるようにする。
        """
        import re

        # **リサーチャーが同じページから既に回収していれば、それを使う。**
        # 同じページを2度読むと、その分だけ待ち時間が倍になる（実測で1回5〜8分だった）
        already = [ctx.root / x for x in (ctx.state.get("harvested_photos") or [])]
        already = [x for x in already if x.exists()]
        if already:
            self.log(ctx, "調査が取り込んだ掲載写真 %d枚 をそのまま使います" % len(already))
            return already

        urls = re.findall(r"https?://[^\s、。）)\"']+", ctx.brief or "")
        if not urls:
            return []
        try:
            import tools

            ok, note = tools.photos.available()
            if not ok:
                self.log(ctx, "写真の取り込みは使えません（%s）" % note, level="warn")
                return []
            self.log(ctx, "依頼のURLから掲載写真を取り込みます")
            found = tools.photos.extract_image_urls(urls[0], limit=12)
            if not found:
                self.log(ctx, "ページから写真を見つけられませんでした", level="warn")
                return []
            saved = tools.photos.download(found, ctx.dir("input"), prefix="web")
            if saved:
                write_json(ctx.dir("input") / "_photo_sources.json",
                           {"page": urls[0], "images": saved})
                self.log(ctx, "写真を%d枚取り込みました（出典は _photo_sources.json）"
                         % len(saved))
            return [Path(x["path"]) for x in saved]
        except Exception as exc:
            self.log(ctx, "写真の取り込みに失敗しました（%s）" % exc, level="warn")
            return []


def _uploaded_photos(ctx: JobContext) -> List[Path]:
    return sorted(p for p in Path(ctx.dir("input")).glob("*")
                  if p.suffix.lower() in IMAGE_EXT)


def _render_card(slide: Dict[str, Any], index: int, dest: Path,
                 width: int, height: int) -> bool:
    """見出しと箇条書きが入ったカードをHTMLで組んで画像にする。"""
    try:
        import tools

        ok, _ = tools.flyer.available()
        if not ok:
            return False
        c1, c2, accent = PALETTES[index % len(PALETTES)]
        scale = height / 720.0
        items = "".join("<li>%s</li>" % _escape(b) for b in slide.get("bullets", [])[:4])
        html = CARD_HTML.format(
            w=width, h=height, c1=c1, c2=c2, accent=accent,
            grid=int(64 * scale), blob=int(520 * scale), blob2=int(150 * scale),
            pad=int(78 * scale), small=int(19 * scale), title=int(56 * scale),
            gap=int(20 * scale), rule=int(120 * scale), ruleh=max(int(6 * scale), 3),
            body=int(26 * scale), dot=int(14 * scale), dotw=max(int(9 * scale), 5),
            no="%02d" % slide["no"], title_text=_escape(slide.get("title", "")),
            items=items or "<li>&nbsp;</li>")
        tools.flyer.render(html, dest, fmt="png", size=(width, height))
        return dest.exists() and dest.stat().st_size > 0
    except Exception:
        return False


def _escape(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _pillow_card(dest: Path, slide: Dict[str, Any], index: int, size) -> None:
    """Playwrightも無い環境向けの最後の砦。後続を止めないためのもの。"""
    try:
        from PIL import Image, ImageDraw
    except Exception:
        dest.write_bytes(b"")
        return
    width, height = size
    top = tuple(int(PALETTES[index % len(PALETTES)][0][i:i + 2], 16) for i in (1, 3, 5))
    bottom = tuple(int(PALETTES[index % len(PALETTES)][1][i:i + 2], 16) for i in (1, 3, 5))
    img = Image.new("RGB", (width, height), top)
    draw = ImageDraw.Draw(img)
    for y in range(height):
        ratio = y / max(height - 1, 1)
        draw.line([(0, y), (width, y)],
                  fill=tuple(int(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3)))
    font = load_font(int(height * 0.07))
    if font:
        draw.text((int(width * 0.08), int(height * 0.42)), slide.get("title", ""),
                  font=font, fill=(255, 255, 255))
    img.save(dest, "PNG")
