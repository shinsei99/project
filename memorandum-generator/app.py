# -*- coding: utf-8 -*-
"""
覚書・同居申請ジェネレーター  — 大京商事株式会社
「覚書・同居申請等」フォルダの170書類をパターン化し、フォーム入力→Word(.docx)自動生成。
port 8524
"""
import datetime
import streamlit as st
import docgen

st.set_page_config(page_title="覚書・合意書ジェネレーター", page_icon="📝", layout="centered")

st.title("📝 覚書・合意書ジェネレーター")
st.caption("フォームに入力 → 覚書・合意書・各種申請書の Word(.docx) を自動作成します。"
           "日付・押印欄は空欄で出力されるので、印刷して手書き・捺印してください。")

# ── 書類タイプ選択 ────────────────────────────────────────────────
type_labels = {k: v[0] for k, v in docgen.DOC_TYPES.items()}
doc_key = st.selectbox("① 書類の種類を選択", list(type_labels.keys()),
                       format_func=lambda k: type_labels[k])

st.divider()

MEMO_FAMILY = {"rent_revision", "rent_reduction", "succession", "rep_change",
               "guarantor_delete", "restoration", "parking_change", "name_change", "freeform"}

d = {}

# ── 覚書ファミリー共通入力 ─────────────────────────────────────────
def property_inputs():
    st.subheader("物件表示")
    c1, c2 = st.columns(2)
    d["address"] = c1.text_input("所在地", placeholder="大阪市都島区…")
    d["name"] = c2.text_input("名称（建物名・号室）", placeholder="○○ビル　３階")
    d["area"] = st.text_input("契約面積（任意）", placeholder="約○○坪")

def era_witness_inputs(default_witness=True):
    c1, c2, c3 = st.columns([1, 1, 2])
    d["era"] = c1.selectbox("元号", ["令和", "平成", "（空欄）"], index=0)
    if d["era"] == "（空欄）":
        d["era"] = ""
    d["witness"] = c2.checkbox("立会人(大京)", value=default_witness)
    d["witness_rep"] = c3.text_input("立会人 代表者名", value=docgen.DAIKYO["rep"]) if d["witness"] else None

def party_ko_otsu(ko_label="賃貸人（甲）", otsu_label="賃借人（乙）"):
    st.subheader("当事者")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**{ko_label}**")
        d["ko_name"] = st.text_input("甲 氏名（前文用）", key="kn", placeholder="大京商事株式会社／個人名")
        d["ko_addr"] = st.text_input("甲 住所（署名欄用・任意）", key="ka")
        d["ko_sign"] = st.text_input("甲 署名欄 氏名（任意・空欄可）", key="ks")
    with c2:
        st.markdown(f"**{otsu_label}**")
        d["otsu_name"] = st.text_input("乙 氏名（前文用）", key="on", placeholder="株式会社○○")
        d["otsu_addr"] = st.text_input("乙 住所（署名欄用・任意）", key="oa")
        d["otsu_sign"] = st.text_input("乙 署名欄 氏名（任意・空欄可）", key="os")

def party_hei(label="新賃借人（丙）"):
    st.markdown(f"**{label}**")
    c1, c2, c3 = st.columns(3)
    d["hei_name"] = c1.text_input("丙 氏名（前文用）", key="hn")
    d["hei_addr"] = c2.text_input("丙 住所（任意）", key="ha")
    d["hei_sign"] = c3.text_input("丙 署名欄 氏名（任意）", key="hs")

def orig_date_input():
    d["orig_date"] = st.text_input("原契約 締結日", placeholder="平成○○年○月○日")


# ═══════════════ タイプ別フォーム ═══════════════
if doc_key in MEMO_FAMILY:
    property_inputs()
    st.divider()

if doc_key == "rent_revision":
    party_ko_otsu()
    orig_date_input()
    st.subheader("賃料（現行 → 改定）")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**現行**")
        d["cur_rent"] = st.text_input("現行 賃料/月額", key="cr", placeholder="７２，０００円")
        d["cur_kyoueki"] = st.text_input("現行 共益費/月額", key="ck")
        d["cur_suido"] = st.text_input("現行 水道代/月額", key="cs")
        d["cur_total"] = st.text_input("現行 合計（任意）", key="ct")
    with c2:
        st.markdown("**改定後**")
        d["new_rent"] = st.text_input("改定 賃料/月額", key="nr", placeholder="５０，０００円")
        d["new_kyoueki"] = st.text_input("改定 共益費/月額", key="nk")
        d["new_suido"] = st.text_input("改定 水道代/月額", key="ns")
        d["new_total"] = st.text_input("改定 合計（任意）", key="nt")
    d["start_date"] = st.text_input("本覚書 開始日", placeholder="２０２１年１月１日（１月分）")
    era_witness_inputs(default_witness=False)

