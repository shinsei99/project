# -*- coding: utf-8 -*-
"""
横断ファイル検索ブラウザ (file-finder)
社内共有ドライブの棚卸しExcel（全ファイル一覧.xlsx）を読み込み、
11,000件超のファイルをフォルダ階層を辿らず横断で即検索・絞り込みするツール。
Streamlit / port 8520
"""
from __future__ import annotations

import io
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).parent
DEFAULT_XLSX = APP_DIR / "data" / "全ファイル一覧.xlsx"
DEFAULT_XLSX.parent.mkdir(exist_ok=True)

st.set_page_config(page_title="横断ファイル検索ブラウザ", page_icon="🔍", layout="wide")

# ------------------------------------------------------------------ データ読込
COLS = ["種別", "フルパス", "名前", "親フォルダ", "階層", "拡張子", "サイズ", "サイズ(bytes)", "更新日時"]


def _norm(s: str) -> str:
    """検索用の正規化：全角→半角、カタカナ半角→全角、小文字化。"""
    if not s:
        return ""
    return unicodedata.normalize("NFKC", str(s)).lower()


def _extract_property(path: str) -> str:
    """フルパスから物件名らしきトークンを推定（物件資料/か/○○/... の3階層目など）。"""
    if not path:
        return ""
    parts = [p for p in str(path).replace("\\", "/").split("/") if p]
    # 「物件資料/<かな>/物件名/...」パターン
    for i, p in enumerate(parts[:-1]):
        if "物件資料" in p and i + 2 < len(parts) and len(parts[i + 1]) <= 2:
            return parts[i + 2]
        if "物件資料" in p and i + 1 < len(parts):
            return parts[i + 1]
    # マンション/駐車場/その他物件 直下
    for key in ("マンション", "駐車場", "その他物件", "ビル", "アパート"):
        if key in parts:
            idx = parts.index(key)
            if idx + 1 < len(parts):
                return parts[idx + 1]
    return ""


@st.cache_data(show_spinner="棚卸しデータを読み込み中…")
def load_data(src, mtime_key: float) -> pd.DataFrame:
    """全シートを1つのDataFrameへ結合。src はパス or BytesIO。"""
    xls = pd.ExcelFile(src, engine="openpyxl")
    frames = []
    for sheet in xls.sheet_names:
        df = xls.parse(sheet, dtype=str)
        df = df.reindex(columns=COLS)  # 列順を固定
        df["カテゴリ"] = sheet
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)

    df["bytes"] = pd.to_numeric(df["サイズ(bytes)"], errors="coerce").fillna(0).astype("int64")
    df["更新日時_dt"] = pd.to_datetime(df["更新日時"], errors="coerce")
    df["拡張子"] = df["拡張子"].fillna("").str.lower()
    df["種別"] = df["種別"].fillna("")
    df["名前"] = df["名前"].fillna("")
    df["フルパス"] = df["フルパス"].fillna("")
    df["親フォルダ"] = df["親フォルダ"].fillna("")
    df["カテゴリ"] = df["カテゴリ"].fillna("")
    df["物件"] = df["フルパス"].map(_extract_property)
    # 実際の共有ドライブ上のパスは、カテゴリ名（トップ階層フォルダ）が手前に付く
    df["表示パス"] = df["カテゴリ"].fillna("") + "/" + df["フルパス"].fillna("")
    df["表示親フォルダ"] = df.apply(
        lambda r: (r["カテゴリ"] + ("/" + r["親フォルダ"] if r["親フォルダ"] else "")), axis=1
    )
    # 検索用インデックス（名前＋カテゴリ込みフルパス）
    df["_search"] = (df["名前"].fillna("") + " " + df["表示パス"]).map(_norm)
    return df


