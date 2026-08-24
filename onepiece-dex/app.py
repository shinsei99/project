"""
ワンピースカード図鑑 — Streamlit UI

**データは公式サイト（onepiece-cardgame.com）だけで足りている。**
ポケカ図鑑は公式がレアリティを非公開なので DMMマイカ・TCGdex・learn-book の
4ソースを継ぎ接ぎしたが、ワンピはカードリストがカード番号・レアリティ・種類・
色・コスト・パワー・カウンター・属性・特徴・テキスト・入手情報・画像を
全部1か所に持っている。組み立ては build_dex.py（dex / dex_series テーブル）。

  🔎 さがす      … カード名・カード番号／色・種類・レアリティ・特徴で絞る
  📦 シリーズ     … ブースターパック・スタートデッキ等から収録カードへ
  👑 リーダー     … リーダーカードだけを色別に。デッキを考える起点がここになる

  ./run.sh → http://127.0.0.1:8537

⚠️ 自分専用・localhost バインド。カード画像の著作権は
   ©尾田栄一郎/集英社・フジテレビ・東映アニメーション ©BANDAI に帰属するため、
   社内LANにも公開しない（ポケカ図鑑と同じ扱い）。
"""

from __future__ import annotations

import os
import sqlite3

import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "data", "cards.db")

PER_PAGE = 150       # 1ページの枚数。サムネイル15KB×150＝約2.2MB

# 公式が使っている並び（赤→緑→青→紫→黒→黄）。絞り込みもこの順で出す
COLORS = ["赤", "緑", "青", "紫", "黒", "黄"]
COLOR_HEX = {"赤": "#d0342c", "緑": "#2e8b57", "青": "#1f6fb2",
             "紫": "#7b4fa8", "黒": "#444444", "黄": "#d4a017"}
CATEGORIES = ["LEADER", "CHARACTER", "EVENT", "STAGE"]
CATEGORY_JA = {"LEADER": "リーダー", "CHARACTER": "キャラクター",
               "EVENT": "イベント", "STAGE": "ステージ", "DON!!": "ドン!!"}
# 属性（打・斬・特・知・射）。カードの右上に刷られている記号
ATTRIBUTES = ["打", "斬", "特", "知", "射"]



# ── 名前空間 ─────────────────────────────────────────────────────────────────
# session_state とウィジェットキーは**必ずこの接頭辞を通す**。
# PSAカード管理（8527）はポケカ図鑑とワンピ図鑑の**両方**を同じ Streamlit
# セッションの中に読み込むので、素の `tab` `detail` `pack` `other` を使うと
# 2本が同じ入れ物を取り合う。実害は2つあった:
#   ・タブ構成が違う（ポケカ3つ／ワンピ4つ）ので、「👑 リーダー」を選んだまま
#     ポケカ図鑑へ移ると、選択肢に無い値が残って st.radio が例外になる
#   ・詳細を開いたまま行き来すると、相手のカードキーで自分のDBを引くことになる
NS = "op_"


def _sk(name: str) -> str:
    """session_state / ウィジェットのキー名にこの図鑑の名前空間を付ける。"""
    return NS + name


def _p(path):
    """DBの画像パスは `data/img/…` の相対。cwd に依らずこのフォルダ基準で開く。

    単独起動（run.sh が cd してから起動する）では気づかないが、PSAカード管理
    から呼ぶと cwd が向こうになり、そのままでは画像が1枚も出ない。
    """
    if not path:
        return None
    return path if os.path.isabs(path) else os.path.join(HERE, path)


# 図鑑のカードを「欲しいカード」としてアルバムへ入れるための差し込み口。
# PSAカード管理が render(album_ui=…) で渡す。単独起動では None＝何も出ない。
# 図鑑側からアルバムの実装（albums.json・cert番号）を知らずに済ませるための境界。
_ALBUM_UI = None


def _album_ui(row, uid: str) -> None:
    if _ALBUM_UI is not None:
        _ALBUM_UI(row, uid)