elif doc_key == "rent_reduction":
    party_ko_otsu("貸主（甲）", "借主（乙）")
    orig_date_input()
    st.subheader("改定内容")
    d["new_rent"] = st.text_input("改定後 賃料/月額", placeholder="８０，０００円（内消費税含む）")
    d["kyoueki_note"] = st.text_input("共益費の扱い", value="共益費は賃料に込み")
    d["start_date"] = st.text_input("開始日", placeholder="平成２８年３月１日")
    era_witness_inputs()

elif doc_key == "succession":
    party_ko_otsu()
    party_hei("新賃借人（丙）")
    st.markdown("**新連帯保証人**（既定=旧賃借人 乙。別人の場合のみ入力）")
    c1, c2, c3 = st.columns(3)
    d["hosho_name"] = c1.text_input("保証人 氏名（前文用・任意）", key="pn")
    d["hosho_addr"] = c2.text_input("保証人 住所（任意）", key="pa")
    d["hosho_sign"] = c3.text_input("保証人 署名欄（任意）", key="ps")
    orig_date_input()
    d["succ_date"] = st.text_input("承継期日", placeholder="平成○○年○月○日")
    era_witness_inputs()

elif doc_key == "rep_change":
    party_ko_otsu("貸主（甲）", "借主（乙）")
    party_hei("新代表取締役・新連帯保証人（丙）")
    orig_date_input()
    d["assume_date"] = st.text_input("連帯保証人 就任日", placeholder="平成○○年○月○日")
    era_witness_inputs()

elif doc_key == "guarantor_delete":
    party_ko_otsu("（甲）", "（乙）")
    orig_date_input()
    d["guarantor_clause"] = st.text_input("連帯保証人に関する条項番号", value="第２４条")
    d["guarantor_person"] = st.text_input("解除する連帯保証人 氏名", placeholder="永井　博")
    era_witness_inputs()

elif doc_key == "restoration":
    party_ko_otsu()
    orig_date_input()
    d["resto_clause"] = st.text_input("原状回復条項", value="第１９条「貸室の原状回復と明渡し」")
    d["reform_when"] = st.text_input("改装の承認時期", placeholder="平成２７年８月")
    d["items"] = st.text_area("原状回復義務を負わない項目（1行1項目）",
                              placeholder="トイレの改装\nキッチンの改装\nブラインド（既設は撤去）")
    era_witness_inputs()

elif doc_key == "parking_change":
    party_ko_otsu("貸主（甲）", "借主（乙）")
    orig_date_input()
    c1, c2 = st.columns(2)
    d["from_no"] = c1.text_input("変更前 区画番号", placeholder="№２番")
    d["to_no"] = c2.text_input("変更後 区画番号", placeholder="№２３番")
    d["start_date"] = st.text_input("開始日", placeholder="平成１９年８月１日")
    era_witness_inputs(default_witness=False)

elif doc_key == "name_change":
    party_ko_otsu()
    party_hei("新賃借人（丙）")
    orig_date_input()
    d["based_on"] = st.text_input("根拠条項", value="特約事項第２項")
    d["reason"] = st.text_input("名義変更の事由", value="新設会社法人登記完了")
    era_witness_inputs()

elif doc_key == "freeform":
    d["doc_title"] = st.selectbox("表題", ["覚　　書", "合　意　書"])
    party_ko_otsu("（甲）", "（乙）")
    orig_date_input()
    d["clauses"] = st.text_area("本文条項（1行1条項。番号は自動付与）", height=160,
                                placeholder="乙は…することを甲は了承する。\n乙が…する場合は事前に甲の承認を得る。")
    d["copies"] = st.selectbox("作成通数", ["２", "３", "４"])
    era_witness_inputs()

