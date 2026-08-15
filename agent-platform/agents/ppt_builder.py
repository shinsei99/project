"""05 パワポビルダー

役割: 構成原稿と素材を受け取り、**講演で使えるPowerPoint**を組み立てる。
使用: core/deck_pptx（python-pptx・APIキー不要・完全ローカル）

なぜ作り直したか:
  前は「左に箇条書き、右に画像」の1種類だけで、何枚並べても単調だった。
  実際に使われている講演資料（Googleドライブの277本）を調べると、
  **4:3・丸ゴシック・1枚に写真1〜6点・文字は見出しだけ**という作りだった。
  文字で説明する資料ではなく、**写真で見せて口で語る**資料になっている。

  そこで面の型を8種類（表紙・章扉・写真・図版・数字・記号3点・引用・締め）用意し、
  中身に合う型を選ばせる。写真が足りないときはフリー素材で埋め、
  **後から本物の写真に差し替えられる**ように、どこに何を置いたかを記録する。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from core.base_agent import BaseAgent, register
from core.context import JobContext
from core.io_utils import slugify, write_json

SYSTEM = """あなたは講演資料の構成者です。原稿を**スライドの面**に割り付けます。

面の型は決まっているので、あなたが決めるのは「どの面にするか」と「そこに載る言葉」だけです。

守ること:
- **1枚に詰め込まない**。要点は3つまで、文字は短く
- 写真が主役。説明は口で話す前提で、スライドには**見出しと要点だけ**置く
- 数字（回数・人数・金額）は numbers の面にまとめて大きく出す
- 事実を作らない。原稿に無い数字・固有名詞を足さない"""


@register
class PPTBuilderAgent(BaseAgent):
    key = "ppt"
    name_ja = "パワポビルダー"
    role_ja = "原稿と素材から、講演で使える .pptx を組み立てる"
    icon = "📊"
    uses = "python-pptx（ローカル処理）＋フリー素材"
    produces_deliverable = True
    depends_on = ()
    depends_if_present = ("researcher", "supervisor", "image")
    deliverable = "pptx"
    llm_role = "reasoning"

    def _run(self, ctx: JobContext) -> Dict[str, Any]:
        from core import deck_pptx

        deck = ctx.state.get("deck")
        if not deck:
            return {"summary": "構成がまだ無いため、スライドは作っていません",
                    "degraded": True}

        photos = self._photos(ctx)
        self.log(ctx, "スライドを組みます（使える素材 %d点）" % len(photos))

        data, result, _ = self.ask_json(ctx, _build_prompt(deck, photos, ctx),
                                        system=SYSTEM, max_tokens=4000,
                                        temperature=0.4)
        degraded = False
        spec = []
        if isinstance(data, dict):
            spec = [x for x in (data.get("slides") or []) if isinstance(x, dict)]
        if not spec:
            self.note_degraded(ctx, result.error or "面の割り付けを受け取れませんでした")
            spec = _fallback_spec(deck, photos)
            degraded = True

        spec = self._fill_photos(ctx, spec, photos)
        spec = _attach_images(spec, photos)
        name = slugify(deck.get("title", "")) or "deck"
        out = ctx.dir("slides") / ("%s.pptx" % name)
        deck_pptx.build(spec, out, paper=str(ctx.options.get("paper") or "4:3"))

        ctx.state["deck_spec"] = spec
        ctx.state["deck_photos"] = [ctx.rel(p) for p in photos]
        ctx.state["pptx"] = ctx.rel(out)
        write_json(ctx.dir("plan") / "deck_spec.json", spec)
        ctx.add_artifact("pptx", out, label="スライド（PowerPoint）", agent=self.key)

        kinds = {}
        for item in spec:
            kinds[item.get("type", "bullets")] = kinds.get(item.get("type"), 0) + 1
        return {
            "summary": "スライド %d枚を作りました（%s）"
                       % (len(spec), "・".join("%s%d" % (k, v) for k, v in kinds.items())),
            "detail": ctx.rel(out),
            "data": {"slides": len(spec)},
            "degraded": degraded,
        }

    def _fill_photos(self, ctx: JobContext, spec, photos) -> List[Dict[str, Any]]:
        """面ごとの `photo_query` で、フリー素材を探して割り当てる。

        **面ごとに探す**のが肝。全体で3〜5語まとめて探すと、
        どの面にも合わない写真が並ぶ（実際にそうなった）。
        """
        import tools

        ok, _ = tools.free_photos.available()
        wanted = [x for x in spec if isinstance(x, dict) and x.get("photo_query")]
        if not ok or not wanted:
            return spec

        self.log(ctx, "面ごとにフリー素材を探します（%d面）" % len(wanted))
        credits, found = [], 0
        for item in wanted:
            query = str(item.pop("photo_query", "")).strip()
            if not query:
                continue
            got = tools.free_photos.fetch(query, ctx.dir("input"), count=1,
                                          orientation="wide")
            if not got:
                continue
            found += 1
            photos.append(Path(got[0]["path"]))
            item["image"] = len(photos)          # 番号で指すので末尾の位置
            note = tools.free_photos.credit(got[0])
            if note:
                credits.append(note)
        if credits:
            ctx.state["photo_credits"] = credits
            self.log(ctx, "出典表示が要る写真が%d枚あります" % len(credits), level="warn")
        self.log(ctx, "フリー素材を %d枚 入れました" % found)
        return spec

    def _photos(self, ctx: JobContext) -> List[Path]:
        """使える素材。実写真・PDFの図版・フリー写真をまとめて集める。"""
        found: List[Path] = []
        seen = set()
        for folder in ("input", "images"):
            for path in sorted(ctx.dir(folder).glob("*")):
                if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
                    continue
                if path.name in seen:
                    continue
                seen.add(path.name)
                found.append(path)
        return found[:40]


def _build_prompt(deck, photos, ctx) -> str:
    body = "\n".join(
        "%d. %s ／ %s" % (s.get("no", i + 1), s.get("title", ""),
                          " / ".join(s.get("bullets", [])[:4]))
        for i, s in enumerate(deck.get("slides", [])))
    photo_lines = "\n".join("  %d: %s" % (i, p.name)
                            for i, p in enumerate(photos, 1)) or "  （素材なし）"
    try:
        from tools import symbols

        symbol_text = symbols.describe_for_prompt()
    except Exception:
        symbol_text = ""

    return """次の原稿を、講演スライドの**面**に割り付けてください。