def human_size(b: int) -> str:
    b = float(b or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024 or unit == "GB":
            return f"{b:.1f} {unit}" if unit != "B" else f"{int(b)} B"
        b /= 1024
    return f"{b:.1f} GB"


# ------------------------------------------------------------------ ヘッダー
st.title("🔍 横断ファイル検索ブラウザ")

# データソース。data/全ファイル一覧.xlsx があれば自動読込。アップロードすると上書き保存して永続化。
has_default = DEFAULT_XLSX.exists()
exp_label = "📁 棚卸しExcelを更新する" if has_default else "📁 棚卸しExcel（全ファイル一覧.xlsx）をアップロードしてください"
with st.expander(exp_label, expanded=not has_default):
    if not has_default:
        st.info("**全ファイル一覧.xlsx** を選択してください。一度アップロードすると次回から自動で読み込まれます。")
    else:
        mtime = datetime.fromtimestamp(DEFAULT_XLSX.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        st.caption(f"保存済みデータ: `{DEFAULT_XLSX.name}`　最終更新: {mtime}")
    uploaded = st.file_uploader("全ファイル一覧.xlsx を選択（アップロードすると上書き保存）", type=["xlsx"])
    if uploaded is not None:
        DEFAULT_XLSX.write_bytes(uploaded.getvalue())
        st.success(f"✅ 保存しました → `{DEFAULT_XLSX}`　次回から自動で読み込まれます。")
        st.cache_data.clear()

if DEFAULT_XLSX.exists():
    data = load_data(str(DEFAULT_XLSX), DEFAULT_XLSX.stat().st_mtime)
else:
    st.stop()

files = data[data["種別"] == "ファイル"].copy()

st.caption(
    f"共有ドライブ棚卸し：{len(files):,} ファイル / "
    f"{human_size(int(files['bytes'].sum()))}"
)

# ------------------------------------------------------------------ 検索・絞り込みUI
q = st.text_input(
    "検索（スペース区切りでAND。ファイル名・フォルダパス・物件名を対象）",
    placeholder="例：グレイスフル 重説   /   点検 報告書 2024",
).strip()

c1, c2, c3, c4 = st.columns([1.3, 1.3, 1.2, 1.2])
with c1:
    cats = sorted(files["カテゴリ"].dropna().unique().tolist())
    sel_cat = st.multiselect("カテゴリ", cats, default=[])
with c2:
    ext_counts = files["拡張子"].value_counts()
    ext_opts = [f"{e or '(なし)'} ({n})" for e, n in ext_counts.items()]
    ext_map = {f"{e or '(なし)'} ({n})": e for e, n in ext_counts.items()}
    sel_ext_lbl = st.multiselect("拡張子", ext_opts, default=[])
    sel_ext = [ext_map[l] for l in sel_ext_lbl]
with c3:
    valid_dt = files["更新日時_dt"].dropna()
    min_d = valid_dt.min().date() if not valid_dt.empty else date(2000, 1, 1)
    max_d = valid_dt.max().date() if not valid_dt.empty else date.today()
    dr = st.date_input("更新日 範囲", value=(min_d, max_d), min_value=min_d, max_value=max_d)
with c4:
    sort_key = st.selectbox("並び替え", ["更新日（新しい順）", "更新日（古い順）", "サイズ（大きい順）", "名前順"])

# ------------------------------------------------------------------ フィルタ適用
res = files
if q:
    for tok in _norm(q).split():
        res = res[res["_search"].str.contains(re.escape(tok), na=False)]
if sel_cat:
    res = res[res["カテゴリ"].isin(sel_cat)]
if sel_ext:
    res = res[res["拡張子"].isin(sel_ext)]
if isinstance(dr, (tuple, list)) and len(dr) == 2:
    lo = pd.Timestamp(dr[0])
    hi = pd.Timestamp(dr[1]) + pd.Timedelta(days=1)
    m = res["更新日時_dt"].notna() & (res["更新日時_dt"] >= lo) & (res["更新日時_dt"] < hi)
    res = res[m]

if sort_key == "更新日（新しい順）":
    res = res.sort_values("更新日時_dt", ascending=False, na_position="last")
elif sort_key == "更新日（古い順）":
    res = res.sort_values("更新日時_dt", ascending=True, na_position="last")
elif sort_key == "サイズ（大きい順）":
    res = res.sort_values("bytes", ascending=False)
else:
    res = res.sort_values("名前")

# ------------------------------------------------------------------ 結果サマリ
st.markdown(
    f"**{len(res):,} 件** ヒット　/　合計 {human_size(int(res['bytes'].sum()))}"
    + (f"　（全{len(files):,}件中）" if q or sel_cat or sel_ext else "")
)

if res.empty:
    st.info("条件に一致するファイルがありません。キーワードや絞り込みを緩めてください。")
    st.stop()

# 表示件数の上限（描画負荷対策）
MAX_ROWS = 500
show = res.head(MAX_ROWS)
if len(res) > MAX_ROWS:
    st.caption(f"※ 先頭 {MAX_ROWS:,} 件を表示中。キーワードで絞り込むと全件見えます。")

# ------------------------------------------------------------------ 結果テーブル
view = pd.DataFrame({
    "名前": show["名前"].values,
    "物件": show["物件"].values,
    "カテゴリ": show["カテゴリ"].values,
    "種類": show["拡張子"].replace("", "(なし)").values,
    "サイズ": [human_size(b) for b in show["bytes"].values],
    "更新日": show["更新日時_dt"].dt.strftime("%Y-%m-%d").fillna("").values,
    "フルパス": show["表示パス"].values,
})

event = st.dataframe(
    view,
    use_container_width=True,
    hide_index=True,
    height=460,
    on_select="rerun",
    selection_mode="single-row",
    column_config={
        "名前": st.column_config.TextColumn(width="large"),
        "フルパス": st.column_config.TextColumn(width="large"),
        "サイズ": st.column_config.TextColumn(width="small"),
        "更新日": st.column_config.TextColumn(width="small"),
    },
)

# ------------------------------------------------------------------ 選択行の詳細（パスコピー）
sel_rows = event.selection.rows if event and event.selection else []
if sel_rows:
    row = show.iloc[sel_rows[0]]
    st.markdown("---")
    st.subheader(f"📄 {row['名前']}")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("カテゴリ", row["カテゴリ"])
    m2.metric("サイズ", human_size(int(row["bytes"])))
    m3.metric("種類", row["拡張子"] or "(なし)")
    m4.metric("更新日", row["更新日時_dt"].strftime("%Y-%m-%d") if pd.notna(row["更新日時_dt"]) else "—")
    if row["物件"]:
        st.caption(f"推定物件：{row['物件']}")
    st.write("**フルパス**（右上のアイコンでコピー → 共有ドライブで開く）")
    st.code(row["表示パス"], language="text")
    st.write("**親フォルダ**")
    st.code(row["表示親フォルダ"], language="text")
else:
    st.caption("💡 行をクリックすると、フルパスをコピーできる詳細パネルが開きます。")

# ------------------------------------------------------------------ ダウンロード
st.markdown("---")
csv = view.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "🔽 この検索結果をCSVで書き出し",
    data=csv,
    file_name="検索結果.csv",
    mime="text/csv",
)
