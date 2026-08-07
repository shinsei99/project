"""PSA保有カード管理

PSA「My Collection」のCSVエクスポートを読み込み、保有カードの検索・絞り込み・
保管場所の記録を行う在庫管理アプリ。
"""

import base64
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from psa_images import DAILY_LIMIT, ImageStore, fetch_many

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
CSV_PATH = DATA_DIR / "collection.csv"
NOTES_PATH = DATA_DIR / "storage_notes.json"
TOKEN_PATH = DATA_DIR / "psa_api.json"
ORDERS_PATH = DATA_DIR / "orders.json"
ALBUMS_PATH = DATA_DIR / "albums.json"

def album_location(vault_status: str) -> str:
    """Vault Status を Home / Vault に分類。"""
    return "Vault" if vault_status in ("Vaulted", "Vault Bound") else "Home"

# PSAグレーディングの工程順（progressSummary.lastCompletedStep の次が「現在の工程」）
GRADING_STEPS = [
    ("OrderPrep", "受付・仕分け"),
    ("Received", "受付・仕分け"),
    ("ResearchAndID", "リサーチ&ID"),
    ("Grading", "グレーディング"),
    ("Assembly", "組立(Assembly)"),
    ("QAChecks", "QAチェック"),
    ("Encapsulation", "封入(Encapsulation)"),
    ("Shipped", "発送済み"),
]

NUM_COLS = [
    "PSA Estimate", "My Cost", "My Value", "Gain/Loss",
    "Listing Price", "Sold Price", "Sold Fees", "Sold Proceeds",
]
DATE_COLS = ["Date Acquired", "Vaulted Date", "Listing Date", "Sold Date", "Payment Date"]

# 画面表示用の日本語ラベル
LABELS = {
    "Cert Number": "証明書番号",
    "Grade": "グレード",
    "Year": "年",
    "Set": "セット",
    "Card Number": "カード番号",
    "Subject": "カード名",
    "Variety": "種別",
    "PSA Estimate": "PSA推定額",
    "Vault Status": "Vault",
    "Listing Status": "出品",
    "Listing Price": "出品価格",
    "Sold Price": "売却額",
    "Sold Proceeds": "手取り",
    "Sold Date": "売却日",
    "Sold On": "売却先",
    "Item Status": "状態",
    "保管場所": "保管場所",
    "メモ": "メモ",
    "cert_url": "PSA",
}

st.set_page_config(page_title="PSA保有カード管理", page_icon="🃏", layout="wide")


# ---------------------------------------------------------------- データ読み込み

@st.cache_data
def load_collection(path: Path, mtime: float) -> pd.DataFrame:
    """CSVを読み、'-' を欠損に、金額・日付を型変換して返す。mtimeはキャッシュ用。"""
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df = df.replace("-", pd.NA)

    for col in NUM_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(r"[$,]", "", regex=True), errors="coerce"
            )
    for col in DATE_COLS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], format="%m/%d/%Y", errors="coerce")

    df["Year"] = df["Year"].fillna("")
    # 「1998-99」のような表記があるため、先頭4桁を数値の年として別に持つ
    df["year_num"] = pd.to_numeric(df["Year"].str.extract(r"(\d{4})")[0], errors="coerce")
    df["grade_num"] = pd.to_numeric(df["Grade"], errors="coerce")
    df["cert_url"] = "https://www.psacard.com/cert/" + df["Cert Number"].astype(str)
    return df


def load_notes() -> dict:
    if NOTES_PATH.exists():
        return json.loads(NOTES_PATH.read_text(encoding="utf-8"))
    return {}


