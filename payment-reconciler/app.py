#!/usr/bin/env python3
"""
入金突合（消込）システム - Streamlit UI
"""

import io
import os
import csv
import tempfile
from pathlib import Path

import streamlit as st

from match_payments import (
    HAS_PYKAKASI,
    load_bank_data,
    load_name_mapping,
    save_name_mapping,
    load_rent_list,
    match_payments,
    update_excel,
    NAME_MAPPING_FILE,
)

# 漢字→カナ変換が使えないと、突合の候補が減って**黙って一致率が下がる**。
# 落ちないので気づけない。画面に出して分かるようにする。
_PYKAKASI_WARNING = not HAS_PYKAKASI

st.set_page_config(
    page_title="入金突合システム",
    page_icon="💴",
    layout="wide",
)

st.title("💴 入金突合（消込）システム")

if _PYKAKASI_WARNING:
    st.warning(
        "**pykakasi が入っていないため、漢字の契約者名をカナに変換できません。**\n\n"
        "動作はしますが、突合の候補が減るぶん**一致率が下がります**（エラーにはなりません）。"
        "`pip install -r requirements.txt` で導入してください。"
    )
st.caption("銀行入金データ × 入金一覧Excelを自動突合")

# ─────────────────────────────────────────────────
# サイドバー: ファイルアップロード
# ─────────────────────────────────────────────────
with st.sidebar:
    st.header("📂 ファイル選択")

    bank_files = st.file_uploader(
        "銀行CSV（最大5ファイル）",
        type=["csv"],
        accept_multiple_files=True,
        help="りそな・UFJ形式を自動判定",
        key="bank",
    )

    rent_files = st.file_uploader(
        "入金一覧Excel（最大20ファイル）",
        type=["xlsx"],
        accept_multiple_files=True,
        help="複数マンション同時処理可",
        key="rent",
    )

    st.divider()

    mapping_file = st.file_uploader(
        "名義変換CSV（任意）",
        type=["csv"],
        help="前回保存したname_mapping.csvを読み込む",
        key="mapping",
    )

    run_btn = st.button(
        "▶ 突合実行",
        type="primary",
        use_container_width=True,
        disabled=(not bank_files or not rent_files),
    )

# ─────────────────────────────────────────────────
# 使い方ガイド（ファイル未選択時）
# ─────────────────────────────────────────────────
if not bank_files and not rent_files:
    st.info("""
**使い方**
1. 左サイドバーから **銀行CSV**（りそな・UFJ）をアップロード
2. **入金一覧Excel** をアップロード
3. **▶ 突合実行** ボタンを押す
4. 結果を確認し、更新済みExcelをダウンロード

---
**突合ロジック**
| 優先度 | 判定 | 色 |
|--------|------|----|
| ① | 完全一致（名義＋金額） | 🟢 緑 |
| ② | 表記揺れ一致（name_mapping経由） | 🟢 緑 |
| ③ | 分割入金（同日・同名義の合算） | 🟡 黄 |
| ④ | 金額不一致（要確認） | 🔴 赤 |
| × | 未突合 | ⬜ なし |
""")
    st.stop()

# ─────────────────────────────────────────────────
# 実行
# ─────────────────────────────────────────────────
if not run_btn:
    st.info("ファイルを選択して **▶ 突合実行** を押してください")
    st.stop()

with st.spinner("突合処理中..."):

    # 銀行CSVを一時ファイルに書き出し
    tmp_bank_paths = []
    for f in bank_files[:5]:
        tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
        tmp.write(f.read())
        tmp.close()
        tmp_bank_paths.append(tmp.name)
        # アップロードファイルにファイル名を付与（format判定用）
        Path(tmp.name)  # パスはそのまま
        import os
        os.rename(tmp.name, tmp.name.replace(".csv", f"_{f.name}"))
        tmp_bank_paths[-1] = tmp.name.replace(".csv", f"_{f.name}")

    bank_records = load_bank_data(tmp_bank_paths)

    # 名義マスタ
    if mapping_file:
        tmp_map = tempfile.NamedTemporaryFile(suffix=".csv", delete=False,
                                               mode='wb')
        tmp_map.write(mapping_file.read())
        tmp_map.close()
        name_mapping = load_name_mapping(Path(tmp_map.name))
    else:
        name_mapping = load_name_mapping(NAME_MAPPING_FILE)

    # 銀行データ件数表示
    st.success(
        f"銀行データ: **{len(bank_records)}件** の振込入金を読み込みました"
        f"（{len(bank_files)}ファイル）"
    )

    all_rent_records = []
    all_results_by_file = []

    # 各Excelを処理
    for rent_f in rent_files[:20]:
        tmp_xl = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        tmp_xl.write(rent_f.read())
        tmp_xl.close()
        tmp_xl_path = tmp_xl.name

        try:
            cols, rent_records = load_rent_list(tmp_xl_path)
        except Exception as e:
            st.error(f"{rent_f.name}: {e}")
            continue

        results = match_payments(bank_records, rent_records, name_mapping)
        all_rent_records.extend(rent_records)

        # Excel更新（メモリ上で完結）
        out_path, n_updated = update_excel(tmp_xl_path, cols, results)
        with open(out_path, "rb") as fp:
            excel_bytes = fp.read()

        all_results_by_file.append({
            "filename":     rent_f.name,
            "out_name":     rent_f.name.replace(".xlsx", "_updated.xlsx"),
            "results":      results,
            "excel_bytes":  excel_bytes,
            "n_updated":    n_updated,
        })

    # 名義マスタを更新保存
    save_name_mapping(NAME_MAPPING_FILE, name_mapping, all_rent_records)

