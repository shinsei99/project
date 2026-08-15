"""
ポケモンカード図鑑（日本語版）— Streamlit UI

日本語版のカードを、名前・カード番号・レアリティ・タイプで検索して閲覧する。

データは **DMMマイカ**（myca.dmm.com）が骨格。番号・総数・レアリティ・収録パックを
持っているのはここだけで、公式サイトはレアリティを公開しておらず、TCGdex は
日本語版の細かい区分（MUR/MA/SAR/SSR …）を持たず収録の抜けも多い。
ワザ・HP・効果文は TCGdex から、セット名・発売日・表紙・商品分類は公式から補う。
組み立ては build_dex.py（dex / dex_sets テーブル）。

  🔎 さがす           … カード名・カード番号（001/081）／タイプ・レアリティで絞る
  📦 拡張パック         … パックの表紙一覧から収録カードへ
  🗃 構築デッキ・その他   … 同じく一覧から。分類は公式の商品種別に従う

⚠️ 自分専用・localhost バインド。カード画像の著作権は
   ©Pokémon/Nintendo/Creatures/GAME FREAK に帰属するため、公開・配布はしない。
"""

from __future__ import annotations

import json
import os
import sqlite3

import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "data", "cards.db")

# TCGdex のタイプ名 → 日本語
TYPE_JA = {
    "Grass": "草", "Fire": "炎", "Water": "水", "Lightning": "雷", "Psychic": "超",
    "Fighting": "闘", "Darkness": "悪", "Metal": "鋼", "Fairy": "妖", "Dragon": "竜",
    "Colorless": "無", "Colorless2": "無",
}
STAGE_JA = {"Basic": "たね", "Stage1": "1進化", "Stage2": "2進化",
            "VMAX": "VMAX", "MEGA": "MEGA"}

# レアリティの読み。絞り込みの選択肢に添えて、どれが何か分かるようにする。
# レアリティが刷られていないカードを絞り込みで選ぶための見出し。
# 実データのレアリティ（RARITY_NOTE の左側）と衝突しない文字列にする
NO_RARITY = "表記なし"

RARITY_NOTE = {
    "C": "コモン", "U": "アンコモン", "R": "レア", "RR": "ダブルレア",
    "RRR": "トリプルレア", "AR": "アートレア", "SR": "スーパーレア",
    "SAR": "スペシャルアートレア", "SSR": "シャイニースーパーレア",
    "UR": "ウルトラレア", "HR": "ハイパーレア", "MA": "メガアート",
    "MUR": "メガウルトラレア", "FUR": "フルアートウルトラレア",
    "BWR": "ブラック＆ホワイトレア", "CHR": "キャラクターレア",
    "CSR": "キャラクタースーパーレア", "TR": "トレーナーズレア",
    "PR": "プリズムレア", "PROMO": "プロモ", "K": "きらめき", "A": "A", "S": "S",
    "●": "コモン（旧裏面）", "◆": "アンコモン（旧裏面）", "★": "レア（旧裏面）",
    "○": "旧裏面", "◇": "旧裏面", "☆": "旧裏面",
    "キラ": "キラ仕様", "ミラー": "ミラー仕様", "e": "e シリーズ",
}


