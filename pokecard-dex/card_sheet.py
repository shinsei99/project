"""カードを4枚えらんで A4 1ページのPDFにする「カードシート」。

図鑑（このフォルダ）に置いているが、**図鑑の中身は一切知らない**。
呼ぶ側が「キー・見出し・画像ファイルのパス」の3つだけ渡す約束にしてあるので、
ワンピースカード図鑑や PSAカード管理の保有カードからも同じ形で使える。

寸法の決め方（2026-08-25 オーナー確認）
    ・実物のポケモンカードは 63×88mm。**その1.15倍＝72.45×101.2mm** で並べる
    ・4枚とも同一サイズ。元にした `カードモデル.docx` は 71〜73×99〜103mm と
      1枚ずつバラついていたので、そこだけ揃えた
    ・縦横比が違う画像（トリミング済みなど）は**枠に収める（contain）**。
      枠を切って合わせる（cover）と絵柄の端が落ちるため

PDFは Pillow だけで作る（reportlab を足さない）。A4を 300dpi のキャンバスに
描いて1ページのPDFとして保存する方式。図鑑・PSA管理とも Pillow は既に入っている。
"""

from __future__ import annotations

import io
import os

import streamlit as st
from PIL import Image

# ── 用紙とカードの寸法（mm）─────────────────────────────────────────────
PAGE_W, PAGE_H = 210.0, 297.0          # A4縦
REAL_W, REAL_H = 63.0, 88.0            # ポケモンカードの実寸
SCALE = 1.15                           # 実物より15%大きく
CARD_W, CARD_H = REAL_W * SCALE, REAL_H * SCALE   # = 72.45 × 101.20mm
GAP = 4.0                              # カードとカードのすき間（2026-08-25にオーナー指示で8→4mm）
DPI = 300
SLOTS = 4                              # 2×2


def _px(mm: float) -> int:
    return int(round(mm / 25.4 * DPI))


def _positions() -> list[tuple[float, float]]:
    """4マスの左上座標（mm）。2×2をページの中央に置く。"""
    left = (PAGE_W - (CARD_W * 2 + GAP)) / 2
    top = (PAGE_H - (CARD_H * 2 + GAP)) / 2
    return [(left + (CARD_W + GAP) * c, top + (CARD_H + GAP) * r)
            for r in (0, 1) for c in (0, 1)]


# ── 選んだカードの持ち回り ───────────────────────────────────────────────
# ns（名前空間）でキーを分ける。図鑑が2本あるので、同じ session_state を
# 使うと選択が混ざる（ワンピ図鑑が `op_` で分けているのと同じ考え方）。

def _key(ns: str) -> str:
    return f"{ns}_sheet"


def picked(ns: str) -> list[dict]:
    """選んでいるカード（最大4件）。{"key","label","img"} の並び。"""
    return st.session_state.setdefault(_key(ns), [])


def is_picked(ns: str, key: str) -> bool:
    return any(p["key"] == key for p in picked(ns))


def toggle(ns: str, key: str, label: str, img) -> None:
    """選ぶ／外す。4枚を超えたら足さない（先頭を押し出したりしない）。

    img は**パスでも、パスを返す関数でもよい**。一覧は150枚ぶん同時に描くので、
    どの画像を使うかの判定（ファイルを開いて大きい方を採る等）は押した1枚だけで
    済ませたい。関数で受け取るのはそのため。
    """
    cur = picked(ns)
    for i, p in enumerate(cur):
        if p["key"] == key:
            cur.pop(i)
            return
    if len(cur) >= SLOTS:
        st.session_state[f"{ns}_sheet_full"] = True
        return
    cur.append({"key": key, "label": label,
                "img": img() if callable(img) else img})


def pick_button(ns: str, uid: str, key: str, label: str, img) -> None:
    """カード1枚ぶんの「並べる」ボタン。一覧・詳細から呼ぶ。

    uid はボタンのキーを一意にするためのもの（同じカードが一覧と詳細の
    両方に出ることがあるため。図鑑の `_album_ui` と同じ約束）。
    """
    on = is_picked(ns, key)
    st.button("✅ 並べる" if on else "🖨 並べる",
              key=f"sheet_{ns}_{uid}", width="stretch",
              type="primary" if on else "secondary",
              on_click=toggle, args=(ns, key, label, img))


# ── PDFを作る ────────────────────────────────────────────────────────────