# ── 特殊フォーマット ──────────────────────────────────────────────
elif doc_key == "cohabitation":
    st.subheader("同居申請書")
    d["era"] = st.selectbox("元号", ["令和", "平成"], index=0)
    d["lessor_to"] = st.text_input("宛先（賃貸人）", placeholder="有限会社　岩城商店")
    d["contract_date"] = st.text_input("賃貸契約書 締結日", placeholder="令和○○年○月○日")
    d["property_name"] = st.text_input("物件名（賃借室）", placeholder="○○ビル　４階（約○○坪）")
    d["prop_addr"] = st.text_input("物件所在地", placeholder="大阪市…")
    d["cohab_start"] = st.text_input("同居開始日", placeholder="令和○○年○月○日")
    d["article"] = st.text_input("同居禁止条項番号", value="１１")
    st.markdown("**申請人（賃借人）**")
    d["tenant_name"] = st.text_input("賃借人 氏名", placeholder="株式会社○○　代表取締役　○○")
    d["tenant_addr"] = st.text_input("賃借人 住所")
    st.markdown("**同居人（最大3件）**")
    for i in range(1, 4):
        c1, c2 = st.columns(2)
        d[f"cohab{i}_name"] = c1.text_input(f"同居人{i} 氏名", key=f"chn{i}")
        d[f"cohab{i}_addr"] = c2.text_input(f"同居人{i} 住所", key=f"cha{i}")

elif doc_key == "minor_consent":
    st.subheader("未成年者同意書")
    d["era"] = st.selectbox("元号", ["令和", "平成"], index=0)
    d["minor_name"] = st.text_input("未成年者 氏名")
    d["minor_addr"] = st.text_input("未成年者 現住所")
    d["property_name"] = st.text_input("物件名", placeholder="○○　４０３号")
    d["prop_addr"] = st.text_input("物件住所")
    d["conditions"] = st.text_area("賃貸借条件（1行1項目）", height=120,
                                   placeholder="敷金　62,500円　礼金　62,500円\n賃料/月　62,500円　管理費/月 7,000円")
    d["parent_name"] = st.text_input("親権者 氏名")
    d["parent_addr"] = st.text_input("親権者 住所")

elif doc_key == "use_permit":
    st.subheader("使用許可承諾書")
    d["era"] = st.selectbox("元号", ["令和", "平成"], index=0)
    d["tenant_name"] = st.text_input("賃借人（申請者）", placeholder="株式会社○○")
    d["tenant_rep"] = st.text_input("賃借人 代表者（任意）", placeholder="代表取締役　○○")
    d["prop_addr"] = st.text_input("賃借物件 所在地")
    d["property_name"] = st.text_input("賃借物件 表示", placeholder="○○ビル　３階B室（約○○坪）")
    d["purpose"] = st.text_input("使用目的・名称", placeholder="○○クリニック 等")
    d["user_name"] = st.text_input("使用を行う者 氏名")
    d["user_addr"] = st.text_input("使用を行う者 住所")
    d["lessor_name"] = st.text_input("賃貸人 氏名（承諾者）")
    d["lessor_addr"] = st.text_input("賃貸人 住所")

st.divider()

# ── 生成 ──────────────────────────────────────────────────────────
if st.button("📄 Word文書を生成", type="primary", use_container_width=True):
    try:
        data = docgen.DOC_TYPES[doc_key][1](d)
        label = type_labels[doc_key].split("（")[0]
        prop = (d.get("name") or d.get("property_name") or "").replace("/", "-")[:20]
        today = datetime.date.today().strftime("%Y%m%d")
        fname = f"{label}_{prop}_{today}.docx" if prop else f"{label}_{today}.docx"
        st.success("生成しました。下のボタンからダウンロードしてください。")
        st.download_button("⬇️ ダウンロード", data=data, file_name=fname,
                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                           use_container_width=True)
    except Exception as e:
        st.error(f"生成エラー: {e}")

with st.expander("ℹ️ 使い方・注意"):
    st.markdown("""
- 立会人は既定で **大京商事株式会社（代表取締役 鷲見文子）** が入ります。物件の貸主が大京自身の場合はチェックを外してください。
- **署名欄の氏名・住所は空欄のまま出力**しても構いません（印刷後に手書き・捺印する運用）。前文用の氏名だけ入れれば本文は完成します。
- 日付欄は「令和　　年　　月　　日」の空欄で出力されます。
- 元となった170書類のパターンを再現しています。特殊な文言は生成後の Word 上で微調整してください。
""")