【題名】{title}
【原稿】
{body}

【使える素材（番号で指定）】
{photos}

{symbols}

面の型は次の9つです。**同じ型を3枚続けない**でください。
- hero     写真を全面＋文字 … {{"type":"hero","title","sub","kicker","photo_query":"英語"}}
- cover    表紙（写真なし）… {{"type":"cover","title","lead","kicker","who"}}
- section  章扉 …………… {{"type":"section","number":"CHAPTER 1","title","lead"}}
- photos   写真を並べる …… {{"type":"photos","title","images":[番号],"captions":[..],"sub"}}
- figure   図版を1点大きく… {{"type":"figure","title","image":番号,"caption"}}
- photo    写真＋要点 …… {{"type":"photo","title","items":[..],"photo_query":"英語"}}
- numbers  数字を大きく …… {{"type":"numbers","title","items":[{{"value":"100","unit":"回超","label":"…"}}],"note"}}
- icons    記号つき3点 …… {{"type":"icons","title","items":[{{"icon":"groups","title","text"}}]}}
- quote    引用（山場）…… {{"type":"quote","text","source"}}
- closing  締め …………… {{"type":"closing","title","lines":[..]}}

【写真の探し方（重要）】
手元の素材（上の番号）に合うものが無い面には、`photo_query` に
**英語の検索語**を書いてください。こちらでフリー素材を探して入れます。
  - 具体的な被写体にする（例: japanese shopping street arcade / children eating lunch together）
  - 抽象語だけにしない（例: success, growth, teamwork は避ける）
  - 日本語では書かない（海外の写真ばかり出てしまう）
図表・グラフなど**手元の図版がある面は必ずそれを使う**（figure）。本物の方が強い。

作り方の目安:
- 1枚目は hero（写真を全面）にすると印象が変わる
- **写真か図版の面を、全体の半分以上**にする。文字だけの面が続くと聞き手が飽きる
- 数字が原稿にあれば必ず numbers の面を作る（講演で一番残るのは数字）
- 話の切り替えでは hero を挟む
- 10〜16枚に収める

JSONだけを返してください: {{"slides": [ ... ]}}""".format(
        title=deck.get("title", ""), body=body, photos=photo_lines,
        symbols=symbol_text)


def _attach_images(spec, photos):
    """番号で指定された素材を、実ファイルのパスに置き換える。

    番号が範囲外なら**その面から画像を外す**（空の枠を残さない）。
    """
    def resolve(value):
        try:
            index = int(value) - 1
        except (TypeError, ValueError):
            return None
        return str(photos[index]) if 0 <= index < len(photos) else None

    out = []
    for item in spec:
        item = dict(item)
        if "image" in item:
            path = resolve(item.get("image"))
            if path:
                item["image"] = path
            else:
                item.pop("image", None)
                if item.get("type") in ("figure", "photo"):
                    item["type"] = "bullets"
                elif item.get("type") == "hero":
                    item["type"] = "cover"        # 写真が無ければ文字だけの表紙に
        if "images" in item:
            item["images"] = [p for p in (resolve(x) for x in item["images"] or []) if p]
            if not item["images"] and item.get("type") == "photos":
                item["type"] = "bullets"
                item["items"] = item.get("items") or []
        out.append(item)
    return out


def _fallback_spec(deck, photos) -> List[Dict[str, Any]]:
    """割り付けを受け取れなかったときの最低限。空手で帰らないため。"""
    spec = [{"type": "cover", "title": deck.get("title", "資料"),
             "lead": deck.get("subtitle", "")}]
    for index, slide in enumerate(deck.get("slides", [])[:12]):
        item = {"type": "bullets", "title": slide.get("title", ""),
                "items": slide.get("bullets", [])[:4]}
        if index < len(photos):
            item["type"] = "photo"
            item["image"] = index + 1
        spec.append(item)
    spec.append({"type": "closing", "title": "ご清聴ありがとうございました",
                 "lines": []})
    return spec
