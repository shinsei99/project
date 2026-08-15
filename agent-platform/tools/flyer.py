"""アイテム: HTML → A4のPDF / PNG（Playwright）

なぜ要るか:
  パワポは「スライド」しか作れない。チラシ・帳票・POPは紙面のレイアウトが命で、
  HTML+CSSで組んで印刷するのが一番確実に狙った形になる。
  日本語フォントもブラウザがそのまま使うので文字化けしない。
"""
from __future__ import annotations

from pathlib import Path
from typing import Tuple

NAME = "flyer"
LABEL = "チラシ/紙面ビルダー（HTML→PDF）"
DESCRIPTION = ("HTMLとCSSで組んだ紙面をA4のPDFやPNGに出力する。"
               "チラシ・POP・帳票など、スライドではないものを作るときに使う")

PAPER = {"A4": {"width": "210mm", "height": "297mm"},
         # 横向きは landscape フラグではなく**寸法をそのまま横長で渡す**。
         # フラグと寸法の両方で回すと二重に回って縦横が戻る。
         "A4_LANDSCAPE": {"width": "297mm", "height": "210mm"},
         "A3": {"width": "297mm", "height": "420mm"},
         "A3_LANDSCAPE": {"width": "420mm", "height": "297mm"},
         "B5": {"width": "182mm", "height": "257mm"}}

# 用紙のCSSピクセル寸法（96dpi換算）。ブラウザは mm をこの比率で描くので、
# PNGを撮るときのビューポートはこれに合わせないと紙面が左上に寄る。
PAPER_PX = {"A4": (794, 1123), "A3": (1123, 1587), "B5": (688, 971),
            "A3_LANDSCAPE": (1587, 1123),
            # 横向きはブラウザ側も横の画面で測らないと、折り返しが実物と変わる
            "A4_LANDSCAPE": (1123, 794)}


def available() -> Tuple[bool, str]:
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except Exception:
        return False, "playwright 未導入（pip install playwright）"
    try:
        from playwright._impl._driver import compute_driver_executable  # noqa: F401
    except Exception:
        pass
    return True, "Chromiumで紙面を出力できます"


def _wait_images(page, timeout_ms: int = 20000) -> None:
    """すべての画像の読み込み・デコードが終わるまで待つ。

    **重要**: 画像を data URI で埋め込むと、ネットワーク要求が発生しないため
    `networkidle` は即座に成立してしまう。大きい画像はまだデコード中で、
    そのまま撮ると**その画像だけが白く抜ける**（実際に外観写真が消えた）。
    """
    try:
        page.wait_for_function(
            "() => Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)",
            timeout=timeout_ms)
        page.evaluate(
            "async () => { await Promise.all(Array.from(document.images)"
            ".map(i => i.decode().catch(() => null))); }")
    except Exception:
        # 待てなくても描画は続ける（欠けるより出す方がまし）
        pass


def measure_overflow(html: str, paper: str = "A4") -> float:
    """紙面に対して中身が何倍あるかを測る。1.0以下なら収まっている。

    見た目で判断せず実測する。積みすぎた紙面は下が切れて、
    問い合わせ先や条件表が消える（実際に起きた）。
    """
    from playwright.sync_api import sync_playwright

    width, height = PAPER_PX.get(paper.upper(), PAPER_PX["A4"])
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height})
        page.set_content(html, wait_until="networkidle")
        _wait_images(page)
        # **overflow:hidden だと scrollHeight は切り詰められて溢れが検出できない。**
        # 各要素の下端を見て、本当の中身の高さを測る。
        actual = page.evaluate(
            "() => { const els = [...document.querySelectorAll('.body > *')];"
            " if (!els.length) return Math.max(document.body.scrollHeight,"
            " document.documentElement.scrollHeight);"
            " const bottom = Math.max(...els.map(e => e.getBoundingClientRect().bottom));"
            " const style = getComputedStyle(document.querySelector('.body'));"
            " return bottom + parseFloat(style.paddingBottom || 0); }")
        browser.close()
    return float(actual) / float(height)


def measure_page(html: str, paper: str = "A4"):
    """紙面の埋まり具合と、**最後の部品の高さ**を測る。

    最後の帯に余りを吸わせるとき、いまの高さが分からないと
    「どれだけ伸ばすか」を決められない。余白の付け替えだけでは高さが変わらず、
    見た目が1mmも改善しないことがあった（実測で差し引きゼロだった）。
    """
    from playwright.sync_api import sync_playwright

    width, height = PAPER_PX.get(paper.upper(), PAPER_PX["A4"])
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height})
        page.set_content(html, wait_until="networkidle")
        _wait_images(page)
        data = page.evaluate(
            "() => { const els = [...document.querySelectorAll('.body > *')];"
            " if (!els.length) return null;"
            " const last = els[els.length - 1];"
            " const bottom = Math.max(...els.map(e => e.getBoundingClientRect().bottom));"
            " const style = getComputedStyle(document.querySelector('.body'));"
            " const m = new DOMMatrixReadOnly(style.transform);"
            # offsetHeight は変形前の高さ。CSSで height を指定するときはこちらに合わせる
            " return {bottom: bottom + parseFloat(style.paddingBottom || 0),"
            "         lastHeight: last.offsetHeight, scale: m.a || 1}; }")
        browser.close()
    if not data:
        return {"ratio": 1.0, "last_height_mm": 0.0}
    return {"ratio": float(data["bottom"]) / float(height),
            # 変形前の高さをmmに直す（96dpi換算）
            "last_height_mm": float(data["lastHeight"]) / 96.0 * 25.4,
            "scale": float(data.get("scale") or 1.0)}