@st.cache_resource
def conn():
    c = sqlite3.connect(DB, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def has_dex() -> bool:
    return bool(conn().execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='dex'").fetchone())


def available() -> bool:
    return os.path.exists(DB) and has_dex()


def db_stamp() -> float:
    """DBの更新時刻。キャッシュの鍵にして、build_dex.py のあと自動で読み直す。"""
    try:
        return os.path.getmtime(DB)
    except OSError:
        return 0.0


@st.cache_data(show_spinner=False)
def stats(_stamp: float = 0.0):
    q = lambda s: conn().execute(s).fetchone()[0]
    return {"cards": q("SELECT COUNT(*) FROM dex"),
            "series": q("SELECT COUNT(*) FROM dex_series"),
            "images": q("SELECT COUNT(*) FROM dex WHERE img IS NOT NULL"),
            "leaders": q("SELECT COUNT(*) FROM dex WHERE category='LEADER'")}


@st.cache_data(show_spinner=False)
def series_list(ptype: str | None = None, _stamp: float = 0.0):
    """シリーズ一覧。並びは**発売日の新しい順**（公式の商品ラインナップ由来）。

    発売日が判らないシリーズ（ST-02〜04・ST-16〜20 は現行の商品ラインナップから
    外れていて載っていない）は末尾に寄せ、公式サイトの並び順で続ける。
    """
    sql = "SELECT * FROM dex_series"
    args: tuple = ()
    if ptype:
        sql += " WHERE ptype = ?"
        args = (ptype,)
    sql += " ORDER BY (release IS NULL), release DESC, (sort IS NULL), sort"
    return [dict(r) for r in conn().execute(sql, args)]


@st.cache_data(show_spinner=False)
def rarities_in(series_id: str | None = None, _stamp: float = 0.0):
    """存在するレアリティを弱い順に、枚数つきで返す。"""
    if series_id:
        sql = ("SELECT d.rarity, MIN(d.rarity_i), MAX(d.rarity_note), COUNT(*) "
               "FROM dex d JOIN card_series cs ON cs.key=d.key "
               "WHERE cs.series_id=? GROUP BY d.rarity ORDER BY MIN(d.rarity_i)")
        args = (series_id,)
    else:
        sql = ("SELECT rarity, MIN(rarity_i), MAX(rarity_note), COUNT(*) FROM dex "
               "GROUP BY rarity ORDER BY MIN(rarity_i)")
        args = ()
    return [(r[0], r[2], r[3]) for r in conn().execute(sql, args) if r[0]]


@st.cache_data(show_spinner=False)
def features_all(_stamp: float = 0.0):
    """特徴（麦わらの一味・四皇…）を、付いているカードの多い順に。"""
    return [(r[0], r[1]) for r in conn().execute(
        "SELECT feature, COUNT(*) n FROM dex_features GROUP BY feature "
        "ORDER BY n DESC, feature")]


def rarity_option(r: str, note: str | None, n: int) -> str:
    return f"{r} {note}（{n}枚）" if note else f"{r}（{n}枚）"


def _pick(key, value):
    """ボタンのコールバック。再実行の前に session_state を書き換える。

    st.rerun() でやると表示中のタブが先頭に戻る（ポケカ図鑑で踏んだ）。
    カード詳細は他より優先して全画面に出すので、別の画面へ移るときは詳細を閉じる。

    key は `detail` `pack` `other` のような素の名前で渡してよい（ここで `_sk()` を通す）。
    """
    st.session_state[_sk(key)] = value
    if key != "detail" and value is not None:
        st.session_state[_sk("detail")] = None


def _picked(key, default=None):
    """`_pick()` で置いた値を読む。"""
    return st.session_state.get(_sk(key), default)


def card_no_label(row) -> str:
    """カード1枚の短い見出し（`OP01-001` / パラレルは `OP01-001 P1`）。

    PSAカード管理がアルバムのキャプションに使う。ポケカ図鑑と同名・同じ役割。
    """
    code = row["code"] or row["key"]
    return f"{code} {row['variant']}" if row["variant"] else code


def thumb_of(row):
    """一覧用の180pxサムネイル。無ければ原寸で代用する。

    公式の原寸PNGは1枚200〜300KB。169枚のパックをそのまま並べると40MBを
    ブラウザへ送ることになる。一覧はサムネイル（15KB前後）を使う。
    """
    for col in ("thumb", "img"):
        p = _p(row[col])
        if p and os.path.exists(p):
            return p
    return None


def image_of(row):
    """詳細用の原寸（公式の600×838 PNG）。無ければサムネイルで代用する。"""
    for col in ("img", "thumb"):
        p = _p(row[col])
        if p and os.path.exists(p):
            return p
    return None


def color_chip(color: str | None) -> str:
    """多色（赤/緑）も1色ずつ丸で出す。色名だけだと一覧で目が滑るため。"""
    if not color:
        return ""
    out = []
    for c in color.split("/"):
        c = c.strip()
        hexc = COLOR_HEX.get(c, "#999")
        out.append(f"<span style='display:inline-block;width:10px;height:10px;"
                   f"border-radius:50%;background:{hexc};margin-right:3px'></span>")
    return "".join(out)


# ── カード詳細 ───────────────────────────────────────────────────────────────

def show_detail(card):
    col_img, col_txt = st.columns([1, 1.4])
    with col_img:
        u = image_of(card)
        if u:
            st.image(u, width="stretch")
            # 透かしを不具合と勘違いさせないため、出どころを書いておく。
            # 公式が配っている画像がこれで、透かしの無い版は公開されていない
            st.caption("公式サイトの画像（600×838）。"
                       "**「SAMPLE」の透かしは公式の画像に元から入っている**")
        else:
            st.info("このカードの画像は未収録です")
        _album_ui(card, f"detail_{card['key']}")

    with col_txt:
        st.markdown(f"### {card['name']}")
        head = [f"`{card['key']}`"]
        if card["rarity"]:
            r = card["rarity"]
            # スーパーパラレルは公式の区分ではないので、元のレアリティも併記する
            if card["rarity_base"] and card["rarity_base"] != r:
                r += f"（{card['rarity_base']}）"
            if card["rarity_note"]:
                r += f"　{card['rarity_note']}"
            head.append(r)
        if card["category_ja"]:
            head.append(card["category_ja"])
        st.caption("　/　".join(head))
        if card["variant"]:
            st.caption(f"別イラスト（{card['variant']}）")

        # コストとパワーは、ワンピでは真っ先に見る数字なので上に大きく置く。
        # LEADER だけ「コスト」ではなく「ライフ」（公式の見出しに従う）
        m = st.columns(4)
        m[0].metric(card["cost_label"] or "コスト",
                    "―" if card["cost"] is None else card["cost"])
        m[1].metric("パワー", "―" if card["power"] is None else f"{card['power']:,}")
        m[2].metric("カウンター",
                    "―" if card["counter"] is None else f"{card['counter']:,}")
        m[3].metric("属性", card["attribute"] or "―")

        st.markdown(f"**色** {color_chip(card['color'])} {card['color'] or '―'}"
                    f"　　**ブロック** {card['block'] or '―'}",
                    unsafe_allow_html=True)
        if card["feature"]:
            st.write("**特徴**　" + "　".join(f"`{f}`" for f in card["feature"].split("/")))
        if card["text"]:
            st.markdown("**テキスト**")
            st.info(card["text"])
        if card["get_info"]:
            st.caption(f"入手情報: {card['get_info']}")
        if card["rarity_short"]:
            # 公式が持っていない区分なので、どこから採った情報かを書いておく
            st.caption("※スーパーパラレル系のレアリティは公式サイトが区分を"
                       "公開していないため、外部の一覧（tier-one-onepiece.jp）を"
                       "典拠に画像照合で補ったもの")

        # 同じカード番号の別イラスト（パラレル）へ飛べるようにする。
        # ワンピはパラレルが多く、同じカードを絵違いで何枚も持つのが普通なため
        same = conn().execute(
            "SELECT key, variant, rarity FROM dex WHERE code=? AND key<>? "
            "ORDER BY variant", (card["code"], card["key"])).fetchall()
        if same:
            st.markdown("**同じカードの別イラスト**")
            for c, o in zip(st.columns(min(len(same), 6)), same):
                c.button(f"{o['variant'] or '通常'}　{o['rarity'] or ''}",
                         key=_sk(f"var_{o['key']}"), width="stretch",
                         on_click=_pick, args=("detail", o["key"]))


def show_cards(rows, cols=6, key_prefix=""):
    """サムネイル一覧。押すと詳細をその場に開く。

    key_prefix はボタンのキーを一意にするために要る（同じカードが
    さがすとシリーズの両方に出ると StreamlitDuplicateElementKey になる）。
    """
    for i in range(0, len(rows), cols):
        for c, row in zip(st.columns(cols), rows[i:i + cols]):
            with c:
                u = thumb_of(row)
                if u:
                    st.image(u, width="stretch")
                else:
                    st.markdown(
                        "<div style='aspect-ratio:5/7;background:#eceff1;"
                        "border-radius:6px;display:flex;align-items:center;"
                        "justify-content:center;color:#90a4ae;font-size:11px'>"
                        "画像なし</div>", unsafe_allow_html=True)
                st.markdown(
                    f"<div style='font-size:11px;line-height:1.5;color:#555'>"
                    f"{color_chip(row['color'])}{row['code']}"
                    f"{'  ' + row['variant'] if row['variant'] else ''}<br>"
                    f"{row['name'][:11]}"
                    f"{'  <b>' + (row['rarity_short'] or row['rarity']) + '</b>' if row['rarity'] else ''}"
                    f"</div>", unsafe_allow_html=True)
                st.button("詳細", key=_sk(f"d_{key_prefix}_{row['key']}"),
                          width="stretch", on_click=_pick,
                          args=("detail", row["key"]))
                _album_ui(row, f"{key_prefix}_{row['key']}")


def paginate(n_hit: int, key: str):
    """ページ送り。選ばれたページ番号を返す。上限で打ち切ると先が見られない。"""
    total = (n_hit + PER_PAGE - 1) // PER_PAGE
    if total <= 1:
        st.write(f"**{n_hit:,}枚**")
        return 1
    c1, c2 = st.columns([2, 3])
    c1.write(f"**{n_hit:,}枚**")
    page = c2.slider("ページ", 1, total, 1, key=_sk(key), label_visibility="collapsed")
    st.caption(f"{page} / {total} ページ（{(page-1)*PER_PAGE+1:,}〜"
               f"{min(page*PER_PAGE, n_hit):,}枚目）")
    return page


def query(where, args, order, page):
    n = conn().execute("SELECT COUNT(*) FROM dex d WHERE " + where, args).fetchone()[0]
    rows = conn().execute(
        f"SELECT d.* FROM dex d WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?",
        args + [PER_PAGE, (page - 1) * PER_PAGE]).fetchall()
    return n, rows


def filter_bar(prefix: str, series_id: str | None = None):
    """色・種類・レアリティの絞り込み。さがすとシリーズで同じものを使う。"""
    c1, c2, c3 = st.columns([1.2, 1.2, 1.6])
    colors = c1.multiselect("色", COLORS, key=_sk(f"{prefix}_col"), placeholder="色")
    cats = c2.multiselect("種類", CATEGORIES, key=_sk(f"{prefix}_cat"),
                          format_func=lambda c: CATEGORY_JA.get(c, c),
                          placeholder="種類")
    rar = rarities_in(series_id, db_stamp())
    note = {r: (n, c) for r, n, c in rar}
    rsel = c3.multiselect("レアリティ", [r for r, _, _ in rar], key=_sk(f"{prefix}_rar"),
                          format_func=lambda r: rarity_option(r, *note[r]),
                          placeholder="レアリティ")
    where, args = [], []
    if colors:
        # 多色（赤/緑）は dex_colors に色ごとに入っている。「赤」で多色も出る
        where.append("d.key IN (SELECT key FROM dex_colors WHERE color IN (%s))"
                     % ",".join("?" * len(colors)))
        args += colors
    if cats:
        where.append("d.category IN (%s)" % ",".join("?" * len(cats)))
        args += cats
    if rsel:
        where.append("d.rarity IN (%s)" % ",".join("?" * len(rsel)))
        args += rsel
    return where, args


def fetch_card(key):
    return conn().execute("SELECT * FROM dex WHERE key = ?", (key,)).fetchone()


# ── 画面 ─────────────────────────────────────────────────────────────────────

def show_series_cards(series_id, back_key: str = "series"):
    s = conn().execute("SELECT * FROM dex_series WHERE series_id=?",
                       (series_id,)).fetchone()
    st.button("← 一覧にもどる", key=_sk(f"back_{back_key}"),
              on_click=_pick, args=(back_key, None))
    if not s:
        st.warning("このシリーズが見つかりません")
        return
    c1, c2 = st.columns([1, 5])
    cover = _p(s["cover"])
    if cover and os.path.exists(cover):
        c1.image(cover, width="stretch")
        if s["cover_src"] == "card":
            c1.caption("※パッケージ画像が無いためリーダーの絵")
    c2.markdown(f"### {s['name']}")
    bits = [s["ptype"] or "分類なし",
            (s["release"] or "発売日不明").replace("-", "."),
            f"{s['cards']}枚（画像 {s['images']}枚）"]
    if s["price"]:
        bits.append(s["price"])
    bits.append(f"`{s['code'] or s['series_id']}`")
    c2.caption("　｜　".join(bits))
    with c2:
        where, args = filter_bar(f"sr{back_key}", series_id)

    where = ["d.key IN (SELECT key FROM card_series WHERE series_id=?)"] + where
    args = [series_id] + args
    cond = " AND ".join(where)
    n = conn().execute("SELECT COUNT(*) FROM dex d WHERE " + cond, args).fetchone()[0]
    page = paginate(n, f"pg_s_{back_key}_{series_id}")
    _, rows = query(cond, args,
                    "(d.card_no IS NULL), d.card_no, d.variant", page)
    show_cards(rows, key_prefix=f"{back_key}{series_id}")


def cover_of(row):
    """表紙。**商品パッケージ画像**があればそれ、無ければリーダーの絵。"""
    p = _p(row.get("cover"))
    return p if p and os.path.exists(p) else None


def show_product_grid(ptype: str, key_prefix: str, on_pick_key: str):
    """商品の表紙をタイル状に並べる。押すと収録カードへ。

    ポケカ図鑑と同じ入口の作り。分類は**公式の商品ラインナップ**（products）の
    カテゴリに従う（ブースター＝拡張パック / デッキ＝構築デッキ / その他）。
    """
    items = series_list(ptype, db_stamp())
    n_pkg = sum(1 for i in items if i["cover_src"] == "product")
    note = f"{len(items)}件　発売日の新しい順"
    if n_pkg < len(items):
        note += (f"　｜　うち{len(items) - n_pkg}件はパッケージ画像が無く"
                 "リーダーの絵で代用（現行の商品ラインナップから外れているため）")
    st.caption(note)
    cols = 6
    for i in range(0, len(items), cols):
        for j, (c, it) in enumerate(zip(st.columns(cols), items[i:i + cols])):
            with c:
                cover = cover_of(it)
                if cover:
                    st.image(cover, width="stretch")
                else:
                    st.markdown(
                        "<div style='aspect-ratio:1/1;background:#eceff1;"
                        "border-radius:6px;display:flex;align-items:center;"
                        "justify-content:center;color:#90a4ae;font-size:11px'>"
                        "表紙なし</div>", unsafe_allow_html=True)
                # 16文字で切ると PRB-01 と PRB-02 がどちらも
                # 「ONE PIECE CARD T」になって見分けがつかなかった
                st.markdown(
                    f"<div style='font-size:11px;line-height:1.4;color:#555'>"
                    f"<b>{it['short'][:30]}</b><br>"
                    f"{(it['release'] or '発売日不明').replace('-', '.')}　"
                    f"{it['cards']}枚<br>"
                    f"<span style='color:#90a4ae'>{it['code'] or ''}</span></div>",
                    unsafe_allow_html=True)
                st.button("収録カード", key=_sk(f"{key_prefix}_{i}_{j}"), width="stretch",
                          on_click=_pick, args=(on_pick_key, it["series_id"]))


def show_leaders():
    """リーダーだけを色別に。ワンピはリーダーを決めてからデッキを組むので、
    「その色のリーダーを見渡す」が独立した入口として要る。"""
    c1, c2 = st.columns([1.2, 3])
    color = c1.selectbox("色", ["すべて"] + COLORS, key=_sk("ld_color"))
    kw = c2.text_input("リーダー名で絞る", key=_sk("ld_kw"), placeholder="例: ルフィ")
    where = ["d.category = 'LEADER'"]
    args: list = []
    if color != "すべて":
        where.append("d.key IN (SELECT key FROM dex_colors WHERE color = ?)")
        args.append(color)
    if kw.strip():
        where.append("d.name LIKE ?")
        args.append(f"%{kw.strip()}%")
    cond = " AND ".join(where)
    n = conn().execute("SELECT COUNT(*) FROM dex d WHERE " + cond, args).fetchone()[0]
    page = paginate(n, "pg_leader")
    _, rows = query(cond, args, "d.set_code DESC, d.card_no, d.variant", page)
    show_cards(rows, key_prefix="ld")


def main():
    st.set_page_config(page_title="ワンピースカード図鑑", page_icon="🏴‍☠️",
                       layout="wide")
    render()


def render(album_ui=None, title: str = "🏴‍☠️ ワンピースカード図鑑"):
    """図鑑の画面。単独起動と PSAカード管理の両方から呼ばれる。

    set_page_config はここでは呼ばない（呼び出し側が既に済ませているため。
    2回呼ぶと StreamlitAPIException になる）。

    album_ui: カード1枚ぶんの「欲しいカード」ボタンを描く関数 (row, uid) -> None。
              PSAカード管理から渡される。単独起動では None＝何も足さない。
    """
    global _ALBUM_UI
    _ALBUM_UI = album_ui

    if not available():
        st.error("データがありません。`python crawl_official.py` → "
                 "`python fetch_images.py` → `python make_thumbs.py` → "
                 "`python build_dex.py` の順に実行してください。")
        return

    s = stats(db_stamp())
    st.title(title)
    st.caption(f"{s['cards']:,}枚 / {s['series']}シリーズ"
               f"　｜　画像 {s['images']:,}枚"
               f"（{100*s['images']/max(1,s['cards']):.0f}%）"
               f"　｜　リーダー {s['leaders']}枚"
               f"　｜　カード情報の出典: ONE PIECEカードゲーム公式サイト")

    if _picked("detail"):
        card = fetch_card(_picked("detail"))
        if card:
            st.button("← 一覧にもどる", key=_sk("back_detail"),
                      on_click=_pick, args=("detail", None))
            show_detail(card)
            return

    # st.tabs は使わない。要素が増減すると選択が先頭に戻る仕様で、
    # 「シリーズの収録カードを押したのに、さがすタブが開く」という動きになる
    # （ポケカ図鑑で実際に踏んだ）。ラジオなら選択が session_state に残る
    TABS = ["🔎 さがす", "📦 拡張パック", "🗃 構築デッキ・その他", "👑 リーダー"]
    tab = st.radio("表示", TABS, horizontal=True, label_visibility="collapsed",
                   key=_sk("tab"))

    if tab == TABS[0]:
        c1, c2 = st.columns([3, 2])
        kw = c1.text_input("カード名・カード番号で検索", key=_sk("find_kw"),
                           placeholder="例: ルフィ / OP01-001 / 001")
        feats = features_all(db_stamp())
        fmap = dict(feats)
        fsel = c2.multiselect("特徴", [f for f, _ in feats], key=_sk("find_feat"),
                              format_func=lambda f: f"{f}（{fmap[f]}枚）",
                              placeholder="特徴（麦わらの一味・四皇…）")
        where, args = filter_bar("find")

        if kw.strip():
            q = kw.strip()
            # 「OP01-001」「op01-001」はカード番号。ハイフンを含むかで見分ける。
            # テキストは検索対象にしない。効果文に「ルフィ」が出てくる別カードが
            # 大量に混ざって、探しているカードが埋もれるため
            if "-" in q:
                where.append("d.key LIKE ?")
                args.append(f"{q.upper()}%")
            elif q.isdigit():
                where.append("d.card_no = ?")
                args.append(int(q))
            else:
                where.append("d.name LIKE ?")
                args.append(f"%{q}%")
        if fsel:
            where.append("d.key IN (SELECT key FROM dex_features WHERE feature IN (%s))"
                         % ",".join("?" * len(fsel)))
            args += fsel

        if not where:
            st.info("カード名で探せます。\n\n"
                    "**`OP01-001` のようにハイフンを含めるとカード番号での検索**"
                    "になります（数字だけなら番号だけで全シリーズ横断）。\n\n"
                    "色・種類・レアリティ・特徴だけでも絞り込めます。")
        else:
            cond = " AND ".join(where)
            n = conn().execute("SELECT COUNT(*) FROM dex d WHERE " + cond,
                               args).fetchone()[0]
            page = paginate(n, "pg_find")
            _, rows = query(cond, args,
                            "(d.img IS NULL), d.rarity_i DESC, d.set_code DESC, "
                            "d.card_no, d.variant", page)
            show_cards(rows, key_prefix="find")

    # ── 拡張パック（表紙の一覧から入る）──────────────────────────────────
    elif tab == TABS[1]:
        if _picked("pack"):
            show_series_cards(_picked("pack"), back_key="pack")
        else:
            show_product_grid("拡張パック", "pk", "pack")

    # ── 構築デッキ・その他 ────────────────────────────────────────────────
    elif tab == TABS[2]:
        if _picked("other"):
            show_series_cards(_picked("other"), back_key="other")
        else:
            kind = st.radio("商品の種類", ["構築デッキ", "その他の商品"],
                            horizontal=True, key=_sk("other_kind"))
            show_product_grid(kind, "ot", "other")

    else:
        show_leaders()


if __name__ == "__main__":
    main()