# ─────────────────────────────────────────────────
# 結果表示
# ─────────────────────────────────────────────────
for file_data in all_results_by_file:
    filename = file_data["filename"]
    results  = file_data["results"]

    exact     = [r for r in results if r["status"] == "exact"]
    split     = [r for r in results if r["status"] == "split"]
    mismatch  = [r for r in results if r["status"] == "amount_mismatch"]
    unmatched = [r for r in results if r["status"] == "unmatched"]

    st.subheader(f"📄 {filename}")

    # KPIカード
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("① 完全一致", f"{len(exact)}件", delta=None)
    col2.metric("③ 分割入金", f"{len(split)}件", delta=None)
    col3.metric("④ 金額不一致", f"{len(mismatch)}件",
                delta="要確認" if mismatch else None,
                delta_color="inverse")
    col4.metric("× 未突合", f"{len(unmatched)}件")

    # ─ 分割入金 ─
    if split:
        with st.expander(f"③ 分割入金  ({len(split)}件)", expanded=True):
            rows = []
            for r in split:
                dt = r["match_date"].strftime("%m/%d") if r["match_date"] else "-"
                amounts = " + ".join(f"{b['amount']:,}" for b in r["bank_records"])
                rows.append({
                    "部屋":   r["rent"]["room"],
                    "契約者": r["rent"]["tenant"],
                    "入金日": dt,
                    "内訳":   amounts,
                    "合計":   f"{r['matched_amount']:,}円",
                })
            st.table(rows)

    # ─ 金額不一致 ─
    if mismatch:
        with st.expander(f"④ 金額不一致  ({len(mismatch)}件) ⚠️", expanded=True):
            rows = []
            for r in mismatch:
                dt = r["match_date"].strftime("%m/%d") if r["match_date"] else "-"
                rows.append({
                    "部屋":   r["rent"]["room"],
                    "契約者": r["rent"]["tenant"],
                    "入金日": dt,
                    "請求金額": f"{r['rent']['amount']:,}円",
                    "入金金額": f"{r['matched_amount']:,}円",
                    "差異":   f"{r['diff']:+,}円",
                })
            st.table(rows)

    # ─ 未突合 ─
    if unmatched:
        with st.expander(f"× 未突合  ({len(unmatched)}件)"):
            rows = []
            for r in unmatched:
                rows.append({
                    "部屋":   r["rent"]["room"],
                    "契約者": r["rent"]["tenant"],
                    "請求金額": f"{r['rent']['amount']:,}円",
                })
            st.table(rows)

    # ─ ダウンロード ─
    st.download_button(
        label=f"⬇ {file_data['out_name']} をダウンロード",
        data=file_data["excel_bytes"],
        file_name=file_data["out_name"],
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    st.divider()

# ─────────────────────────────────────────────────
# 名義マスタダウンロード
# ─────────────────────────────────────────────────
if NAME_MAPPING_FILE.exists():
    st.subheader("📋 名義変換マスタ")
    st.caption("bank_kana列を修正して次回アップロードすると②表記揺れ突合が改善します")

    with open(NAME_MAPPING_FILE, encoding="utf-8-sig") as f:
        mapping_csv_bytes = f.read().encode("utf-8-sig")

    col_a, col_b = st.columns([2, 1])
    with col_a:
        rows = list(csv.DictReader(io.StringIO(mapping_csv_bytes.decode("utf-8-sig"))))
        st.dataframe(rows, use_container_width=True, height=300)
    with col_b:
        st.download_button(
            "⬇ name_mapping.csv をダウンロード",
            data=mapping_csv_bytes,
            file_name="name_mapping.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.info("修正後は左サイドバーの「名義変換CSV」欄にアップロードして再実行")
