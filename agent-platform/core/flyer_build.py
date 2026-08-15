"""紙面を書き出す（PDF・PNG・HTML・PowerPoint）

なぜ切り出したか:
  同じ「部品の並び → ファイル」の処理が、チラシビルダー・画面の組み直し・
  最終確認の直しの3か所に必要になった。3つに書くと必ずどれかが古くなる
  （実際、画面側だけ用紙が縦固定のままで、横の型が縦で描かれかけた）。

  ここを唯一の出口にして、**どこから直しても同じ物が出る**ようにする。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional


def render(layout: List[Dict[str, Any]], photos: List[str], out_dir,
           stem: str = "flyer", paper: str = "A4", accent: str = "",
           ink: str = "", palette: str = "") -> Dict[str, Path]:
    """部品の並びから紙面ファイル一式を作る。戻り値は作ったファイル。

    用紙は呼び出し側が型から決めて渡すこと。ここで縦に決め打ちすると、
    横の型が縦の紙で組まれて左右に分けた意味が無くなる。
    """
    import tools
    from core import blocks, palettes

    # 配色は名前で指定する（"forest" など）。色を直接渡した場合はそれを優先する
    theme = palettes.colors(palette or palettes.DEFAULT)
    accent = accent or theme["accent"]
    ink = ink or theme["ink"]

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    html = blocks.render_page(layout, photos=photos, accent=accent, ink=ink,
                              padding="0mm 12mm", paper=paper)
    html = tools.flyer.fit_to_page(html, paper=paper)
    html = _absorb_gap(html, layout, paper)

    made = {}
    made["html"] = out_dir / ("%s.html" % stem)
    made["html"].write_text(html, encoding="utf-8")
    made["pdf"] = out_dir / ("%s.pdf" % stem)
    tools.flyer.render(html, made["pdf"], fmt="pdf", paper=paper)
    made["png"] = out_dir / ("%s.png" % stem)
    tools.flyer.render(html, made["png"], fmt="png", paper=paper)

    # **編集用のPowerPointは出さない。**
    # 紙面をPowerPointの図形に落とすと、位置・級数・余白がどうしても崩れ、
    # 「これなら無い方がいい」出来にしかならなかった。
    # 文字を直したいときは、成果物タブの「紙面を組み直す」で打ち変えて
    # 数秒で作り直す。そちらの方が速く、崩れようがない。
    return made


BAR_BLOCKS = ("contact_bar", "company_bar", "cta")


def _absorb_gap(html: str, layout, paper: str) -> str:
    """紙面の下に残った隙間を、**最後の帯に吸わせる**。

    合わせ込みは拡大するほど段が狭くなり、文字の折り返しが増えて背が伸びる。
    そのため「ちょうど1.0」まで拡大できず、数%（実測4.4%＝13mm）残ることがある。

    その隙間は帯と同じ色で塗ってあるので白くはならないが、
    **帯の下に何も無い面ができて「余った」ように見える**。
    隙間ぶんを帯の上下の余白にすると、帯が厚くなって中身が中央に来るので、
    紙面が最後まで詰まって見える。文字の大きさは変えないので崩れない。
    """
    import tools

    last = (layout or [])[-1] if layout else None
    if not isinstance(last, dict) or str(last.get("block")) not in BAR_BLOCKS:
        return html
    try:
        measured = tools.flyer.measure_page(html, paper)
    except Exception:
        return html
    ratio = measured["ratio"]
    if ratio >= 0.985 or ratio < 0.80:
        return html
    height_mm = 210.0 if str(paper).upper().endswith("LANDSCAPE") else 297.0
    gap = min((1.0 - ratio) * height_mm, 32.0)
    # **高さを直接決める。** 上下の余白を付け替えるだけでは高さが変わらず、
    # 見た目が1mmも改善しなかった（下の余白を減らして上に足していた）。
    # 帯を高くして、中身は上下中央に置く（電話番号が下端に寄らないように）。
    # 紙面の隙間（mm）は縮小後の寸法。CSSは縮小前の単位なので割り戻す
    scale = max(measured.get("scale") or 1.0, 0.2)
    target = measured["last_height_mm"] + gap / scale
    css = (".body > *:last-child{height:%.1fmm !important;box-sizing:border-box;"
           "display:flex;flex-direction:column;justify-content:center}" % target)
    return html.replace("<style>", "<style>" + css, 1)


def write_all(ctx, layout: List[Dict[str, Any]], photos: List[str],
              paper: str = "A4", palette: Optional[str] = None) -> Dict[str, Path]:
    """ジョブの中で紙面を作り直す（既にあるファイルを置き換える）。

    ファイル名は最初に作ったものに合わせる。名前が変わると、
    受け取った人が「どれが最新か」分からなくなる。
    """
    slides = ctx.dir("slides")
    existing = sorted(slides.glob("*.pdf"))
    stem = existing[0].stem if existing else "flyer"
    made = render(layout, photos, slides, stem=stem, paper=paper,
                  palette=palette or ctx.state.get("flyer_palette") or "")
    ctx.state["flyer"] = ctx.rel(made["pdf"])
    return made