def ja_types(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        return "・".join(TYPE_JA.get(t, t) for t in json.loads(raw))
    except Exception:
        return ""


def ja_cost(cost: list) -> str:
    return "".join(TYPE_JA.get(c, c[:1]) for c in (cost or [])) or "―"


def card_no_label(row) -> str:
    """「110/076」の形。番号が印刷されていないカード（プロモ等）は空。"""
    if row["card_no"] is None:
        return ""
    if row["total"]:
        return f"{row['card_no']:03d}/{row['total']:03d}"
    return f"{row['card_no']:03d}"


@st.cache_resource
def conn():
    c = sqlite3.connect(DB, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def has_dex() -> bool:
    return bool(conn().execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='dex'").fetchone())


def db_stamp() -> float:
    """DBの更新時刻。キャッシュの鍵にして、build_dex.py を回したあと
    自動で読み直されるようにする。この鍵があるので手動の再読み込みボタンは
    要らない（キャッシュ関数は全てこれを受け取ること）。"""
    try:
        return os.path.getmtime(DB)
    except OSError:
        return 0.0


@st.cache_data(show_spinner=False)
def stats(_stamp: float = 0.0):
    q = lambda s: conn().execute(s).fetchone()[0]
    return {
        "cards": q("SELECT COUNT(*) FROM dex"),
        "sets": q("SELECT COUNT(*) FROM dex_sets"),
        "images": q("SELECT COUNT(*) FROM dex WHERE img IS NOT NULL "
                    "OR img_off IS NOT NULL OR img_web IS NOT NULL"),
        "rarity": q("SELECT COUNT(*) FROM dex WHERE rarity IS NOT NULL"),
    }


@st.cache_data(show_spinner=False)
def product_list(ptype: str | None, _stamp: float = 0.0):
    """図鑑の入口。公式の商品（拡張パック187件など）を軸に並べる。

    セット記号で並べると公式の商品と1対1にならない（プロモが細かく割れる、
    TCGdex の分割が公式と違う）。公式に商品ページが無い初期のパックは
    build_dex.py がセットのまま入れているので、そちらも同じ一覧に出る。
    """
    sql = ("SELECT title, ptype, release, cover, set_code, pack_name, cards, images "
           "FROM dex_products WHERE " + ("ptype = ?" if ptype else "ptype IS NULL")
           + " ORDER BY (release IS NULL), release DESC, title")
    return [dict(r) for r in conn().execute(sql, (ptype,) if ptype else ())]


@st.cache_data(show_spinner=False)
def rarities_in(set_code: str | None = None, pack_name: str | None = None,
                _stamp: float = 0.0):
    """存在するレアリティを、弱い順に（枚数つきで）返す。

    レアリティが無いカードも NO_RARITY として最後に混ぜる。これはデータの
    欠落ではなく**カードに刷られていない**（スタートデッキ100、THE BEST OF XY、
    ハイクラスパックの通常カード、構築デッキなど）。全体の3分の1がこれに当たり、
    除いてしまうと絞り込みから丸ごと外れて辿れなくなる。
    """
    sql = "SELECT rarity, COUNT(*) FROM dex WHERE 1=1"
    args: tuple = ()
    if pack_name:
        sql += " AND pack_name = ?"
        args = (pack_name,)
    elif set_code:
        sql += " AND set_code = ?"
        args = (set_code,)
    sql += " GROUP BY rarity ORDER BY (rarity IS NULL), MIN(rarity_i)"
    return [(r[0] if r[0] is not None else NO_RARITY, r[1])
            for r in conn().execute(sql, args)]


@st.cache_data(show_spinner=False)
def types_in(set_code: str | None = None, pack_name: str | None = None,
             _stamp: float = 0.0):
    """そのパックに実際にあるタイプを、図鑑の並び順で返す。

    タイプは TCGdex 由来なので、ワザ等が紐づいていないカードには入っていない。
    1枚も無いパックでは選択肢を出さない。
    """
    sql = "SELECT types FROM dex WHERE types IS NOT NULL"
    args: tuple = ()
    if pack_name:
        sql += " AND pack_name = ?"
        args = (pack_name,)
    elif set_code:
        sql += " AND set_code = ?"
        args = (set_code,)
    found = set()
    for (raw,) in conn().execute(sql, args):
        try:
            for t in json.loads(raw):
                if t in TYPE_JA:
                    found.add(TYPE_JA[t])
        except Exception:
            pass
    order = list(dict.fromkeys(TYPE_JA.values()))
    return [t for t in order if t in found]


def rarity_option(r: str, n: int) -> str:
    if r == NO_RARITY:
        return f"{NO_RARITY}（{n}枚）"
    note = RARITY_NOTE.get(r)
    return f"{r}（{n}枚）" if not note else f"{r} {note}（{n}枚）"


def rarity_where(picked) -> tuple[str, list]:
    """選ばれたレアリティを SQL の条件にする。「表記なし」は NULL で引く。"""
    real = [r for r in picked if r != NO_RARITY]
    cond, args = [], []
    if real:
        cond.append("rarity IN (" + ",".join("?" for _ in real) + ")")
        args += real
    if NO_RARITY in picked:
        cond.append("rarity IS NULL")
    return "(" + " OR ".join(cond) + ")", args


def _pick(key, value, extra=None):
    """ボタンのコールバック。再実行の前に session_state を書き換える。

    st.rerun() でやると st.tabs の選択が先頭に戻り、「拡張パックの収録カードを
    押したのに、さがすタブが開く」という動きになる。

    カード詳細は他の何よりも優先して全画面で出すので、詳細を開いたまま
    別のタブでパックを開くと詳細のままになる（さがすでゼラオラを開いたあと
    拡張パックの収録カードを押すとゼラオラが出た）。パックを開くときは
    詳細を閉じる。
    """
    st.session_state[key] = (value, extra) if extra is not None else value
    if key != "detail" and value is not None:
        st.session_state["detail"] = None


def thumb_of(row):
    """一覧用の小さい画像。無ければ通常の画像で代用する。

    400px版は1枚67KBあり、MEGAドリームex（486枚）を一度に並べると
    33MBをブラウザへ送ることになって表示が遅い。一覧では180px版
    （1枚18KB）を使い、詳細を開いたときだけ400px版を出す。
    """
    small = os.path.join(HERE, "data", "myca_thumbs", *_key_parts(row))
    if os.path.exists(small):
        return small
    return image_of(row)


def _key_parts(row):
    k = (row["key"] or "").split("/")
    return (k[0], f"{k[1]}.jpg") if len(k) == 2 else ("", "none.jpg")


def image_of(row):
    """公式の高画質画像（360px）を主にし、無いものだけマイカ画像で補う。

    公式のファイル名は通し番号で番号を含まないため、build_dex.py は
    「AIが画像の印字を読んで番号を確定した」または「そのセットに同名が
    1枚だけ」の場合しか img_off に入れない。別のカードの絵を出さないための
    条件で、これを満たさないぶんはマイカ画像（番号と1対1）を使う。

    公式は発売直後のパックの特別枠を登録しないので（ストームエメラルダの
    SAR/MUR など）、そこは当面マイカ画像のままになる。公式に追加されたあと
    crawl_official → read_official → build_dex を回せば自動で差し替わる。
    """
    if row["img_off"] and os.path.exists(row["img_off"]):
        return row["img_off"]
    if row["img"] and os.path.exists(row["img"]):
        return row["img"]
    # 公式にもマイカにも無い年代（eシリーズ・PCG4/9・1996年の第1弾）だけ、
    # learn-book.com から補ったものを使う。最後の手段（learnbook.py 参照）
    if row["img_web"] and os.path.exists(row["img_web"]):
        return row["img_web"]
    if row["image_tcgdex"]:
        return f"{row['image_tcgdex']}/low.png"
    return None


# ── カード詳細 ───────────────────────────────────────────────────────────────

def show_detail(card):
    col_img, col_txt = st.columns([1, 1.4])
    with col_img:
        u = image_of(card)
        if u:
            st.image(u, width="stretch")
            if card["img_off"] and os.path.exists(card["img_off"]):
                st.caption("公式サイトの画像")
            elif card["img"] and u == card["img"]:
                st.caption("マイカの画像で補完（公式に未登録のため）")
            elif card["img_web"] and u == card["img_web"]:
                st.caption("learn-book.com の画像で補完"
                           "（この年代は公式・マイカ・TCGdex のどこにも画像が無い）")
        else:
            st.info("このカードの画像は未収録です")

    with col_txt:
        st.markdown(f"### {card['name']}")
        bits = []
        if card["hp"]:
            bits.append(f"HP {card['hp']}")
        if ja_types(card["types"]):
            bits.append(ja_types(card["types"]))
        if card["stage"]:
            bits.append(STAGE_JA.get(card["stage"], card["stage"]))
        if card["rarity"]:
            note = RARITY_NOTE.get(card["rarity"])
            bits.append(card["rarity"] + (f"（{note}）" if note else ""))
        if bits:
            st.caption("　/　".join(bits))

        sname = conn().execute("SELECT name FROM dex_sets WHERE set_code=?",
                               (card["set_code"],)).fetchone()
        st.write(f"**{sname['name'] if sname else card['set_code']}**"
                 f"　{card_no_label(card)}　`{card['set_code']}`")
        if card["pack_name"]:
            st.caption(f"収録: {card['pack_name']}")

        try:
            attacks = json.loads(card["attacks"] or "[]")
        except Exception:
            attacks = []
        for a in attacks:
            dmg = a.get("damage")
            st.markdown(f"**{ja_cost(a.get('cost'))}　{a.get('name')}**"
                        + (f"　　{dmg}" if dmg else ""))
            if a.get("effect"):
                st.caption(a["effect"])

        try:
            weak = json.loads(card["weaknesses"] or "[]")
        except Exception:
            weak = []
        if weak:
            st.write("弱点: " + "、".join(
                f"{TYPE_JA.get(w.get('type'), w.get('type'))}{w.get('value','')}"
                for w in weak))
        if card["retreat"] is not None:
            st.write(f"にげる: {card['retreat']}")
        if card["descr"]:
            st.caption(card["descr"])
        if card["illustrator"]:
            st.caption(f"Illus. {card['illustrator']}")
        if not attacks and not card["tcg_id"]:
            st.caption("ワザや効果文は未収録です（TCGdex に該当カードがありません）")


def show_cards(rows, cols=6, key_prefix=""):
    """サムネイル一覧。押すと詳細をその場に開く。

    key_prefix はボタンのキーを一意にするために要る。Streamlit はタブを
    すべて同時に描画するので、拡張パックタブと構築デッキタブの両方で
    セットを開いた状態にすると同じカードのボタンが2回作られてしまう
    （StreamlitDuplicateElementKey）。
    """
    for i in range(0, len(rows), cols):
        for c, row in zip(st.columns(cols), rows[i:i + cols]):
            with c:
                u = thumb_of(row)
                if u:
                    st.image(u, width="stretch")
                else:
                    st.markdown(
                        "<div style='aspect-ratio:180/251;background:#eceff1;"
                        "border-radius:6px;display:flex;align-items:center;"
                        "justify-content:center;color:#90a4ae;font-size:11px'>"
                        "画像なし</div>", unsafe_allow_html=True)
                no = card_no_label(row)
                st.caption(f"{no} {row['name'][:10]}"
                           + (f"　**{row['rarity']}**" if row["rarity"] else ""))
                st.button("詳細", key=f"d_{key_prefix}_{row['key']}",
                          width="stretch",
                          on_click=_pick, args=("detail", row["key"]))


def show_cover_grid(items, key_prefix, on_pick_key, cols=6):
    """商品の表紙をタイル状に並べる。押すと収録カードへ。"""
    for i in range(0, len(items), cols):
        for j, (c, p) in enumerate(zip(st.columns(cols), items[i:i + cols])):
            with c:
                if p.get("cover") and os.path.exists(p["cover"]):
                    st.image(p["cover"], width="stretch")
                else:
                    st.markdown(
                        "<div style='aspect-ratio:4/3;background:#eceff1;"
                        "border-radius:6px;display:flex;align-items:center;"
                        "justify-content:center;color:#90a4ae;font-size:11px'>"
                        "表紙なし</div>", unsafe_allow_html=True)
                st.caption(f"**{p['title'][:26]}**\n\n"
                           f"{p['release'] or '発売日不明'}　{p['cards'] or 0}枚")
                if p.get("set_code") or p.get("pack_name"):
                    # 1つのセット記号に複数パックが同居することがあるので
                    # （XY11 = 冷酷の反逆者＋爆熱の闘士）、パック名も渡す。
                    # 逆にセット記号が無いカードもある（初期のスターターパック
                    # はタイトルに記号が印字されていない）。その場合は
                    # パック名だけで絞る。
                    # rerun ではなく on_click を使う。rerun するとタブの選択が
                    # 先頭（さがす）に戻ってしまう。
                    st.button("収録カード", key=f"{key_prefix}_{i}_{j}",
                              width="stretch",
                              on_click=_pick, args=(on_pick_key, p["set_code"],
                                                    p.get("pack_name")))
                else:
                    st.caption("（収録カードは未取得）")


def show_set_cards(picked_key, back_key=None):
    """1商品の収録カードを、そこにあるレアリティだけで絞り込めるように出す。

    セット記号だけでは足りない。1つの記号に複数パックが同居することがあり
    （XY11 = 冷酷の反逆者＋爆熱の闘士、S-P に至っては14パック）、記号で引くと
    片方しか出せない。パック名が判っているものはそちらで絞る。
    """
    if isinstance(picked_key, (tuple, list)):
        set_code, pack_name = picked_key[0], picked_key[1]
    else:
        set_code, pack_name = picked_key, None
    info = conn().execute(
        "SELECT * FROM dex_sets WHERE set_code=?", (set_code,)).fetchone() \
        if set_code else None
    if back_key:
        st.button("← 一覧にもどる", key=f"back_{back_key}",
                  on_click=_pick, args=(back_key, None))
    if not info and pack_name:
        st.markdown(f"### {pack_name}")
    present = rarities_in(set_code, pack_name, db_stamp())
    # 丸ごと無印のセット（スタートデッキ100・THE BEST OF XY など）は「表記なし」
    # しか出ない。選ぶ意味が無いので選択肢は出さず、下の一文で理由を書く
    if len(present) == 1 and present[0][0] == NO_RARITY:
        present = []
    picked, t_pick = [], None
    rar_key = f"rar_{back_key or ''}_{set_code}_{pack_name or ''}"

    if info:
        # 表紙の右に「見出し → 情報 → レアリティ絞り込み」を積む。
        # 絞り込みを表紙の下に離して置くと縦に間延びして読みにくい。
        c1, c2 = st.columns([1, 4])
        if info["cover"] and os.path.exists(info["cover"]):
            c1.image(info["cover"], width="stretch")
        c2.markdown(f"### {info['name']}")
        c2.caption(f"{info['release'] or '発売日不明'}"
                   f"　｜　{info['ptype'] or '分類なし'}"
                   f"　｜　{info['cards']}枚（画像 {info['images']}枚）"
                   f"　｜　`{set_code}`")
        with c2:
            # レアリティとタイプを横並びにする。さがすタブと同じ操作感にする
            f1, f2 = st.columns([2, 1])
            with f1:
                if present:
                    picked = st.multiselect(
                        "レアリティで絞る（未選択なら全部）", [r for r, _ in present],
                        format_func=lambda r: rarity_option(r, dict(present)[r]),
                        key=rar_key, label_visibility="collapsed",
                        placeholder="レアリティで絞る（未選択なら全部）")
                else:
                    st.caption("このセットのカードにはレアリティ記号が印字されて"
                               "いないため、絞り込みはありません")
            with f2:
                types_here = types_in(set_code, pack_name, db_stamp())
                if types_here:
                    t_pick = st.selectbox(
                        "タイプ", ["すべてのタイプ"] + types_here,
                        key=f"typ_{back_key or ''}_{set_code}_{pack_name or ''}",
                        label_visibility="collapsed")
    else:
        f1, f2 = st.columns([2, 1])
        with f1:
            if present:
                picked = st.multiselect(
                    "レアリティで絞る（未選択なら全部）", [r for r, _ in present],
                    format_func=lambda r: rarity_option(r, dict(present)[r]),
                    key=rar_key)
            else:
                st.caption("このセットのカードにはレアリティ記号が印字されて"
                           "いないため、絞り込みはありません")
        with f2:
            types_here = types_in(set_code, pack_name, db_stamp())
            if types_here:
                t_pick = st.selectbox(
                    "タイプ", ["すべてのタイプ"] + types_here,
                    key=f"typ_{back_key or ''}_{set_code}_{pack_name or ''}")

    if pack_name:
        sql, args = "SELECT * FROM dex WHERE pack_name = ?", [pack_name]
    elif set_code:
        sql, args = "SELECT * FROM dex WHERE set_code = ?", [set_code]
    else:
        sql, args = "SELECT * FROM dex WHERE 0", []
    if picked:
        cond, cond_args = rarity_where(picked)
        sql += " AND " + cond
        args += cond_args
    if t_pick and t_pick != "すべてのタイプ":
        en = [k for k, v in TYPE_JA.items() if v == t_pick]
        sql += " AND (" + " OR ".join("types LIKE ?" for _ in en) + ")"
        args += [f'%"{e}"%' for e in en]
    sql += " ORDER BY (card_no IS NULL), card_no, key"
    rows = conn().execute(sql, args).fetchall()

    # 1ページに全部並べると画像の転送量が数十MBになり表示が遅い
    # （MEGAドリームex 486枚 × 400px版67KB = 32MB）。一覧はサムネイル
    # （180px・18KB）にした上で、150枚ずつに区切る（6列×25段で約2.7MB）。
    PER_PAGE = 150
    total_pages = (len(rows) + PER_PAGE - 1) // PER_PAGE
    page = 1
    conds = list(picked) + ([t_pick] if t_pick and t_pick != "すべてのタイプ" else [])
    head = f"**{len(rows)}枚**" + ("　｜　" + "・".join(conds) if conds else "")
    if total_pages > 1:
        c1, c2 = st.columns([2, 3])
        c1.write(head)
        page = c2.slider("ページ", 1, total_pages, 1,
                         key=f"pg_{back_key or ''}_{set_code}_{pack_name or ''}",
                         label_visibility="collapsed")
        st.caption(f"{page} / {total_pages} ページ"
                   f"（{(page-1)*PER_PAGE+1}〜{min(page*PER_PAGE, len(rows))}枚目）")
    else:
        st.write(head)
    show_cards(rows[(page - 1) * PER_PAGE: page * PER_PAGE],
               key_prefix=back_key or set_code)


def fetch_card(key):
    return conn().execute("SELECT * FROM dex WHERE key = ?", (key,)).fetchone()


# ── メイン ───────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(page_title="ポケモンカード図鑑", page_icon="🃏", layout="wide")

    if not os.path.exists(DB) or not has_dex():
        st.error("データがありません。`python crawl_myca.py` → "
                 "`python fetch_myca_large.py` → `python make_thumbs.py` → "
                 "`python build_dex.py` を実行してください。")
        return

    s = stats(db_stamp())
    st.title("🃏 ポケモンカード図鑑")
    # レアリティは割合を出さない。空欄は取りこぼしではなく、カードに記号が
    # 刷られていないもの（構築デッキ・スタートデッキ100・ハイクラスパックの
    # 通常カードなど3分の1が該当する）。％にすると欠落のように見えてしまう
    st.caption(f"日本語版 {s['cards']:,}枚 / {s['sets']}セット"
               f"　｜　画像 {s['images']:,}枚（{100*s['images']/max(1,s['cards']):.0f}%）"
               f"　｜　レアリティ記号あり {s['rarity']:,}枚")

    if st.session_state.get("detail"):
        card = fetch_card(st.session_state.detail)
        if card:
            st.button("← 一覧にもどる", on_click=_pick, args=("detail", None))
            show_detail(card)
            return

    # st.tabs は使わない。要素が増減すると選択が先頭に戻る仕様で、
    # 「さがすで検索した状態で拡張パックの収録カードを押すと、さがすタブに
    # 飛ぶ」という動きになった。ラジオなら選択が session_state に残るので
    # リセットされない。選んだタブだけ描画するので表示も軽くなる
    # （st.tabs は3タブ全部を毎回描画していた）。
    TABS = ["🔎 さがす", "📦 拡張パック", "🗃 構築デッキ・その他"]
    tab = st.radio("表示", TABS, horizontal=True, label_visibility="collapsed",
                   key="tab")

    # ── さがす ────────────────────────────────────────────────────────────
    if tab == TABS[0]:
        c1, c2, c3 = st.columns([3, 1, 1.4])
        kw = c1.text_input("カード名・カード番号で検索",
                           placeholder="例: リザードン / 110/076 / 001/081")
        t_sel = c2.selectbox("タイプ", ["すべて"] + list(TYPE_JA.values())[:11])
        all_rar = rarities_in(None, None, db_stamp())
        r_sel = c3.multiselect("レアリティ", [r for r, _ in all_rar],
                               format_func=lambda r: rarity_option(r, dict(all_rar)[r]),
                               placeholder="すべて")

        where, args = [], []
        if kw.strip():
            q = kw.strip()
            # 「110/076」のようにスラッシュを含むならカード番号として扱う。
            # 分母はそのセットのナンバリング総数なので、両方で照合すると
            # 「001/083」のような別セットの1番を拾わずに済む。
            if "/" in q:
                head, _, tail = q.partition("/")
                hn = head.strip().lstrip("0") or "0"
                tn = tail.strip().lstrip("0")
                if hn.isdigit():
                    where.append("card_no = ?")
                    args.append(int(hn))
                if tn.isdigit():
                    where.append("total = ?")
                    args.append(int(tn))
            else:
                # カード名だけを見る。ワザ名や効果文まで対象にすると
                # 「ピカチュウ」でロケット団のミミッキュ（効果文にピカチュウが
                # 出てくる）が引っかかり、関係ないカードが混ざる
                where.append("name LIKE ?")
                args.append(f"%{q}%")
        if t_sel != "すべて":
            en = [k for k, v in TYPE_JA.items() if v == t_sel]
            where.append("(" + " OR ".join("types LIKE ?" for _ in en) + ")")
            args += [f'%"{e}"%' for e in en]
        if r_sel:
            cond, cond_args = rarity_where(r_sel)
            where.append(cond)
            args += cond_args

        if not where:
            st.info("カード名で探せます。\n\n"
                    "**`110/076` のようにスラッシュを含めるとカード番号での検索**になります。")
        else:
            # 件数を先に数えて、表示は1ページぶんだけ取る。上限で打ち切ると
            # 「300件（上限）」と出るだけで先が見られないため、ページ送りにする。
            cond = " AND ".join(where)
            n_hit = conn().execute(
                "SELECT COUNT(*) FROM dex WHERE " + cond, args).fetchone()[0]
            PER_PAGE = 150
            total_pages = (n_hit + PER_PAGE - 1) // PER_PAGE
            page = 1
            if total_pages > 1:
                h1, h2 = st.columns([2, 3])
                h1.write(f"**{n_hit:,}件**")
                page = h2.slider("ページ", 1, total_pages, 1, key="pg_find",
                                 label_visibility="collapsed")
                st.caption(f"{page} / {total_pages} ページ"
                           f"（{(page-1)*PER_PAGE+1:,}〜"
                           f"{min(page*PER_PAGE, n_hit):,}件目）")
            else:
                st.write(f"**{n_hit:,}件**")

            rows = conn().execute(
                "SELECT * FROM dex WHERE " + cond
                + " ORDER BY (img IS NULL), rarity_i DESC, set_code, card_no"
                + " LIMIT ? OFFSET ?",
                args + [PER_PAGE, (page - 1) * PER_PAGE]).fetchall()
            show_cards(rows, key_prefix="find")

    # ── 拡張パック（表紙の一覧から入る）───────────────────────────────────
    elif tab == TABS[1]:
        if st.session_state.get("pack"):
            show_set_cards(st.session_state.pack, back_key="pack")
        else:
            packs = product_list("拡張パック", db_stamp())
            st.caption(f"{len(packs)}パック　新しい順　｜　"
                       "「収録カード」でそのパックの中身へ")
            show_cover_grid(packs, "pk", "pack")

    # ── 構築デッキ・その他 ────────────────────────────────────────────────
    else:
        if st.session_state.get("other"):
            show_set_cards(st.session_state.other, back_key="other")
        else:
            kind = st.radio("商品の種類",
                            ["構築デッキ", "その他の商品", "分類なし"],
                            horizontal=True)
            items = product_list(None if kind == "分類なし" else kind, db_stamp())
            st.caption(f"{len(items)}件　新しい順"
                       + ("　｜　公式の商品ページと対応が付かないもの"
                          "（プロモ・初期セット等）" if kind == "分類なし" else ""))
            show_cover_grid(items, "ot", "other")


if __name__ == "__main__":
    main()
