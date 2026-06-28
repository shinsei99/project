"""決済案内書 自動作成＆清算監査システム。

重要事項説明書PDFと固定資産税評価証明書PDFをアップロードするだけで、
売買条件・税額・宛名を自動パースし、固都税／管理費等の日割りを1円単位で
計算。買主用・売主用の決済案内書（Excel）を一括生成する。
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from models.settlement_data import (
    SettlementData,
    START_MONTH_KANTO,
    START_MONTH_KANSAI,
)
from services.pdf_parser import (
    parse_explanation,
    parse_tax_certificate,
    to_amount,
    PdfExtractionError,
)
from services.settlement_engine import build_documents, compute_tax, compute_fee
from services.excel_generator import build as build_excel


st.set_page_config(page_title="決済案内書 自動作成", page_icon="🏦", layout="wide")

st.title("🏦 決済案内書 自動作成＆清算監査システム")
st.caption(
    "重要事項説明書PDFと固定資産税評価証明書PDFをアップロードするだけで、"
    "固都税・管理費等の日割りを自動計算し、買主用・売主用の決済案内書(Excel)を生成します。"
)


# ---- セッション初期化（パース結果のプリフィル保持） ----
DEFAULTS = {
    "sale_price": 0, "deposit": 0, "mgmt_fee_monthly": 0, "repair_fee_monthly": 0,
    "seller_name": "", "buyer_name": "", "property_location": "",
    "fixed_asset_tax": 0, "city_planning_tax": 0, "tax_year_label": "",
}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(f"pf_{k}", v)


# ============================================================
# 1. PDFアップロード ＆ 自動パース
# ============================================================
st.header("1. 書類アップロード")
c1, c2 = st.columns(2)
with c1:
    file_exp = st.file_uploader("重要事項説明書 / 売買契約書（PDF）", type="pdf", key="up_exp")
with c2:
    file_tax = st.file_uploader("固定資産税 評価証明書 / 納税通知書（PDF）", type="pdf", key="up_tax")

if st.button("🔍 PDFを自動解析してフォームに反映", type="primary", use_container_width=True):
    if not file_exp and not file_tax:
        st.warning("少なくとも1つのPDFをアップロードしてください。")
    else:
        try:
            if file_exp:
                with st.spinner("重要事項説明書を解析中…（数十秒かかります）"):
                    r = parse_explanation(file_exp.getvalue())
                st.session_state.pf_sale_price = to_amount(r.get("売買代金"))
                st.session_state.pf_deposit = to_amount(r.get("手付金"))
                st.session_state.pf_mgmt_fee_monthly = to_amount(r.get("管理費月額"))
                st.session_state.pf_repair_fee_monthly = to_amount(r.get("修繕積立金月額"))
                st.session_state.pf_seller_name = str(r.get("売主氏名", "") or "")
                st.session_state.pf_buyer_name = str(r.get("買主氏名", "") or "")
                st.session_state.pf_property_location = str(r.get("物件所在", "") or "")
            if file_tax:
                with st.spinner("評価証明書を解析中…（数十秒かかります）"):
                    t = parse_tax_certificate(file_tax.getvalue())
                st.session_state.pf_fixed_asset_tax = to_amount(t.get("固定資産税相当額"))
                st.session_state.pf_city_planning_tax = to_amount(t.get("都市計画税相当額"))
                st.session_state.pf_tax_year_label = str(t.get("年度", "") or "")
            st.success("解析が完了しました。下のフォームに反映しています。内容をご確認ください。")
        except PdfExtractionError as e:
            st.error(str(e))


# ============================================================
# 2. 売買条件・税額（パース結果を編集可能に表示）
# ============================================================
st.header("2. 売買条件・税額の確認")
st.caption("AI解析の結果です。誤りがあればこの場で修正してください。")

cc1, cc2 = st.columns(2)
with cc1:
    st.subheader("売買条件（重説）")
    sale_price = st.number_input("売買代金（円）", min_value=0, step=10000, value=int(st.session_state.pf_sale_price))
    deposit = st.number_input("手付金（円）", min_value=0, step=10000, value=int(st.session_state.pf_deposit))
    mgmt_fee = st.number_input("管理費（月額・円）", min_value=0, step=500, value=int(st.session_state.pf_mgmt_fee_monthly))
    repair_fee = st.number_input("修繕積立金（月額・円）", min_value=0, step=500, value=int(st.session_state.pf_repair_fee_monthly))
    seller_name = st.text_input("売主氏名", value=st.session_state.pf_seller_name)
    buyer_name = st.text_input("買主氏名", value=st.session_state.pf_buyer_name)
    property_location = st.text_input("物件所在", value=st.session_state.pf_property_location)

with cc2:
    st.subheader("税額（評価証明書）")
    fixed_asset_tax = st.number_input("固定資産税相当額（年額・円）", min_value=0, step=100, value=int(st.session_state.pf_fixed_asset_tax))
    city_planning_tax = st.number_input("都市計画税相当額（年額・円）", min_value=0, step=100, value=int(st.session_state.pf_city_planning_tax))
    tax_year_label = st.text_input("課税年度", value=st.session_state.pf_tax_year_label, placeholder="例: 令和6年度")
    st.metric("固都税 年間総額（T）", f"¥{fixed_asset_tax + city_planning_tax:,}")


# ============================================================
# 3. 決済条件
# ============================================================
st.header("3. 決済条件")
dc1, dc2, dc3 = st.columns(3)
with dc1:
    settlement_date = st.date_input("決済日（引き渡し日）", value=date.today())
with dc2:
    region = st.radio(
        "固都税の起算日",
        ["4月1日：関西", "1月1日：関東"],
        help="売主・買主の固都税負担を日割りする基準日。地域慣習で選択します。",
    )
    start_month = START_MONTH_KANTO if region.startswith("1月") else START_MONTH_KANSAI
with dc3:
    fee_mode = st.radio(
        "管理費等の清算方法",
        ["当月日割り分のみ", "当月日割り ＋ 翌月1ヶ月分 前払い"],
        help="管理組合への引落タイミングにより翌月分を先出し清算する場合に選択します。",
    )
    next_month_fee = fee_mode.startswith("当月日割り ＋")

st.subheader("諸費用（任意・手動微調整）")
ec1, ec2, ec3, ec4 = st.columns(4)
with ec1:
    buyer_brokerage = st.number_input("買主 仲介手数料", min_value=0, step=10000, value=0)
with ec2:
    buyer_registration = st.number_input("買主 登記費用（移転）", min_value=0, step=10000, value=0)
with ec3:
    seller_brokerage = st.number_input("売主 仲介手数料", min_value=0, step=10000, value=0)
with ec4:
    seller_registration = st.number_input("売主 登記費用（抹消等）", min_value=0, step=10000, value=0)


# ---- データ集約 ----
data = SettlementData(
    sale_price=sale_price,
    deposit=deposit,
    mgmt_fee_monthly=mgmt_fee,
    repair_fee_monthly=repair_fee,
    seller_name=seller_name,
    buyer_name=buyer_name,
    property_location=property_location,
    fixed_asset_tax=fixed_asset_tax,
    city_planning_tax=city_planning_tax,
    tax_year_label=tax_year_label,
    settlement_date=settlement_date,
    start_month=start_month,
    next_month_fee=next_month_fee,
    buyer_brokerage=buyer_brokerage,
    buyer_registration=buyer_registration,
    seller_brokerage=seller_brokerage,
    seller_registration=seller_registration,
)


# ============================================================
# 4. 清算プレビュー ＆ 出力
# ============================================================
st.header("4. 清算プレビュー")

if sale_price <= 0:
    st.info("売買代金を入力（またはPDFを解析）すると清算結果が表示されます。")
else:
    buyer_doc, seller_doc = build_documents(data)
    tax = compute_tax(data)
    fee = compute_fee(data)

    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("固都税 清算金（買主負担）", f"¥{tax['amount']:,}", help=tax["note"] or None)
    mc2.metric("管理費等 清算金", f"¥{fee['amount']:,}", help=fee["note"] or None)
    mc3.metric("売買残代金", f"¥{data.remaining_price:,}")

    pc1, pc2 = st.columns(2)
    with pc1:
        st.subheader(f"買主用：{buyer_doc.name or '買主'} 様")
        df_b = pd.DataFrame(
            [{"項目": l.label, "金額": l.amount, "内訳": l.note} for l in buyer_doc.lines]
        )
        st.dataframe(df_b, hide_index=True, use_container_width=True,
                     column_config={"金額": st.column_config.NumberColumn(format="¥%d")})
        st.metric(buyer_doc.total_label, f"¥{buyer_doc.total:,}")
    with pc2:
        st.subheader(f"売主用：{seller_doc.name or '売主'} 様")
        df_s = pd.DataFrame(
            [{"項目": l.label, "金額": l.amount, "内訳": l.note} for l in seller_doc.lines]
        )
        st.dataframe(df_s, hide_index=True, use_container_width=True,
                     column_config={"金額": st.column_config.NumberColumn(format="¥%d")})
        st.metric(seller_doc.total_label, f"¥{seller_doc.total:,}")
        for n in seller_doc.notes:
            st.warning(n)

    st.divider()
    xlsx = build_excel(data, buyer_doc, seller_doc)
    fname = f"決済案内書_{property_location or '物件'}_{settlement_date}.xlsx"
    st.download_button(
        "📥 決済案内書（買主用・売主用）をExcelでダウンロード",
        data=xlsx,
        file_name=fname,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
    )
