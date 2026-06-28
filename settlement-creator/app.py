"""決済案内書・賃貸精算 自動作成＆清算監査システム。

【売買】重説PDF＋固定資産税評価証明書PDFから、固都税・管理費等の日割りを
自動計算し、買主用・売主用の決済案内書(Excel)を生成。
【賃貸】賃貸借契約書/重説PDFから、入居者用の初期費用請求明細と、オーナー用の
初回送金精算明細(Excel)を生成。発行企業はサイドバーで登録・切替できる。
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from models.settlement_data import SettlementData, START_MONTH_KANTO, START_MONTH_KANSAI
from models.rental_data import RentalData, RentLine
from services.pdf_parser import (
    parse_explanation, parse_tax_certificate, parse_rental_explanation,
    to_amount, PdfExtractionError,
)
from services.settlement_engine import build_documents, compute_tax, compute_fee
from services.excel_generator import build as build_sale_excel
from services.rental_engine import build_defaults
from services.rental_excel import build as build_rental_excel
from services import issuer_store


st.set_page_config(page_title="決済案内書・賃貸精算 自動作成", page_icon="🏦", layout="wide")


# ============================================================
# サイドバー：発行企業（自社）情報 ── 登録・呼出・削除
# ============================================================
NEW_ISSUER_LABEL = "＋ 新規入力"

st.session_state.setdefault("issuer_form_version", 0)
st.session_state.setdefault("issuer_prefill", dict(issuer_store.EMPTY_ISSUER))

with st.sidebar:
    st.header("🏢 発行企業（自社）情報")
    st.caption("帳票のヘッダーに印字されます。会社名で保存・切り替えできます。")

    issuers_df = issuer_store.load_issuers()
    options = [NEW_ISSUER_LABEL] + issuers_df["name"].tolist()
    selected = st.selectbox("保存済みの発行企業から呼び出し", options, key="issuer_select")

    if selected != NEW_ISSUER_LABEL:
        srow = issuers_df[issuers_df["name"] == selected].iloc[0]
        candidate = {f: str(srow.get(f, "")) for f in issuer_store.ISSUER_FIELDS}
    else:
        candidate = dict(issuer_store.EMPTY_ISSUER)
    if candidate != st.session_state.issuer_prefill:
        st.session_state.issuer_prefill = candidate
        st.session_state.issuer_form_version += 1

    v = st.session_state.issuer_form_version
    p = st.session_state.issuer_prefill
    issuer = {
        "name": st.text_input("会社名", value=p["name"], key=f"iss_name_{v}"),
        "representative": st.text_input("代表者", value=p["representative"], key=f"iss_rep_{v}"),
        "address": st.text_area("住所", value=p["address"], height=60, key=f"iss_addr_{v}"),
        "tel": st.text_input("TEL", value=p["tel"], key=f"iss_tel_{v}"),
        "fax": st.text_input("FAX", value=p["fax"], key=f"iss_fax_{v}"),
        "registration_no": st.text_input("インボイス登録番号", value=p["registration_no"], key=f"iss_reg_{v}"),
        "bank": st.text_area("振込先（請求書用）", value=p["bank"], height=60, key=f"iss_bank_{v}"),
    }

    cs, cd = st.columns(2)
    with cs:
        if st.button("💾 保存", use_container_width=True):
            if issuer["name"].strip():
                issuer_store.save_issuer(issuer)
                st.success(f"「{issuer['name']}」を保存しました。")
                st.rerun()
            else:
                st.warning("会社名を入力してください。")
    with cd:
        if selected != NEW_ISSUER_LABEL and st.button("🗑 削除", use_container_width=True):
            issuer_store.delete_issuer(selected)
            st.success(f"「{selected}」を削除しました。")
            st.rerun()


st.title("🏦 決済案内書・賃貸精算 自動作成システム")

mode = st.radio(
    "取引種別",
    ["売買（決済案内書）", "賃貸（初期費用・送金精算）"],
    horizontal=True,
)


# ============================================================================
# 売買モード
# ============================================================================
def render_sale() -> None:
    st.caption(
        "重説PDFと固定資産税評価証明書PDFから、固都税・管理費等の日割りを自動計算し、"
        "買主用・売主用の決済案内書(Excel)を生成します。"
    )

    DEFAULTS = {
        "sale_price": 0, "deposit": 0, "mgmt_fee_monthly": 0, "repair_fee_monthly": 0,
        "seller_name": "", "buyer_name": "", "property_location": "",
        "fixed_asset_tax": 0, "city_planning_tax": 0, "tax_year_label": "",
    }
    for k, val in DEFAULTS.items():
        st.session_state.setdefault(f"pf_{k}", val)

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

    st.header("3. 決済条件")
    dc1, dc2, dc3 = st.columns(3)
    with dc1:
        settlement_date = st.date_input("決済日（引き渡し日）", value=date.today())
    with dc2:
        region = st.radio("固都税の起算日", ["4月1日：関西", "1月1日：関東"],
                          help="売主・買主の固都税負担を日割りする基準日。地域慣習で選択します。")
        start_month = START_MONTH_KANTO if region.startswith("1月") else START_MONTH_KANSAI
    with dc3:
        fee_mode = st.radio("管理費等の清算方法", ["当月日割り分のみ", "当月日割り ＋ 翌月1ヶ月分 前払い"],
                            help="管理組合への引落タイミングにより翌月分を先出し清算する場合に選択します。")
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

    data = SettlementData(
        sale_price=sale_price, deposit=deposit, mgmt_fee_monthly=mgmt_fee,
        repair_fee_monthly=repair_fee, seller_name=seller_name, buyer_name=buyer_name,
        property_location=property_location, fixed_asset_tax=fixed_asset_tax,
        city_planning_tax=city_planning_tax, tax_year_label=tax_year_label,
        settlement_date=settlement_date, start_month=start_month, next_month_fee=next_month_fee,
        buyer_brokerage=buyer_brokerage, buyer_registration=buyer_registration,
        seller_brokerage=seller_brokerage, seller_registration=seller_registration,
    )

    st.header("4. 清算プレビュー")
    if sale_price <= 0:
        st.info("売買代金を入力（またはPDFを解析）すると清算結果が表示されます。")
        return

    buyer_doc, seller_doc = build_documents(data)
    tax, fee = compute_tax(data), compute_fee(data)
    m1, m2, m3 = st.columns(3)
    m1.metric("固都税 清算金（買主負担）", f"¥{tax['amount']:,}", help=tax["note"] or None)
    m2.metric("管理費等 清算金", f"¥{fee['amount']:,}", help=fee["note"] or None)
    m3.metric("売買残代金", f"¥{data.remaining_price:,}")

    pc1, pc2 = st.columns(2)
    for col, doc in ((pc1, buyer_doc), (pc2, seller_doc)):
        with col:
            st.subheader(f"{doc.role}用：{doc.name or doc.role} 様")
            df = pd.DataFrame([{"項目": l.label, "金額": l.amount, "内訳": l.note} for l in doc.lines])
            st.dataframe(df, hide_index=True, use_container_width=True,
                         column_config={"金額": st.column_config.NumberColumn(format="¥%d")})
            st.metric(doc.total_label, f"¥{doc.total:,}")
            for n in doc.notes:
                st.warning(n)

    st.divider()
    xlsx = build_sale_excel(data, buyer_doc, seller_doc, issuer)
    st.download_button(
        "📥 決済案内書（買主用・売主用）をExcelでダウンロード", data=xlsx,
        file_name=f"決済案内書_{property_location or '物件'}_{settlement_date}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary", use_container_width=True,
    )


# ============================================================================
# 賃貸モード
# ============================================================================
RENTAL_DEFAULTS = {
    "rent": 0, "common_fee": 0, "parking": 0, "insurance": 0,
    "deposit": 0, "key_money": 0, "guarantee_fee": 0, "key_exchange": 0,
    "parking_key_money": 0, "remote_fee": 0, "brokerage": 0,
    "landlord_name": "", "tenant_name": "", "property_location": "", "room_number": "",
    "move_in_iso": "",
}


def _items_to_df(items: list[RentLine]) -> pd.DataFrame:
    return pd.DataFrame([{"項目": i.label, "金額": i.amount, "備考": i.note} for i in items])


def _df_to_items(df: pd.DataFrame) -> list[RentLine]:
    items = []
    for _, r in df.iterrows():
        label = str(r.get("項目", "") or "").strip()
        if not label:
            continue
        amt = to_amount(r.get("金額"))
        items.append(RentLine(label, amt, str(r.get("備考", "") or "")))
    return items


def render_rental() -> None:
    st.caption(
        "賃貸借契約書/重説PDFから賃料・一時金を自動入力し、入居者用の初期費用請求明細と"
        "オーナー用の初回送金精算明細(Excel)を生成します。明細は自由に追加・修正できます。"
    )

    for k, val in RENTAL_DEFAULTS.items():
        st.session_state.setdefault(f"pr_{k}", val)

    st.header("1. 書類アップロード")
    file_r = st.file_uploader("賃貸借契約書 / 賃貸 重要事項説明書（PDF）", type="pdf", key="up_rent")
    if st.button("🔍 PDFを自動解析してフォームに反映", type="primary", use_container_width=True):
        if not file_r:
            st.warning("PDFをアップロードしてください。")
        else:
            try:
                with st.spinner("賃貸借契約書を解析中…（数十秒かかります）"):
                    r = parse_rental_explanation(file_r.getvalue())
                st.session_state.pr_rent = to_amount(r.get("家賃"))
                st.session_state.pr_common_fee = to_amount(r.get("共益費"))
                st.session_state.pr_parking = to_amount(r.get("駐車場"))
                st.session_state.pr_insurance = to_amount(r.get("火災保険"))
                st.session_state.pr_deposit = to_amount(r.get("敷金"))
                st.session_state.pr_key_money = to_amount(r.get("礼金"))
                st.session_state.pr_guarantee_fee = to_amount(r.get("保証料"))
                st.session_state.pr_key_exchange = to_amount(r.get("鍵交換代"))
                st.session_state.pr_parking_key_money = to_amount(r.get("駐車場礼金"))
                st.session_state.pr_brokerage = to_amount(r.get("仲介手数料"))
                st.session_state.pr_landlord_name = str(r.get("貸主氏名", "") or "")
                st.session_state.pr_tenant_name = str(r.get("借主氏名", "") or "")
                st.session_state.pr_property_location = str(r.get("物件所在", "") or "")
                st.session_state.pr_move_in_iso = str(r.get("入居日", "") or "")
                st.success("解析が完了しました。下のフォームに反映しています。内容をご確認ください。")
            except PdfExtractionError as e:
                st.error(str(e))

    st.header("2. 契約条件の確認")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("月額")
        rent = st.number_input("家賃", min_value=0, step=1000, value=int(st.session_state.pr_rent))
        common_fee = st.number_input("共益費・管理費", min_value=0, step=500, value=int(st.session_state.pr_common_fee))
        parking = st.number_input("駐車場代", min_value=0, step=500, value=int(st.session_state.pr_parking))
        insurance = st.number_input("火災保険・サポート（月額相当）", min_value=0, step=100, value=int(st.session_state.pr_insurance))
    with c2:
        st.subheader("一時金")
        deposit = st.number_input("敷金", min_value=0, step=1000, value=int(st.session_state.pr_deposit))
        key_money = st.number_input("礼金", min_value=0, step=1000, value=int(st.session_state.pr_key_money))
        guarantee_fee = st.number_input("家賃保証料", min_value=0, step=1000, value=int(st.session_state.pr_guarantee_fee))
        key_exchange = st.number_input("鍵交換代", min_value=0, step=1000, value=int(st.session_state.pr_key_exchange))
        parking_key_money = st.number_input("駐車場礼金", min_value=0, step=1000, value=int(st.session_state.pr_parking_key_money))
        remote_fee = st.number_input("リモコン代", min_value=0, step=1000, value=int(st.session_state.pr_remote_fee))
    with c3:
        st.subheader("当事者・物件")
        landlord_name = st.text_input("貸主（オーナー）", value=st.session_state.pr_landlord_name)
        tenant_name = st.text_input("借主（入居者）", value=st.session_state.pr_tenant_name)
        property_location = st.text_input("物件所在", value=st.session_state.pr_property_location)
        room_number = st.text_input("部屋番号", value=st.session_state.pr_room_number)
        try:
            move_in_default = date.fromisoformat(st.session_state.pr_move_in_iso)
        except (ValueError, TypeError):
            move_in_default = date.today()
        move_in_date = st.date_input("入居日（賃料発生日）", value=move_in_default)

    st.header("3. 仲介・オーナー精算の設定")
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        brokerage = st.number_input("仲介手数料（入居者）", min_value=0, step=1000, value=int(st.session_state.pr_brokerage))
    with s2:
        brokerage_discount = st.number_input("仲介手数料 割引", min_value=0, step=1000, value=0)
    with s3:
        ad_fee = st.number_input("広告料 AD（オーナー天引き）", min_value=0, step=1000, value=0)
    with s4:
        mgmt_fee_rate = st.number_input("集金代行手数料率（家賃%）", min_value=0.0, step=0.5, value=5.0)
    f1, f2 = st.columns(2)
    with f1:
        payment_due = st.text_input("支払期限", placeholder="例: 2026年7月8日")
    with f2:
        required_docs = st.text_input("必要書類", placeholder="例: 住民票、収入証明、車検証写し")
    owner_brokerage = st.number_input("仲介手数料（貸主負担・オーナー天引き）", min_value=0, step=1000, value=0)

    data = RentalData(
        property_location=property_location, room_number=room_number,
        landlord_name=landlord_name, tenant_name=tenant_name, move_in_date=move_in_date,
        rent=rent, common_fee=common_fee, parking=parking, insurance=insurance,
        deposit=deposit, key_money=key_money, guarantee_fee=guarantee_fee,
        key_exchange=key_exchange, parking_key_money=parking_key_money, remote_fee=remote_fee,
        brokerage=brokerage, brokerage_discount=brokerage_discount,
        ad_fee=ad_fee, owner_brokerage=owner_brokerage, mgmt_fee_rate=mgmt_fee_rate,
        payment_due=payment_due, required_docs=required_docs,
    )

    st.header("4. 明細プレビュー（編集可）")
    st.caption("「標準明細を生成」で自動作成後、表を直接編集して項目の追加・修正ができます。")
    if st.button("⚙️ 標準明細を生成 / 再生成", use_container_width=True):
        build_defaults(data)
        st.session_state.rent_tenant_df = _items_to_df(data.tenant_items)
        st.session_state.rent_owner_df = _items_to_df(data.owner_items)

    if "rent_tenant_df" not in st.session_state:
        st.info("「標準明細を生成」を押すと、入力値から請求明細・送金精算が作成されます。")
        return

    col_cfg = {
        "金額": st.column_config.NumberColumn("金額", format="¥%d"),
        "項目": st.column_config.TextColumn("項目", width="large"),
        "備考": st.column_config.TextColumn("備考", width="medium"),
    }
    tc, oc = st.columns(2)
    with tc:
        st.subheader(f"入居者用：{tenant_name or '入居者'} 様（請求書）")
        ed_t = st.data_editor(st.session_state.rent_tenant_df, num_rows="dynamic",
                              use_container_width=True, hide_index=True, column_config=col_cfg, key="ed_tenant")
        tenant_items = _df_to_items(ed_t)
        st.metric("ご請求金額", f"¥{sum(i.amount for i in tenant_items):,}")
    with oc:
        st.subheader(f"オーナー用：{landlord_name or 'オーナー'} 様（送金精算）")
        ed_o = st.data_editor(st.session_state.rent_owner_df, num_rows="dynamic",
                              use_container_width=True, hide_index=True, column_config=col_cfg, key="ed_owner")
        owner_items = _df_to_items(ed_o)
        st.metric("送金金額（オーナー手取り）", f"¥{sum(i.amount for i in owner_items):,}")

    data.tenant_items = tenant_items
    data.owner_items = owner_items

    st.divider()
    xlsx = build_rental_excel(data, issuer)
    st.download_button(
        "📥 賃貸精算（入居者用・オーナー用）をExcelでダウンロード", data=xlsx,
        file_name=f"賃貸精算_{property_location or '物件'}_{move_in_date}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary", use_container_width=True,
    )


if mode.startswith("売買"):
    render_sale()
else:
    render_rental()