def fit_to_page(html: str, paper: str = "A4", min_scale: float = 0.55,
                max_scale: float = 1.45, rounds: int = 7) -> str:
    """紙面ぴったりに収める。**足りなければ広げ、溢れれば縮める。**

    下に余白が残るのは、紙面が余っているのに中身がそのままだから。
    埋めればそのぶん写真が大きくなり、紙面が強くなる。

    「1回で計算して当てる」ができない理由:
      拡大率を変えると `.body` の幅も変わり、**文字の折り返し位置が変わる**。
      高さは拡大率に比例しない。実際 ×1.015 と ×0.983 を行き来して止まらなかった。
      → **収まる倍率と溢れる倍率で挟んで、二分探索**する。数回で 0.5% 以内に入る。

    body に zoom をかけてはいけない。紙面そのものが縮んで白が出る。
    中身（.body）だけを scale し、幅を 1/scale にして紙面いっぱいを保つ。
    """
    def build(scale: float) -> str:
        if abs(scale - 1.0) < 1e-6:
            return html
        css = (".body{transform:scale(%.4f);transform-origin:top left;"
               "width:%.2f%%}" % (scale, 100.0 / scale))
        return html.replace("<style>", "<style>" + css, 1)

    def ratio_of(scale: float):
        try:
            return measure_overflow(build(scale), paper)
        except Exception:
            return None

    base = ratio_of(1.0)
    if base is None:
        return html
    if 0.995 <= base <= 1.0:
        return html

    clamp = lambda s: max(min_scale, min(max_scale, s))
    guess = clamp(1.0 / base)
    got = ratio_of(guess)
    if got is None:
        return html

    if got <= 1.0:
        lo, hi = guess, clamp(guess * 1.08)      # lo=収まる / hi=溢れる（想定）
        if lo >= max_scale:
            return build(lo)
    else:
        lo, hi = clamp(guess * 0.92), guess
        for _ in range(3):                        # lo が本当に収まるまで下げる
            r = ratio_of(lo)
            if r is not None and r <= 1.0:
                break
            lo = clamp(lo * 0.92)
        else:
            return build(min_scale)

    for _ in range(max(1, rounds)):
        mid = (lo + hi) / 2.0
        r = ratio_of(mid)
        if r is None:
            break
        if r <= 1.0:
            lo = mid
            if r >= 0.997:
                break
        else:
            hi = mid
    return build(lo)


def render(html: str, out_path, fmt: str = "pdf", paper: str = "A4",
           landscape: bool = False, scale: float = 1.0, size=None,
           png_scale: int = 2) -> Path:
    """HTML文字列を紙面ファイルにする。

    画像は file:// の絶対パス、または data: URI で埋め込むこと
    （相対パスは基準が無いため読めない）。
    """
    from playwright.sync_api import sync_playwright

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    paper_size = PAPER.get(paper.upper(), PAPER["A4"])

    with sync_playwright() as p:
        browser = p.chromium.launch()
        # png_scale で解像度を上げる（寸法はCSSピクセルのまま、画素だけ倍に）
        context = browser.new_context(device_scale_factor=max(1, int(png_scale)))
        page = context.new_page()
        page.set_content(html, wait_until="networkidle")
        _wait_images(page)
        if fmt == "png":
            if size:
                # 動画・スライド用は寸法ぴったりで撮る（full_pageだと余白が付く）
                width, height = size
            else:
                # 紙面は**用紙のCSSピクセル寸法**で撮る。ここを取り違えると
                # 紙面が画像の左上だけに寄って、右と下に巨大な余白が出る（実際に踏んだ）。
                width, height = PAPER_PX.get(paper.upper(), PAPER_PX["A4"])
                if landscape:
                    width, height = height, width
            page.set_viewport_size({"width": int(width), "height": int(height)})
            page.screenshot(path=str(out_path), full_page=False)
        else:
            page.pdf(path=str(out_path), width=paper_size["width"],
                     height=paper_size["height"],
                     landscape=landscape, print_background=True, scale=scale,
                     margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
        browser.close()
    return out_path