def save_notes(notes: dict) -> None:
    NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
    NOTES_PATH.write_text(
        json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_token() -> str:
    if TOKEN_PATH.exists():
        return json.loads(TOKEN_PATH.read_text(encoding="utf-8")).get("token", "")
    return ""


def save_token(token: str) -> None:
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(json.dumps({"token": token}), encoding="utf-8")


def yen(v) -> str:
    return "—" if pd.isna(v) else f"${v:,.0f}"


@st.cache_data
def load_orders(mtime: float):
    """data/orders.json（PSAグレーディング申請一覧）を読む。mtimeはキャッシュ用。"""
    return json.loads(ORDERS_PATH.read_text(encoding="utf-8"))


def order_current_step(order: dict) -> str:
    """progressSummary.lastCompletedStep の次の工程名を日本語で返す。"""
    ps = order.get("progressSummary") or {}
    last = ps.get("lastCompletedStep")
    keys = [k for k, _ in GRADING_STEPS]
    labels = dict(GRADING_STEPS)
    if last in keys:
        i = keys.index(last)
        nxt = keys[i + 1] if i + 1 < len(keys) else last
        return labels.get(nxt, nxt)
    return "受付・仕分け"


def fmt_due(lo, hi) -> str:
    """完成予定（dueOutDate ～ upperRange）を YYYY-MM-DD 〜 YYYY-MM-DD 表記に。"""
    def d(x):
        return str(x)[:10] if x else None
    a, b = d(lo), d(hi)
    if a and b:
        return f"{a} 〜 {b}"
    return a or "—"


# グレーディング工程名（英→日）。orderProgressSteps の step 値に対応。
STEP_JA = {
    "Arrived": "到着", "OrderPrep": "受付・仕分け", "ResearchAndID": "リサーチ&ID",
    "Grading": "グレーディング", "Assembly": "組立", "QACheck": "QAチェック",
    "GradesReady": "グレード確定", "Completed": "完了",
}


def render_grading():
    """「鑑定中」ビュー：PSAグレーディング申請中の個別カード（263枚）を表示する。"""
    st.subheader("🔬 グレーディング申請中のカード")
    if not ORDERS_PATH.exists():
        st.info(
            "グレーディング申請データがありません。\n\n"
            "ターミナルで **`./update_orders.sh`** を実行すると、"
            "ログイン済みSafariのPSAアカウントから申請中カードを取り込みます。"
        )
        return

    data = load_orders(ORDERS_PATH.stat().st_mtime)
    cards = data.get("cards", [])
    orders = data.get("orders", [])
    in_prog = [o for o in orders if o.get("status") == "Processing"]

    if not cards:
        st.success("グレーディング申請中のカードはありません。")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("進行中オーダー", f"{len(in_prog)} 件")
    c2.metric("鑑定中カード", f"{len(cards):,} 枚")
    c3.caption(
        f"最終取込\n\n{datetime.fromtimestamp(ORDERS_PATH.stat().st_mtime):%Y-%m-%d %H:%M}"
        "\n\n更新: `./update_orders.sh`"
    )

    # オーダー別サマリー（サービス・工程・枚数・完成予定）
    order_by_no = {str(o.get("orderNumber")): o for o in in_prog}
    for o in in_prog:
        step = order_current_step(o)
        due = fmt_due(o.get("dueOutDate"), o.get("dueOutDateUpperRange"))
        st.markdown(
            f"・ **#{o.get('orderNumber')}**　{o.get('service')}　"
            f"<span style='color:#2563eb;font-weight:700'>{step}</span>　"
            f"{o.get('itemCount')}枚　完成予定 {due}",
            unsafe_allow_html=True,
        )
    st.divider()

    # 絞り込み
    fc1, fc2 = st.columns([2, 2])
    q = fc1.text_input("カード名・cert番号で検索", placeholder="CHARIZARD / 168518228", key="grading_q")
    order_opts = {f"#{o.get('orderNumber')}（{o.get('service')}・{o.get('itemCount')}枚）": str(o.get("orderNumber")) for o in in_prog}
    picked = fc2.multiselect("オーダーで絞り込み", list(order_opts.keys()), key="grading_orders")
    picked_nos = {order_opts[p] for p in picked}

    view = cards
    if q.strip():
        ql = q.strip().lower()
        view = [c for c in view if ql in (c.get("name") or "").lower() or ql in str(c.get("certNo") or "")]
    if picked_nos:
        view = [c for c in view if str(c.get("orderNumber")) in picked_nos]

    st.caption(f"{len(view):,} 枚を表示")

    # ギャラリー表示（画像＋カード名＋cert番号＋工程）
    per_row = 5
    for i in range(0, len(view), per_row):
        cols = st.columns(per_row)
        for col, c in zip(cols, view[i:i + per_row]):
            o = order_by_no.get(str(c.get("orderNumber")), {})
            step = STEP_JA.get(c.get("currentStep"), c.get("currentStep") or "—")
            front = c.get("front")
            if front:
                col.markdown(
                    f"<img src='{front}' style='width:100%;border-radius:8px'>",
                    unsafe_allow_html=True,
                )
            name = c.get("name") or "—"
            col.markdown(
                f"<div style='font-size:0.72rem;line-height:1.25;margin-top:4px'>"
                f"<b>{name[:60]}</b><br>"
                f"cert #{c.get('certNo') or '—'}<br>"
                f"<span style='color:#2563eb'>{step}</span> ・ #{c.get('orderNumber')}"
                f"</div>",
                unsafe_allow_html=True,
            )

    # 一覧（表）でも確認・書き出しできるように
    with st.expander("📋 一覧（表）で見る"):
        rows = [
            {
                "カード名": c.get("name"),
                "cert番号": c.get("certNo"),
                "工程": STEP_JA.get(c.get("currentStep"), c.get("currentStep")),
                "オーダー#": c.get("orderNumber"),
                "サービス": c.get("service"),
            }
            for c in view
        ]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def load_albums() -> dict:
    """data/albums.json（アルバム名 -> 証明書番号リスト）を読む。"""
    if ALBUMS_PATH.exists():
        try:
            return json.loads(ALBUMS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_albums(albums: dict) -> None:
    ALBUMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    ALBUMS_PATH.write_text(json.dumps(albums, ensure_ascii=False, indent=2), encoding="utf-8")


def _data_uri(path):
    """ローカル画像を base64 data URI に。st.image のメディアID失効を回避（バインダー用）。"""
    if not path:
        return None
    try:
        return "data:image/jpeg;base64," + base64.b64encode(Path(path).read_bytes()).decode()
    except Exception:
        return None


def album_label(df, cert) -> str:
    """外すカード選択用のラベル（PSAグレード＋カード名＋cert）。"""
    row = df[df["Cert Number"].astype(str) == str(cert)]
    if len(row):
        rr = row.iloc[0]
        return f"PSA {rr['Grade']} {(rr['Subject'] or '')[:24]}（{cert}）"
    return str(cert)


def render_album(df, store):
    """「アルバム」ビュー：保有中(Home/Vault)から選び、4列バインダーをドラッグで並べ替え。"""
    st.subheader("📔 コレクションアルバム")
    albums = load_albums()
    active = df[df["Item Status"] == "Active"].copy()

    top = st.columns([3, 2, 1])
    names = list(albums.keys())
    sel = top[0].selectbox("アルバム", names, key="album_sel") if names else None
    if not names:
        top[0].caption("アルバムがありません。右で新規作成してください。")
    new_name = top[1].text_input("新規アルバム名", key="album_new", placeholder="お気に入り など")
    if top[2].button("作成", key="album_create"):
        nm = new_name.strip()
        if nm and nm not in albums:
            albums[nm] = []
            save_albums(albums)
            st.rerun()

    if sel is None:
        st.info("アルバム名を入れて「作成」してください。")
        return

    current = [str(c) for c in albums.get(sel, [])]

    with st.expander("このアルバムの操作（改名・削除）"):
        oc = st.columns([3, 1, 1])
        rn = oc[0].text_input("新しい名前", value=sel, key="album_rename")
        if oc[1].button("改名", key="album_do_rename") and rn.strip() and rn.strip() != sel:
            albums[rn.strip()] = albums.pop(sel)
            save_albums(albums)
            st.rerun()
        if oc[2].button("削除", key="album_delete", type="primary"):
            albums.pop(sel, None)
            save_albums(albums)
            st.rerun()

    view_tab, add_tab = st.tabs([f"📖 バインダー（{len(current)}枚）", "➕ カードを追加"])

    with view_tab:
        if not current:
            st.info("まだカードがありません。「➕ カードを追加」から入れてください。")
        else:
            st.caption("並べ替え：**「つかむ」を押す → 移動先の「ここへ」を押す**（4列×10行/ページ）。 🟩HOME ／ 🟦VAULT")

            pick = st.session_state.get("album_pick")
            if pick and pick not in current:
                pick = st.session_state["album_pick"] = None
            if pick:
                pc1, pc2 = st.columns([4, 1])
                pc1.info(f"移動中：{album_label(df, pick)} — 置きたい位置の「ここへ」を押してください。")
                if pc2.button("選択解除", key="album_unpick", width="stretch"):
                    st.session_state["album_pick"] = None
                    st.rerun()

            per_page = 40  # 4列×10行
            n_pages = max(1, -(-len(current) // per_page))
            page = st.number_input(f"ページ（全{n_pages}・40枚/ページ）", 1, n_pages, 1, key="album_view_page")
            page_certs = current[(page - 1) * per_page: page * per_page]

            for i in range(0, len(page_certs), 4):
                cols = st.columns(4)
                for col, cert in zip(cols, page_certs[i:i + 4]):
                    row = df[df["Cert Number"].astype(str) == cert]
                    rr = row.iloc[0] if len(row) else None
                    loc = album_location(rr["Vault Status"]) if rr is not None else "Home"
                    badge = "🟦VAULT" if loc == "Vault" else "🟩HOME"
                    uri = _data_uri(store.thumb(cert))
                    with col:
                        if uri:
                            ring = "outline:3px solid #2563eb;outline-offset:2px;" if cert == pick else ""
                            st.markdown(
                                f"<img src='{uri}' style='width:100%;border-radius:6px;{ring}'>",
                                unsafe_allow_html=True,
                            )
                        gr = rr["Grade"] if rr is not None else ""
                        nm = ((rr["Subject"] if rr is not None else "") or "")[:16]
                        st.caption(f"{badge}・PSA {gr} {nm}")
                        if pick is None:
                            if st.button("つかむ", key=f"grab_{cert}", width="stretch"):
                                st.session_state["album_pick"] = cert
                                st.rerun()
                        elif cert == pick:
                            st.button("● 選択中", key=f"picked_{cert}", width="stretch", disabled=True)
                        else:
                            if st.button("ここへ", key=f"here_{cert}", type="primary", width="stretch"):
                                lst = [c for c in current if c != pick]
                                lst.insert(lst.index(cert), pick)
                                albums[sel] = lst
                                save_albums(albums)
                                st.session_state["album_pick"] = None
                                st.rerun()

            rem = st.multiselect(
                "アルバムから外すカード", current,
                format_func=lambda c: album_label(df, c), key="album_remove",
            )
            if st.button("選択したカードを外す", disabled=not rem, key="album_remove_btn"):
                albums[sel] = [c for c in current if c not in rem]
                save_albums(albums)
                st.rerun()

    with add_tab:
        loc = st.radio("場所", ["両方", "Home", "Vault"], horizontal=True, key="album_loc")
        cand = active[~active["Cert Number"].astype(str).isin(current)].copy()
        if loc == "Home":
            cand = cand[cand["Vault Status"] == "Unvaulted"]
        elif loc == "Vault":
            cand = cand[cand["Vault Status"].isin(["Vaulted", "Vault Bound"])]
        q = st.text_input("検索", key="album_add_q", placeholder="リザードン / セット名 / cert番号")
        if q.strip():
            hay = (
                cand["Subject"].fillna("") + " " + cand["Set"].fillna("") + " "
                + cand["Cert Number"].astype(str)
            )
            cand = cand[hay.str.contains(q.strip(), case=False, na=False)]
        st.caption(f"追加候補 {len(cand)} 枚（保有中で未追加）。選んで下のボタンで追加。")

        picked = []
        rows = list(cand.iterrows())
        per_row = 5
        for i in range(0, len(rows), per_row):
            cols = st.columns(per_row)
            for col, (_, card) in zip(cols, rows[i:i + per_row]):
                cert = str(card["Cert Number"])
                lc = album_location(card["Vault Status"])
                with col:
                    uri = _data_uri(store.thumb(cert))
                    badge = "🟦VAULT" if lc == "Vault" else "🟩HOME"
                    if uri:
                        st.markdown(f"<img src='{uri}' style='width:100%;border-radius:6px'>", unsafe_allow_html=True)
                    st.caption(f"{badge}・PSA {card['Grade']} {(card['Subject'] or '')[:16]}")
                    if st.checkbox("選択", key=f"album_add_{cert}"):
                        picked.append(cert)

        if st.button(
            f"選択した {len(picked)} 枚を「{sel}」に追加",
            type="primary", disabled=not picked, key="album_add_btn",
        ):
            albums[sel] = current + [c for c in picked if c not in current]
            save_albums(albums)
            st.rerun()


if not CSV_PATH.exists():
    st.error(f"CSVが見つかりません: {CSV_PATH}")
    st.info("PSA My Collection のエクスポートCSVをアップロードすると、この端末に取り込んで開始できます。")
    boot = st.file_uploader("CSVを選択", type="csv", key="bootstrap_csv")
    if boot is not None:
        CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        CSV_PATH.write_bytes(boot.getvalue())
        st.cache_data.clear()
        st.success("取り込みました。")
        st.rerun()
    st.stop()

df = load_collection(CSV_PATH, CSV_PATH.stat().st_mtime)
notes = load_notes()
store = ImageStore(DATA_DIR)
cached = store.cached_certs()
df["画像"] = df["Cert Number"].astype(str).isin(cached)

# 保管メモを結合（証明書番号がキー）
df["保管場所"] = df["Cert Number"].map(lambda c: notes.get(str(c), {}).get("place", ""))
df["メモ"] = df["Cert Number"].map(lambda c: notes.get(str(c), {}).get("memo", ""))


# ---------------------------------------------------------------- サイドバー

st.sidebar.title("🃏 PSA保有カード管理")

status = st.sidebar.radio(
    "表示対象",
    ["保有中（Vault）", "保有中（Home）", "アルバム", "鑑定中", "売却済", "すべて"],
)

# 「アルバム」は保有中(Home/Vault)から選ぶ4列バインダー（ドラッグ並べ替え）の別ビュー
if status == "アルバム":
    render_album(df, store)
    st.stop()
# 「鑑定中」はコレクションCSVではなく PSA申請データ（orders.json）を表示する別ビュー
if status == "鑑定中":
    render_grading()
    st.stop()

active = df[df["Item Status"] == "Active"]
if status == "保有中（Vault）":
    view = active[active["Vault Status"].isin(["Vaulted", "Vault Bound"])].copy()
elif status == "保有中（Home）":
    view = active[active["Vault Status"] == "Unvaulted"].copy()
elif status == "売却済":
    view = df[df["Item Status"] == "Sold"].copy()
else:
    view = df.copy()

keyword = st.sidebar.text_input(
    "キーワード検索", placeholder="リザードン / CHARIZARD / 98769002",
    help="カード名・セット名・品名・証明書番号を横断検索（スペース区切りでAND）",
)
if keyword.strip():
    haystack = (
        view["Item"].fillna("") + " " + view["Subject"].fillna("") + " "
        + view["Set"].fillna("") + " " + view["Variety"].fillna("") + " "
        + view["Cert Number"].fillna("") + " " + view["保管場所"] + " " + view["メモ"]
    ).str.upper()
    for word in keyword.upper().split():
        view = view[haystack.str.contains(word, regex=False, na=False)]
        haystack = haystack[haystack.str.contains(word, regex=False, na=False)]

grades = sorted(df["Grade"].dropna().unique(), key=lambda g: -float(g))
sel_grades = st.sidebar.multiselect("グレード", grades, default=grades)
if sel_grades:
    view = view[view["Grade"].isin(sel_grades)]

# セット候補は現在の絞り込み結果から（件数の多い順）
set_counts = view["Set"].value_counts()
sel_sets = st.sidebar.multiselect(
    "セット", [f"{s}（{n}）" for s, n in set_counts.items()],
    help="未選択なら全セット",
)
if sel_sets:
    picked = {s.rsplit("（", 1)[0] for s in sel_sets}
    view = view[view["Set"].isin(picked)]

years = sorted(int(y) for y in df["year_num"].dropna().unique())
if years:
    y_min, y_max = st.sidebar.select_slider(
        "年", options=years, value=(years[0], years[-1]),
    )
    # 年が読み取れない行は、範囲を絞ったときだけ除外する
    in_range = view["year_num"].between(y_min, y_max)
    if (y_min, y_max) == (years[0], years[-1]):
        in_range |= view["year_num"].isna()
    view = view[in_range]

with st.sidebar.expander("さらに絞り込む"):
    vaults = sorted(view["Vault Status"].dropna().unique())
    sel_vault = st.multiselect("Vault状況", vaults)
    if sel_vault:
        view = view[view["Vault Status"].isin(sel_vault)]

    listings = sorted(view["Listing Status"].dropna().unique())
    sel_listing = st.multiselect("出品状況", listings)
    if sel_listing:
        view = view[view["Listing Status"].isin(sel_listing)]

    est = view["PSA Estimate"].dropna()
    if not est.empty and est.max() > est.min():
        lo, hi = st.slider(
            "PSA推定額（$）", 0, int(est.max()) + 1, (0, int(est.max()) + 1), step=10,
        )
        view = view[view["PSA Estimate"].between(lo, hi) | view["PSA Estimate"].isna()]

    only_unplaced = st.checkbox("保管場所が未記入のものだけ")
    if only_unplaced:
        view = view[view["保管場所"].str.strip() == ""]

    img_filter = st.radio("カード画像", ["こだわらない", "画像ありのみ", "画像なしのみ"])
    if img_filter == "画像ありのみ":
        view = view[view["画像"]]
    elif img_filter == "画像なしのみ":
        view = view[~view["画像"]]

st.sidebar.divider()

with st.sidebar.expander("🖼 カード画像の取得", expanded=False):
    n_cached = len(cached)
    st.progress(
        n_cached / len(df) if len(df) else 0.0,
        text=f"取得済み {n_cached:,} / {len(df):,} 枚",
    )

    token = st.text_input(
        "PSA APIトークン", value=load_token(), type="password",
        help="psacard.com/publicapi で無料発行（PSAアカウントでログイン）。一度入れれば保存されます。",
    )
    if token and token != load_token():
        save_token(token)

    remaining = store.remaining_today()
    st.caption(f"本日の残り取得可能数: **{remaining} / {DAILY_LIMIT} 件**")

    target_label = st.radio(
        "取得する対象", ["絞り込み中のカード", "保有中(Active)すべて"],
        help="画像は証明書番号ごとに保存され、一度取れたら再取得しません。",
    )
    targets = (
        view["Cert Number"].astype(str).tolist()
        if target_label == "絞り込み中のカード"
        else df[df["Item Status"] == "Active"]["Cert Number"].astype(str).tolist()
    )
    todo = [c for c in targets if c not in cached]

    if not token:
        st.info("トークンを入れると取得できます。")
    elif not todo:
        st.success("対象はすべて取得済みです。")
    elif remaining <= 0:
        st.warning("本日の上限に達しました。明日また実行してください。")
    else:
        n = min(len(todo), remaining)
        st.caption(f"未取得 {len(todo):,}枚 → 今回 {n}枚 取得（残りは翌日以降）")
        if st.button(f"▶ {n}枚 取得する", type="primary", width="stretch"):
            bar = st.progress(0.0, text="取得中…")
            result = fetch_many(
                todo, token, store,
                progress=lambda i, total, cert: bar.progress(
                    i / total, text=f"{i}/{total} 取得中… (証明書 {cert})"
                ),
            )
            bar.empty()
            if result["stopped"]:
                st.warning(result["stopped"])
            st.success(f"{result['ok']}枚 取得、{result['ng']}枚 失敗")
            if result["messages"]:
                st.caption("失敗内訳: " + " / ".join(result["messages"][:5]))
            st.rerun()

    failed = store.failed_certs()
    if failed:
        st.caption(f"取得できなかったもの: {len(failed)}件")
        if st.button("失敗記録をクリアして再挑戦可能にする", width="stretch"):
            store.clear_failed()
            st.rerun()

with st.sidebar.expander("📷 画像を手動で追加"):
    st.caption(
        "自分で撮影・スキャンした画像も使えます。"
        "**ファイル名を証明書番号**（例 `98769002.jpg`、裏面は `98769002_back.jpg`）に"
        "してからアップロードしてください。"
    )
    ups = st.file_uploader(
        "画像を選択（複数可）", type=["jpg", "jpeg", "png"],
        accept_multiple_files=True, key="manual_images",
    )
    if ups and st.button("取り込む", width="stretch"):
        all_certs = set(df["Cert Number"].astype(str))
        added, skipped = 0, []
        for f in ups:
            stem = Path(f.name).stem
            cert, back = (stem[:-5], True) if stem.endswith("_back") else (stem, False)
            if cert in all_certs:
                store.save_bytes(cert, f.getvalue(), back=back)
                added += 1
            else:
                skipped.append(f.name)
        st.success(f"{added}枚 取り込みました。")
        if skipped:
            st.warning("証明書番号が一致せず取り込めなかったファイル: " + ", ".join(skipped[:5]))
        st.rerun()

with st.sidebar.expander("📥 データ更新"):
    st.caption("PSA My Collection の最新CSVで丸ごと差し替えます。")
    up = st.file_uploader("CSVを選択", type="csv", label_visibility="collapsed")
    if up is not None and st.button("差し替える", type="primary", width="stretch"):
        CSV_PATH.write_bytes(up.getvalue())
        st.cache_data.clear()
        st.success("更新しました。")
        st.rerun()
    st.caption(
        f"現在のデータ: {len(df):,}件 / "
        f"{datetime.fromtimestamp(CSV_PATH.stat().st_mtime):%Y-%m-%d %H:%M} 取込"
    )


# ---------------------------------------------------------------- KPI

is_sold_view = status == "売却済"
c1, c2, c3, c4 = st.columns(4)
c1.metric("該当枚数", f"{len(view):,} 枚", f"全{len(df):,}枚中")

if is_sold_view:
    sold_total = view["Sold Price"].sum()
    est_total = view["PSA Estimate"].sum()
    c2.metric("売却額 合計", yen(sold_total))
    c3.metric("手取り 合計", yen(view["Sold Proceeds"].sum()))
    c4.metric("現在推定額 合計", yen(est_total), f"売却比 {yen(est_total - sold_total)}")
    fees = view["Sold Fees"].sum()
    rate = fees / sold_total * 100 if sold_total else 0
    st.caption(
        f"手数料 合計 {yen(fees)}（売却額の{rate:.1f}%）"
        "　／　現在推定額はCSVエクスポート時点のPSA推定値"
    )
else:
    c2.metric("PSA推定額 合計", yen(view["PSA Estimate"].sum()))
    c3.metric("1枚あたり平均", yen(view["PSA Estimate"].mean()))
    n10 = (view["Grade"] == "10").sum()
    c4.metric("PSA10", f"{n10:,} 枚", f"{n10 / len(view) * 100:.0f}%" if len(view) else "—")

st.divider()


# ---------------------------------------------------------------- 並べ替え

SORT_MAP = {
    "PSA推定額が高い順": ("PSA Estimate", False),
    "PSA推定額が安い順": ("PSA Estimate", True),
    "年が新しい順": ("year_num", False),
    "年が古い順": ("year_num", True),
    "グレードが高い順": ("grade_num", False),
    "セット順": ("Set", True),
    "カード名順": ("Subject", True),
    "売却日が新しい順": ("Sold Date", False),
    "売却額が高い順": ("Sold Price", False),
}
SOLD_ONLY_SORTS = {"売却日が新しい順", "売却額が高い順"}


def sort_options() -> list:
    """売却済ビューのときだけ売却関連の並べ替えも出す。"""
    return [k for k in SORT_MAP if is_sold_view or k not in SOLD_ONLY_SORTS]


def apply_sort(frame: pd.DataFrame, key: str) -> pd.DataFrame:
    by, asc = SORT_MAP[key]
    return frame.sort_values(by, ascending=asc, na_position="last")


# ---------------------------------------------------------------- タブ

tab_gallery, tab_list, tab_place, tab_stats = st.tabs(
    ["🖼 ギャラリー", "📋 一覧", "📦 保管場所", "📊 集計"]
)

with tab_gallery:
    if view.empty:
        st.info("条件に合うカードがありません。絞り込みを緩めてください。")
    else:
        top_bar = st.columns([3, 2, 2, 2])
        g_sort = top_bar[0].selectbox("並べ替え", sort_options(), key="gallery_sort")
        per_row = top_bar[1].select_slider("1行の枚数", [3, 4, 5, 6, 8], value=5)
        page_size = top_bar[2].select_slider("1ページの枚数", [20, 40, 60, 100], value=40)
        n_pages = max(1, -(-len(view) // page_size))
        page = top_bar[3].number_input(
            f"ページ（全{n_pages}）", 1, n_pages, 1, key="gallery_page"
        )

        page_df = apply_sort(view, g_sort).iloc[(page - 1) * page_size : page * page_size]
        n_missing = (~page_df["画像"]).sum()
        if n_missing:
            st.caption(
                f"このページの {n_missing} 枚は画像が未取得です。"
                "サイドバーの「🖼 カード画像の取得」から取り込めます。"
            )

        for start in range(0, len(page_df), per_row):
            chunk = page_df.iloc[start : start + per_row]
            for col, (_, card) in zip(st.columns(per_row), chunk.iterrows()):
                cert = str(card["Cert Number"])
                with col:
                    img = store.thumb(cert)
                    if img:
                        st.image(img, width="stretch")
                    else:
                        st.markdown(
                            "<div style='aspect-ratio:5/7;border:1px dashed #999;"
                            "border-radius:6px;display:flex;align-items:center;"
                            "justify-content:center;color:#999;font-size:12px;'>"
                            "画像なし</div>",
                            unsafe_allow_html=True,
                        )
                    if is_sold_view:
                        price_html = (
                            f"売却 {yen(card['Sold Price'])}　"
                            f"<span style='color:#16a34a'>現在推定 {yen(card['PSA Estimate'])}</span>"
                        )
                    else:
                        price_html = yen(card["PSA Estimate"])
                    place = f"📦 {card['保管場所']}" if card["保管場所"].strip() else ""
                    st.markdown(
                        f"<div style='font-size:0.8rem;line-height:1.35'>"
                        f"<b>PSA {card['Grade']}</b>　{price_html}<br>"
                        f"{card['Subject'] or ''}<br>"
                        f"<span style='font-size:11px;color:#888'>"
                        f"{card['Year'] or ''} {card['Set'] or ''}<br>{place}</span><br>"
                        f"<a href='{card['cert_url']}' target='_blank'>証明書 {cert}</a>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    full = store.source(cert)
                    if full:
                        with st.expander("拡大"):
                            st.image(full, width="stretch")
                    back = store.source(cert, back=True)
                    if back:
                        with st.expander("裏面"):
                            st.image(back, width="stretch")
            st.divider()


with tab_list:
    if view.empty:
        st.info("条件に合うカードがありません。絞り込みを緩めてください。")
    else:
        cols = ["Grade", "Year", "Set", "Card Number", "Subject", "Variety", "保管場所"]
        cols += (
            ["Sold Price", "PSA Estimate", "Sold Proceeds", "Sold Date", "Sold On"]
            if is_sold_view
            else ["PSA Estimate", "Vault Status", "Listing Status", "Listing Price"]
        )
        cols += ["Cert Number", "cert_url"]

        sort_key = st.selectbox("並べ替え", sort_options(), key="list_sort")
        shown = apply_sort(view, sort_key)[cols]

        st.dataframe(
            shown,
            width="stretch",
            hide_index=True,
            height=560,
            column_config={
                "cert_url": st.column_config.LinkColumn(
                    "PSA", display_text="照会", width="small"
                ),
                "PSA Estimate": st.column_config.NumberColumn("PSA推定額", format="$%d"),
                "Listing Price": st.column_config.NumberColumn("出品価格", format="$%d"),
                "Sold Price": st.column_config.NumberColumn("売却額", format="$%d"),
                "Sold Proceeds": st.column_config.NumberColumn("手取り", format="$%d"),
                "Sold Date": st.column_config.DateColumn("売却日", format="YYYY-MM-DD"),
                **{k: v for k, v in LABELS.items() if k in cols and k != "cert_url"},
            },
        )

        st.download_button(
            "この絞り込み結果をCSVでダウンロード",
            shown.drop(columns=["cert_url"]).to_csv(index=False).encode("utf-8-sig"),
            file_name=f"psa_collection_{datetime.now():%Y%m%d}.csv",
            mime="text/csv",
        )

with tab_place:
    st.caption(
        "現物がどこにあるかを記録します。左の絞り込みで対象を出してから編集し、"
        "「保存」を押してください。証明書番号にひも付いて保存され、CSVを差し替えても残ります。"
    )
    if view.empty:
        st.info("編集対象がありません。")
    else:
        editable = view[
            ["Cert Number", "Grade", "Year", "Set", "Subject", "保管場所", "メモ"]
        ].sort_values(["Set", "Subject"])

        edited = st.data_editor(
            editable,
            width="stretch",
            hide_index=True,
            height=520,
            disabled=["Cert Number", "Grade", "Year", "Set", "Subject"],
            column_config={
                "保管場所": st.column_config.TextColumn(
                    "保管場所", help="例: バインダーA / 金庫 / PSA Vault", width="medium"
                ),
                "メモ": st.column_config.TextColumn("メモ", width="large"),
                **{k: v for k, v in LABELS.items() if k in editable.columns},
            },
            key="place_editor",
        )

        left, right = st.columns([1, 4])
        if left.button("💾 保存", type="primary"):
            for _, row in edited.iterrows():
                cert = str(row["Cert Number"])
                place, memo = str(row["保管場所"] or ""), str(row["メモ"] or "")
                if place.strip() or memo.strip():
                    notes[cert] = {"place": place, "memo": memo}
                else:
                    notes.pop(cert, None)
            save_notes(notes)
            st.success(f"{len(notes):,}枚分の保管情報を保存しました。")
            st.rerun()

        recorded = (view["保管場所"].str.strip() != "").sum()
        right.caption(f"表示中 {len(view):,}枚のうち {recorded:,}枚に保管場所を記録済み")

with tab_stats:
    value_col = "Sold Price" if is_sold_view else "PSA Estimate"
    value_label = "売却額" if is_sold_view else "PSA推定額"

    left, right = st.columns(2)
    with left:
        st.subheader("セット別")
        by_set = (
            view.groupby("Set")
            .agg(枚数=("Cert Number", "count"), 金額=(value_col, "sum"))
            .sort_values("金額", ascending=False)
            .head(20)
        )
        st.bar_chart(by_set["金額"], horizontal=True, height=460)
        st.caption(f"{value_label}が大きい上位20セット")

    with right:
        st.subheader("グレード別")
        by_grade = (
            view.groupby("Grade")
            .agg(枚数=("Cert Number", "count"), 金額=(value_col, "sum"))
            .sort_index(key=lambda i: i.map(float), ascending=False)
        )
        st.dataframe(
            by_grade.style.format({"金額": "${:,.0f}"}), width="stretch"
        )

        st.subheader("年別")
        dated = view[view["year_num"].notna()].copy()
        dated["年"] = dated["year_num"].astype(int).astype(str)
        by_year = (
            dated.groupby("年")
            .agg(枚数=("Cert Number", "count"), 金額=(value_col, "sum"))
            .sort_index()
        )
        st.bar_chart(by_year["金額"], height=240)

    st.subheader(f"{value_label} 上位30枚")
    top = view.nlargest(30, value_col)[
        ["Grade", "Year", "Set", "Subject", "Variety", value_col, "保管場所", "cert_url"]
    ]
    st.dataframe(
        top,
        width="stretch",
        hide_index=True,
        column_config={
            "cert_url": st.column_config.LinkColumn("PSA", display_text="照会", width="small"),
            value_col: st.column_config.NumberColumn(value_label, format="$%d"),
            **{k: v for k, v in LABELS.items() if k in top.columns and k != "cert_url"},
        },
    )
