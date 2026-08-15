"""加東 貸家チラシメーカー — 屋外ホルダー（インフォパックA4 #31010）に入れるA4を作る。

看板本体には賃料を刷らず、変わる情報はこの紙に逃がす、という運用の紙側。
写真はDropboxの撮影フォルダ（CR2も可）、間取り図はGoogleドライブの案件フォルダから拾う。
"""
from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import streamlit as st
from PIL import Image

import engine
import flyer
import tracking
from properties import PROPERTIES, list_madori, list_photos

APP_DIR = Path(__file__).parent
DATA = APP_DIR / "data"
CACHE = DATA / "thumbs"
OVERRIDES = DATA / "overrides.json"

st.set_page_config(page_title="加東 貸家チラシメーカー", page_icon="🏡", layout="wide")


def load_overrides() -> dict:
    if OVERRIDES.exists():
        return json.loads(OVERRIDES.read_text())
    return {}


def save_overrides(d: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    OVERRIDES.write_text(json.dumps(d, ensure_ascii=False, indent=1))


@st.cache_data(show_spinner=False)
def thumb(path: str, mtime: float, px: int = 320) -> bytes:
    """一覧用サムネ。CR2はsips変換が重いので必ずキャッシュに載せる。"""
    CACHE.mkdir(parents=True, exist_ok=True)
    im = flyer.load_image(path)
    im.thumbnail((px, px))
    buf = BytesIO()
    im.save(buf, "JPEG", quality=80)
    return buf.getvalue()


ov = load_overrides()

# ── サイドバー：物件と素材の選択
st.sidebar.title("🏡 加東 貸家チラシ")
name = st.sidebar.selectbox("物件", list(PROPERTIES.keys()))
base = PROPERTIES[name]
cur = {**base, **ov.get(name, {})}

photos = list_photos(base)
madoris = list_madori(base)
st.sidebar.caption(f"写真 {len(photos)}点／間取り図 {len(madoris)}点")

if not photos:
    st.sidebar.error(
        "写真が見つかりません。DropboxまたはGoogleドライブの実体が"
        "Macに降りていない可能性があります。"
    )

st.sidebar.divider()
st.sidebar.subheader("紙面の型")

# 型はマルチプロダクション（../agent-platform）から読む。
# 向こうが無いPCでも、これまでの型だけで従来どおり動く。
PIL_TEMPLATE = {"id": "pil", "name": "これまでの型", "orientation": "portrait",
                "summary": "外観1枚＋室内3枚。橙の見出し帯と濃紺の賃料帯。従来のA4（300dpiの画像PDF）",
                "shape": "見出し帯／大写真／名前・賃料帯／室内3枚／タグ／説明／条件表｜間取り／連絡先"}
engine_ok, engine_note = engine.available()
choices = [PIL_TEMPLATE]
if engine_ok:
    try:
        choices += engine.templates()
    except Exception as exc:
        engine_ok, engine_note = False, "型を読めませんでした：%s" % exc


def _label(t: dict) -> str:
    mark = "▭ " if t["orientation"] == "landscape" else ""
    return "%s%s" % (mark, t["name"])


tpl = st.sidebar.selectbox("型", choices, format_func=_label,
                           help="▭ は A4横。型ごとに並べ方が決まっています")
st.sidebar.caption(tpl["summary"])
if not engine_ok:
    st.sidebar.warning("増やした型は使えません：%s" % engine_note)

palette_id = engine.KATO_PALETTE["id"]
if tpl["id"] != "pil":
    pals = engine.palettes()
    pal = st.sidebar.selectbox(
        "配色", pals, format_func=lambda p: p["name"],
        help="既定は看板と同じ橙×濃紺。現地で検証した色なので、通常は変えないこと",
    )
    palette_id = pal["id"]
    st.sidebar.markdown(
        '<div style="display:flex;gap:6px;align-items:center">'
        '<span style="width:22px;height:14px;background:%s;border-radius:3px"></span>'
        '<span style="width:22px;height:14px;background:%s;border-radius:3px"></span>'
        '<span style="font-size:12px;color:#666">%s / %s</span></div>'
        % (pal["accent"], pal["ink"], pal["accent"], pal["ink"]),
        unsafe_allow_html=True,
    )
    need = tpl.get("photos_min", 0)
    if need:
        st.sidebar.caption("この型は写真%d枚から。並び：%s" % (need, tpl["shape"]))

st.sidebar.divider()
st.sidebar.subheader("QRの飛び先")
# チラシのQRはサイトのトップへ。集計では「チラシ」として数える。
_qr_default = tracking.from_url("doc")
qr_url = st.sidebar.text_input("URL", _qr_default)
if qr_url == _qr_default:
    st.sidebar.caption("サイトのトップに飛びます。集計では「チラシ」として数えます。")
else:
    st.sidebar.caption(f"既定に戻すには → {_qr_default}")
qr_label = st.sidebar.text_input("QRの説明", cur.get("qr_label", "写真と間取りをもっと見る"))
tel = st.sidebar.text_input("電話番号", cur.get("tel", "06-6935-7267"))

st.sidebar.divider()
if st.sidebar.button("この物件の編集内容を保存", use_container_width=True):
    ov[name] = st.session_state.get("_edited", {})
    save_overrides(ov)
    st.sidebar.success("保存しました")

# ── 本文：編集
left, right = st.columns([1, 1.15], gap="large")

with left:
    st.subheader("文言")
    kicker = st.text_input("上の小さい文字", cur["kicker"])
    catch = st.text_area("キャッチ（2行まで）", cur["catch"], height=90)
    title = st.text_input("物件名", cur["title"])
    c1, c2 = st.columns([1, 2])
    rent = c1.text_input("賃料", cur["rent"])
    rent_note = c2.text_input("賃料の補足", cur["rent_note"])
    tags = st.text_input("特徴タグ（読点区切り）", "、".join(cur.get("tags", [])))
    body = st.text_area("説明文", cur.get("body", ""), height=100)

    st.subheader("スペック表")
    spec_txt = st.text_area(
        "「項目：値」を1行ずつ",
        "\n".join(f"{k}：{v}" for k, v in cur.get("specs", [])),
        height=200,
    )

    st.subheader("写真を選ぶ")
    # 型によって使う枚数が違う（写真たっぷりは6枚から）。既定を型に合わせておく
    want = max(4, int(tpl.get("photos_min") or 0))
    st.caption("1枚目に選んだものが大きく入り、続きが下段に並びます。この型は%d枚から。" % want
               if tpl["id"] != "pil" else
               "1枚目に選んだものが大きく入り、次の3枚が下段に並びます。")
    names = [p.name for p in photos]
    picked = st.multiselect("使う写真（選んだ順）", names, default=names[:want])
    if picked:
        cols = st.columns(min(4, len(picked)))
        for i, n in enumerate(picked[:4]):
            p = photos[names.index(n)]
            cols[i].image(thumb(str(p), p.stat().st_mtime), caption=f"{i + 1}枚目")

    madori_name = st.selectbox(
        "間取り図", ["（なし）"] + [p.name for p in madoris],
        index=1 if madoris else 0,
    )

# ── 組版
specs: list[tuple[str, str]] = []
for line in spec_txt.splitlines():
    for sep in ("：", ":"):
        if sep in line:
            k, v = line.split(sep, 1)
            specs.append((k.strip(), v.strip()))
            break

sel = [photos[names.index(n)] for n in picked]
fl = flyer.Flyer(
    kicker=kicker,
    catch=catch,
    title=title,
    rent=rent,
    rent_note=rent_note,
    specs=specs,
    tags=[t.strip() for t in tags.replace(",", "、").split("、") if t.strip()],
    body=body,
    tel=tel,
    qr_url=qr_url,
    qr_label=qr_label,
    main_photo=str(sel[0]) if sel else None,
    # 増やした型は6枚まで使う。これまでの型は先頭3枚しか見ないので渡しても影響しない
    sub_photos=[str(p) for p in sel[1:7]],
    madori=str(madoris[[p.name for p in madoris].index(madori_name)])
    if madori_name != "（なし）" else None,
)

st.session_state["_edited"] = {
    "kicker": kicker, "catch": catch, "title": title, "rent": rent,
    "rent_note": rent_note, "tags": fl.tags, "body": body, "specs": specs,
    "qr_url": qr_url, "qr_label": qr_label, "tel": tel,
}

PAPER_LABEL = {"portrait": "A4縦", "landscape": "A4横"}
WEATHER_NOTE = ("屋外ホルダーに入れるなら**耐水紙（ユポ等）**で。"
                "普通紙は雨と日焼けで数週間で読めなくなります。")


def _stem() -> str:
    return "%s_%s" % (title.replace(" ", "_") or "flyer", tpl["id"])


with right:
    if tpl["id"] == "pil":
        st.subheader("仕上がり（A4・300dpi）")
        try:
            img = flyer.render(fl)
        except Exception as e:  # 写真が降りていない等はここで出る
            st.error(f"描画できませんでした：{type(e).__name__} {e}")
            st.stop()

        prev = img.copy()
        prev.thumbnail((900, 1300))
        st.image(prev)

        pdf = BytesIO()
        flyer.save_pdf(img, pdf)
        st.download_button(
            "📄 A4 PDFをダウンロード",
            pdf.getvalue(),
            file_name=f"{title.replace(' ', '_')}.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary",
        )
        png = BytesIO()
        img.save(png, "PNG")
        st.download_button("PNGでも保存", png.getvalue(),
                           file_name=f"{title.replace(' ', '_')}.png",
                           mime="image/png", use_container_width=True)
        st.caption(WEATHER_NOTE)
    else:
        st.subheader("仕上がり（%s・%s）" % (tpl["name"], PAPER_LABEL.get(tpl["orientation"], "A4縦")))
        # 描くたびに写真の下ごしらえとブラウザ組版が走るので、**入力のたびには描かない**。
        # 文言を打つたびに10〜40秒待たされると編集にならない。
        st.caption("文言や写真を変えたら、下のボタンでもう一度作り直してください。")
        if st.button("🖨 この型で作る", use_container_width=True, type="primary"):
            with st.spinner("紙面を組んでいます（写真の下ごしらえ込みで10〜40秒）"):
                try:
                    made = engine.render(fl, tpl["id"], palette_id, DATA / "render",
                                         stem=_stem())
                    st.session_state["_made"] = {k: str(v) for k, v in made.items()}
                    st.session_state["_made_for"] = (tpl["id"], palette_id, title)
                except Exception as e:
                    st.session_state.pop("_made", None)
                    st.error(f"作れませんでした：{type(e).__name__} {e}")

        made = st.session_state.get("_made")
        if made and Path(made.get("png", "")).exists():
            if st.session_state.get("_made_for") != (tpl["id"], palette_id, title):
                st.info("型・配色・物件名を変えました。作り直すと反映されます（下は前回の紙面）。")
            st.image(made["png"])
            pdf_path = Path(made["pdf"])
            st.download_button(
                "📄 A4 PDFをダウンロード（ベクター）", pdf_path.read_bytes(),
                file_name=pdf_path.name, mime="application/pdf",
                use_container_width=True, type="primary",
            )
            png_path = Path(made["png"])
            st.download_button("PNGでも保存", png_path.read_bytes(),
                               file_name=png_path.name, mime="image/png",
                               use_container_width=True)
            st.caption(WEATHER_NOTE)
        elif not made:
            st.info("ボタンを押すと、この型で1枚組みます。")