def compose(items: list[dict]) -> Image.Image:
    """4マスぶんの画像をA4の紙に並べた1枚の画像を作る。

    items は最大4件。足りないぶんのマスは空白のままにする。
    PDFも画面プレビューもここを通す（別々に組むと見た目がずれるため）。
    """
    page = Image.new("RGB", (_px(PAGE_W), _px(PAGE_H)), "white")
    box_w, box_h = _px(CARD_W), _px(CARD_H)

    for item, (mx, my) in zip(items, _positions()):
        path = item.get("img")
        if not path or not os.path.exists(path):
            continue
        im = Image.open(path).convert("RGB")
        # 枠の大きさは4枚とも同じ。絵柄は枠に収めて中央へ置く
        scale = min(box_w / im.width, box_h / im.height)
        w, h = max(1, int(im.width * scale)), max(1, int(im.height * scale))
        im = im.resize((w, h), Image.LANCZOS)
        page.paste(im, (_px(mx) + (box_w - w) // 2, _px(my) + (box_h - h) // 2))

    return page


def build_pdf(items: list[dict]) -> bytes:
    """A4 1ページのPDFのバイト列。"""
    buf = io.BytesIO()
    compose(items).save(buf, "PDF", resolution=DPI)
    return buf.getvalue()


def preview_png(items: list[dict], width_px: int = 720) -> bytes:
    """画面で見るための縮小PNG。PDFと同じ組版を通す。

    **PDFのバイト列から作り直してはいけない。** Pillow はPDFを書けるが
    読めないので `Image.open` が UnidentifiedImageError になる
    （2026-08-25 に実際に踏んだ）。組版は compose() を共有する。
    """
    page = compose(items)
    h = int(page.height * width_px / page.width)
    buf = io.BytesIO()
    page.resize((width_px, h), Image.LANCZOS).save(buf, "PNG")
    return buf.getvalue()


# ── 画面 ─────────────────────────────────────────────────────────────────

def _move(ns: str, i: int, d: int) -> None:
    cur = picked(ns)
    j = i + d
    if 0 <= j < len(cur):
        cur[i], cur[j] = cur[j], cur[i]


def _remove(ns: str, i: int) -> None:
    cur = picked(ns)
    if 0 <= i < len(cur):
        cur.pop(i)


def _clear(ns: str) -> None:
    st.session_state[_key(ns)] = []


def render(ns: str, stamp: str = "") -> None:
    """「🖨 並べる」タブの中身。

    stamp: ダウンロードするファイル名に入れる文字（日時など）。
           呼ぶ側が渡す（この関数の中で時刻を作ると押すたびに変わる）。
    """
    cur = picked(ns)
    st.subheader("🖨 4枚を A4 に並べて PDF にする")
    st.caption(f"カード1枚 **{CARD_W:.2f} × {CARD_H:.2f} mm**"
               f"（実物 {REAL_W:.0f}×{REAL_H:.0f}mm の {SCALE:g}倍）"
               f"　｜　A4縦に 2×2　｜　4枚とも同じ大きさ")

    if st.session_state.pop(f"{ns}_sheet_full", False):
        st.warning("4枚まで。入れ替えるときは、どれかを ✕ で外してから選んでください。")

    if not cur:
        st.info("一覧や詳細の **「🖨 並べる」** を押してカードを4枚まで選んでください。")
        return

    st.write(f"**{len(cur)} / {SLOTS} 枚**")
    for i, (c, item) in enumerate(zip(st.columns(SLOTS), cur)):
        with c:
            if item.get("img") and os.path.exists(item["img"]):
                st.image(item["img"], width="stretch")
            else:
                st.markdown(
                    "<div style='aspect-ratio:63/88;background:#eceff1;"
                    "border-radius:6px;display:flex;align-items:center;"
                    "justify-content:center;color:#90a4ae;font-size:11px'>"
                    "画像なし</div>", unsafe_allow_html=True)
            st.caption(item["label"])
            b1, b2, b3 = st.columns(3)
            b1.button("◀", key=f"sheet_{ns}_left_{i}", width="stretch",
                      disabled=(i == 0), on_click=_move, args=(ns, i, -1))
            b2.button("▶", key=f"sheet_{ns}_right_{i}", width="stretch",
                      disabled=(i == len(cur) - 1), on_click=_move, args=(ns, i, 1))
            b3.button("✕", key=f"sheet_{ns}_del_{i}", width="stretch",
                      on_click=_remove, args=(ns, i))

    st.divider()
    left, right = st.columns([2, 3])
    with left:
        st.download_button("📄 PDFをダウンロード", data=build_pdf(cur),
                           file_name=f"cards-{stamp}.pdf" if stamp else "cards.pdf",
                           mime="application/pdf", type="primary", width="stretch")
        st.button("すべて外す", key=f"sheet_{ns}_clear", width="stretch",
                  on_click=_clear, args=(ns,))
        if len(cur) < SLOTS:
            st.caption(f"あと{SLOTS - len(cur)}枚ぶんは空白のまま出ます。")
    with right:
        st.image(preview_png(cur), caption="このまま印刷されます（A4縦）")
