# -*- coding: utf-8 -*-
"""不動産査定書 作成システム（DAIKYO）。

物件種別（土地・戸建て / マンション）を選び、取引事例・売出物件のPDFをAIで読み込み、
評点方式で査定価格を自動算出（手修正可）→ 3枚セットの査定書(Excel)を出力する。
不動産情報ライブラリAPIは「参考相場」として補助的に利用する。
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from services import satei_core as sc
from services import case_extractor, satei_report, explanation_service, ryutsu_service
from services import (area_stats_service, geo_service, market_research_service,
                      registry_parser, satei_store)

st.set_page_config(page_title="不動産査定書 作成システム", page_icon="🏠", layout="wide")


# ── ヘルパ ────────────────────────────────────────────────────────────────────
def wareki(d: date) -> str:
    if d.year >= 2019:
        n = d.year - 2018
        y = "元" if n == 1 else str(n)
        return f"令和{y}年{d.month}月{d.day}日"
    return d.strftime("%Y年%m月%d日")


def add_months(d: date, months: int) -> date:
    import calendar
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    return date(y, m, day)


def colspec(ptype):
    if ptype == sc.TYPE_MANSION:
        return [
            ("address", "所在地"), ("mansion_name", "マンション名・号室"),
            ("price_man", "価格(万円)"), ("exclusive_area", "専有面積㎡"),
            ("balcony_area", "ﾊﾞﾙｺﾆｰ㎡"), ("unit_price", "単価(円/㎡)"),
            ("direction", "向"), ("floor_no", "階/階建"), ("build_ym", "築年月"),
            ("station", "最寄駅"), ("access", "アクセス"), ("trade_ym", "取引年月"),
        ]
    return [
        ("address", "所在地"), ("price_man", "価格(万円)"),
        ("land_price_man", "うち土地(万円)"), ("land_area", "土地面積㎡"),
        ("building_area", "建物面積㎡"), ("unit_price", "土地単価(円/㎡)"),
        ("structure", "構造"), ("build_ym", "築年月"), ("madori", "間取り"),
        ("station", "最寄駅"), ("access", "アクセス"), ("trade_ym", "取引年月"),
    ]


def cases_to_df(cases, spec):
    if not cases:
        return pd.DataFrame([{label: "" for _, label in spec}])
    return pd.DataFrame([{label: c.get(key, "") for key, label in spec} for c in cases])


def df_to_cases(df, spec):
    out = []
    for _, row in df.iterrows():
        c = sc.empty_case()
        nonempty = False
        for key, label in spec:
            v = row.get(label, "")
            if pd.isna(v):
                v = ""
            c[key] = v
            if str(v).strip() not in ("", "0", "0.0", "nan"):
                nonempty = True
        if nonempty:
            out.append(c)
    return out


def avg_unit(cases):
    vals = [float(c.get("unit_price") or 0) for c in cases if float(c.get("unit_price") or 0) > 0]
    return round(sum(vals) / len(vals)) if vals else 0


def num(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


# ── 謄本（登記簿PDF）→ 査定対象物件の自動入力 ────────────────────────────────
# ①査定対象物件の各ウィジェットのキー（自動入力で上書きする対象）
AUTOFILL_KEYS = [
    "w_ptype", "w_addr", "w_chiban", "w_chimoku", "w_kaoku_no",
    "w_build_ym", "w_station", "w_access", "w_structure",
    "w_madori", "w_land_area", "w_building_area",
    "w_mansion_name", "w_exclusive_area", "w_balcony_area", "w_floor_no", "w_direction",
]


def build_subject_from_registries(infos):
    """複数の RegistryInfo を1物件に統合し (fill, ptype) を返す。

    土地謄本（地積）＋建物謄本（床面積・構造・築年）＋区分建物謄本（専有面積・名称）を
    まとめて1つの査定対象にする。1枚でも区分建物なら種別＝マンションと判定する。
    各項目は最初に得られた非空の値を採用（先勝ち）。
    """
    fill: dict = {}
    is_mansion = False

    def setk(key, value):
        if value in (None, "", 0, 0.0):
            return
        if not fill.get(key):
            fill[key] = value

    for info in infos:
        cls = registry_parser.classify(info)
        if cls == "mansion":
            is_mansion = True
        # 所在（土地・建物は地番を付す。区分建物は所在のみ）
        addr = info.location or ""
        if cls != "mansion" and info.chiban:
            addr = f"{addr}{info.chiban}".strip()
        setk("address", addr)
        setk("chiban", info.chiban)
        setk("chimoku", info.chimoku)
        setk("kaoku_no", info.kaoku_no)
        setk("structure", info.structure)
        setk("build_ym", info.build_ym)
        setk("land_area", info.land_area)
        setk("building_area", info.floor_area)
        if cls == "mansion":
            setk("mansion_name", info.mansion_name)
            setk("exclusive_area", info.exclusive_area)
            floor = f"{info.floor_no or ''}/{info.total_floors or ''}".strip("/")
            setk("floor_no", floor)

    ptype = sc.TYPE_MANSION if is_mansion else sc.TYPE_KODATE
    return fill, ptype


def apply_autofill(fill, ptype):
    """統合結果を①各ウィジェットの session_state キーへ書き込む（次回描画で反映）。"""
    ss["w_ptype"] = ptype
    text_map = {
        "address": "w_addr", "chiban": "w_chiban", "chimoku": "w_chimoku",
        "kaoku_no": "w_kaoku_no", "structure": "w_structure", "build_ym": "w_build_ym",
        "mansion_name": "w_mansion_name", "floor_no": "w_floor_no",
    }
    for src, wk in text_map.items():
        if src in fill:
            ss[wk] = str(fill[src])
    num_map = {
        "land_area": "w_land_area", "building_area": "w_building_area",
        "exclusive_area": "w_exclusive_area",
    }
    for src, wk in num_map.items():
        if src in fill:
            ss[wk] = float(fill[src])


# 謄本読取結果パネルの列（RegistryInfo属性 → 表示名）
REG_VIEW_COLS = [
    ("_file", "ファイル"), ("_cls", "分類"),
    ("location", "所在"), ("chiban", "地番"), ("chimoku", "地目"),
    ("land_area", "地積㎡"), ("kaoku_no", "家屋番号"), ("floor_area", "床面積㎡"),
    ("structure", "構造"), ("build_ym", "築年月"), ("build_year", "築年(西暦)"),
    ("mansion_name", "建物名称"), ("exclusive_area", "専有面積㎡"),
    ("floor_no", "所在階"), ("total_floors", "総階数"), ("total_units", "総戸数"),
]

_CLS_LABEL = {"mansion": "区分建物", "building": "建物", "land": "土地"}


def registry_view_df(reg_infos):
    """[(filename, RegistryInfo)] を読取結果一覧の DataFrame に整形（空欄は空文字）。"""
    rows = []
    for fname, info in reg_infos:
        d = vars(info)
        row = {}
        for attr, label in REG_VIEW_COLS:
            if attr == "_file":
                row[label] = fname
            elif attr == "_cls":
                row[label] = _CLS_LABEL.get(registry_parser.classify(info), "")
            else:
                v = d.get(attr, "")
                row[label] = "" if v in (None, "", 0, 0.0) else v
        rows.append(row)
    return pd.DataFrame(rows, columns=[label for _, label in REG_VIEW_COLS])


# ── 査定の保存・呼び出し（任意の名前で丸ごと保存／復元） ──────────────────────
# スナップショットに含めるウィジェットキー（①各欄＋種別＋顧客/日付）
SNAPSHOT_WIDGET_KEYS = AUTOFILL_KEYS + [
    "w_rights", "w_customer", "w_satei_date", "w_expiry_date",
]
_SNAPSHOT_DATE_KEYS = {"w_satei_date", "w_expiry_date"}


def collect_snapshot():
    """現在の入力一式を JSON 化可能な dict にまとめる。"""
    widgets = {}
    for k in SNAPSHOT_WIDGET_KEYS:
        if k not in ss:
            continue
        v = ss[k]
        if k in _SNAPSHOT_DATE_KEYS and isinstance(v, date):
            v = v.isoformat()
        widgets[k] = v
    return {
        "widgets": widgets,
        "trades": ss.get("trades", []),
        "sales": ss.get("sales", []),
        "plus": ss.get("plus", []),
        "minus": ss.get("minus", []),
        "explanation": ss.get("explanation", ""),
        "ryutsu": ss.get("ryutsu", 100),
        "ryutsu_reason": ss.get("ryutsu_reason", ""),
    }


def apply_snapshot(snap):
    """保存スナップショットを session_state へ書き戻す（次回描画で復元）。"""
    for k, v in (snap.get("widgets") or {}).items():
        if k in _SNAPSHOT_DATE_KEYS and isinstance(v, str):
            try:
                v = date.fromisoformat(v)
            except Exception:
                continue
        ss[k] = v
    ss["trades"] = snap.get("trades", []) or []
    ss["sales"] = snap.get("sales", []) or []
    ss["plus"] = snap.get("plus", []) or [sc.empty_point() for _ in range(2)]
    ss["minus"] = snap.get("minus", []) or [sc.empty_point() for _ in range(2)]
    ss["explanation"] = snap.get("explanation", "")
    ss["ryutsu"] = snap.get("ryutsu", 100)
    ss["ryutsu_reason"] = snap.get("ryutsu_reason", "")
    # データエディタ／流通性選択の内部状態はリセットし、復元データで作り直させる
    for k in ("ed_trades", "ed_sales", "ed_plus", "ed_minus", "ryutsu_choice"):
        ss.pop(k, None)
    ss["ryutsu_choice_prev"] = None


# ── セッション初期化 ──────────────────────────────────────────────────────────
ss = st.session_state
ss.setdefault("trades", [])
ss.setdefault("sales", [])
ss.setdefault("reg_infos", [])   # [(filename, RegistryInfo)] 謄本の読取結果
ss.setdefault("plus", [sc.empty_point() for _ in range(2)])
ss.setdefault("minus", [sc.empty_point() for _ in range(2)])
ss.setdefault("explanation", "")
ss.setdefault("ryutsu", 100)
ss.setdefault("ryutsu_reason", "")
ss.setdefault("ryutsu_trades", None)   # {ratio, reason, basis}
ss.setdefault("ryutsu_ai", None)       # {ratio, reason}
ss.setdefault("ryutsu_choice_prev", None)
# 顧客名・日付（保存/呼び出しで復元できるようキー付き管理）
ss.setdefault("w_customer", "")
ss.setdefault("w_satei_date", date.today())
ss.setdefault("w_expiry_date", add_months(date.today(), 3))
# 会社セレクトの保留適用（ウィジェット生成前に行う）
if "_pending_company_sel" in ss:
    ss["company_sel"] = ss.pop("_pending_company_sel")
company = sc.load_company()


# ============================================================
# サイドバー：自社情報
# ============================================================
with st.sidebar:
    st.header("🏢 自社情報")
    st.caption("会社名ごとに登録・選択できます")

    names = sc.list_companies()
    options = names + ["＋ 新規登録"]
    cur = sc.current_name()
    default_idx = names.index(cur) if cur in names else 0
    sel = st.selectbox("登録会社", options, index=default_idx, key="company_sel")
    is_new = sel == "＋ 新規登録"
    prof = sc.get_profile(sel) if not is_new else dict(
        company_name="", office="", staff="", tel="", address="",
        license_no="", logo_path="")
    if not is_new and sel != cur:
        sc.set_current(sel)

    kp = "new" if is_new else sel
    with st.form("company_form"):
        company_name = st.text_input("会社名", value=prof.get("company_name", ""), key=f"cn_{kp}")
        office = st.text_input("営業所", value=prof.get("office", ""), key=f"of_{kp}")
        staff = st.text_input("担当者名", value=prof.get("staff", ""), key=f"st_{kp}")
        tel = st.text_input("電話番号", value=prof.get("tel", ""), key=f"tl_{kp}")
        addr = st.text_input("所在地", value=prof.get("address", ""), key=f"ad_{kp}")
        lic = st.text_input("免許番号", value=prof.get("license_no", ""), key=f"lc_{kp}")
        logo_up = st.file_uploader("ロゴ画像（任意）", type=["png", "jpg", "jpeg"], key=f"lg_{kp}")
        submitted = st.form_submit_button("💾 保存", use_container_width=True)
    if submitted:
        if not company_name.strip():
            st.error("会社名を入力してください")
        else:
            info = {
                "company_name": company_name, "office": office, "staff": staff,
                "tel": tel, "address": addr, "license_no": lic,
                "logo_path": prof.get("logo_path", "") or "assets/logo.jpeg",
            }
            if logo_up is not None:
                import os, hashlib
                os.makedirs("assets", exist_ok=True)
                ext = logo_up.name.split(".")[-1].lower()
                tag = hashlib.md5(company_name.encode("utf-8")).hexdigest()[:8]
                p = f"assets/logo_{tag}.{ext}"
                with open(p, "wb") as f:
                    f.write(logo_up.getvalue())
                info["logo_path"] = p
            sc.save_profile(info)
            st.session_state["_pending_company_sel"] = company_name
            st.success("保存しました")
            st.rerun()

    if not is_new and len(names) > 1:
        if st.button("🗑 この会社を削除", use_container_width=True):
            sc.delete_profile(sel)
            st.session_state["_pending_company_sel"] = sc.current_name()
            st.rerun()

    st.divider()
    with st.expander("参考：不動産情報ライブラリAPI"):
        if market_research_service.get_api_key():
            st.success("API：設定済み（参考相場に利用）")
        else:
            st.info("APIキー未設定。参考相場は利用できません。")
        st.caption("査定は事例・売出のPDF入力が主、API相場は参考扱いです。")

    st.divider()
    st.header("💾 査定の保存・呼び出し")
    st.caption("入力内容一式を任意の名前で保存し、後で呼び出して続きから編集できます。")
    save_name = st.text_input("保存名", placeholder="例：上田様_網島町戸建",
                              key="satei_save_name")
    if st.button("💾 現在の内容を保存", use_container_width=True,
                 disabled=not save_name.strip()):
        satei_store.save_satei(save_name.strip(), collect_snapshot())
        st.success(f"「{save_name.strip()}」を保存しました")
        st.rerun()

    _saved = satei_store.list_saved()
    if _saved:
        pick = st.selectbox("保存済みから呼び出し", ["— 選択 —"] + _saved,
                            key="satei_pick")
        picked = pick != "— 選択 —"
        lc1, lc2 = st.columns(2)
        if lc1.button("📂 呼び出し", use_container_width=True, disabled=not picked):
            snap = satei_store.load_satei(pick)
            if snap:
                apply_snapshot(snap)
                st.success(f"「{pick}」を呼び出しました")
                st.rerun()
            else:
                st.error("読み込みに失敗しました")
        if lc2.button("🗑 削除", use_container_width=True, disabled=not picked):
            satei_store.delete_satei(pick)
            st.rerun()
    else:
        st.caption("保存済みの査定はまだありません。")


# ============================================================
# メイン
# ============================================================
st.title("🏠 不動産査定書 作成システム")
st.caption("取引事例・売出物件PDFをAIで読み込み → 評点方式で査定 → 3枚セットの査定書(Excel)を出力")

# ── 0. 謄本（登記簿PDF）から自動入力 ──
with st.expander("📄 謄本（登記簿PDF）から自動入力 — 複数枚まとめてOK（土地＋建物など）", expanded=True):
    st.caption("土地・建物の謄本をまとめてアップ→AIが読み取り、専有面積や建物名称の有無から"
               "種別（戸建／マンション）を自動判別して、下の①各欄に反映します。")
    reg_pdfs = st.file_uploader("謄本PDF（複数可）", type=["pdf"], accept_multiple_files=True,
                                key="reg_up", label_visibility="collapsed")
    ra, rb = st.columns([3, 1])
    do_reg = ra.button("🤖 謄本を読み取り→①に自動入力", use_container_width=True,
                       disabled=not reg_pdfs)
    if rb.button("🧹 ①をクリア", use_container_width=True):
        for _k in AUTOFILL_KEYS:
            ss.pop(_k, None)
        st.rerun()
    if do_reg:
        infos, errs = [], []
        with st.spinner(f"{len(reg_pdfs)}件の謄本を解析中…（スキャンPDFはAI-OCRのため時間がかかります）"):
            for f in reg_pdfs:
                try:
                    info, _m = registry_parser.parse_auto(f.getvalue(), f.name, mode="auto")
                    infos.append((f.name, info))
                except (registry_parser.RegistryParseError,
                        registry_parser.PdfExtractionError) as e:
                    errs.append(f"{f.name}: {e}")
                except Exception as e:  # 想定外も個別ファイル単位で握る
                    errs.append(f"{f.name}: {e}")
        for e in errs:
            st.error(e)
        if infos:
            ss.reg_infos = infos
            fill, det_ptype = build_subject_from_registries([i for _, i in infos])
            apply_autofill(fill, det_ptype)
            st.success(f"{len(infos)}件を読み取り、種別「{det_ptype}」と判定して①に反映しました。"
                       "内容を確認・補正してください。")
            st.rerun()

    # 読取結果一覧（謄本の重要情報をそのまま表示・確認用）
    if ss.get("reg_infos"):
        st.markdown("**📋 謄本の読取結果（原文の重要項目）**")
        st.caption("アップした謄本ごとの抽出結果です。①への反映内容と突き合わせて確認してください。")
        st.dataframe(registry_view_df(ss.reg_infos), use_container_width=True, hide_index=True)

ptype = st.radio("物件種別", sc.PROPERTY_TYPES, horizontal=True, key="w_ptype")
is_mansion = ptype == sc.TYPE_MANSION
spec = colspec(ptype)

c1, c2, c3 = st.columns(3)
customer = c1.text_input("お客様氏名", placeholder="例：上田", key="w_customer")
satei_d = c2.date_input("査定年月日", key="w_satei_date")
expiry_d = c3.date_input("有効期限", key="w_expiry_date")

st.divider()

# ── 1. 査定対象物件 ──
st.subheader("① 査定対象物件")
subj = sc.empty_case()
s1, s2, s3 = st.columns([2, 1, 1])
subj["address"] = s1.text_input("物件所在地", key="w_addr")
subj["rights"] = s2.selectbox("権利", ["所有権", "地上権", "賃借権", "定期借地権"], key="w_rights")
subj["build_ym"] = s3.text_input("築年月", placeholder="例 平成10年3月", key="w_build_ym")
s4, s5, s6, s7 = st.columns(4)
subj["station"] = s4.text_input("最寄駅・路線", key="w_station")
subj["access"] = s5.text_input("アクセス", placeholder="徒歩8分", key="w_access")
subj["structure"] = s6.text_input("建物構造", placeholder="木造2F", key="w_structure")
subj["madori"] = s7.text_input("間取り", placeholder="3LDK", key="w_madori")
# 登記情報（謄本の重要項目：地番・地目・家屋番号）
r1, r2, r3 = st.columns(3)
subj["chiban"] = r1.text_input("地番（登記）", placeholder="例 9番56", key="w_chiban")
subj["chimoku"] = r2.text_input("地目（登記）", placeholder="例 宅地", key="w_chimoku")
subj["kaoku_no"] = r3.text_input("家屋番号（登記）", placeholder="例 9番56", key="w_kaoku_no")
if is_mansion:
    m1, m2, m3, m4 = st.columns(4)
    subj["mansion_name"] = m1.text_input("マンション名・号室", key="w_mansion_name")
    subj["exclusive_area"] = m2.number_input("専有面積(㎡)", min_value=0.0, step=0.01,
                                             format="%.2f", key="w_exclusive_area")
    subj["balcony_area"] = m3.number_input("バルコニー(㎡)", min_value=0.0, step=0.01,
                                           format="%.2f", key="w_balcony_area")
    subj["floor_no"] = m4.text_input("階／階建", placeholder="6/11", key="w_floor_no")
    subj["direction"] = st.text_input("向き", placeholder="南", key="w_direction")
else:
    k1, k2 = st.columns(2)
    subj["land_area"] = k1.number_input("土地面積(㎡)", min_value=0.0, step=0.01,
                                        format="%.2f", key="w_land_area")
    subj["building_area"] = k2.number_input("建物面積(㎡)", min_value=0.0, step=0.01,
                                            format="%.2f", key="w_building_area")

st.divider()

# ── 2. 取引事例・売出物件（PDF→AI抽出） ──
st.subheader("② 取引事例・売出物件")
st.caption("PDFをアップして「AIで抽出」→ 下の表に反映され、手修正できます。")

up1, up2 = st.columns(2)
with up1:
    st.markdown("**取引事例 PDF**")
    trade_pdfs = st.file_uploader("取引事例", type=["pdf"], accept_multiple_files=True,
                                  key="trade_up", label_visibility="collapsed")
    if st.button("🤖 取引事例をAI抽出", use_container_width=True, disabled=not trade_pdfs):
        got = 0
        with st.spinner("PDFを解析中..."):
            for f in trade_pdfs:
                try:
                    cs = case_extractor.extract_cases(f.getvalue(), f.name, "取引事例", ptype)
                    ss.trades.extend(cs); got += len(cs)
                except Exception as e:
                    st.error(f"{f.name}: {e}")
        st.success(f"{got}件の取引事例を抽出しました"); st.rerun()
with up2:
    st.markdown("**売出物件 PDF**")
    sale_pdfs = st.file_uploader("売出物件", type=["pdf"], accept_multiple_files=True,
                                 key="sale_up", label_visibility="collapsed")
    if st.button("🤖 売出物件をAI抽出", use_container_width=True, disabled=not sale_pdfs):
        got = 0
        with st.spinner("PDFを解析中..."):
            for f in sale_pdfs:
                try:
                    cs = case_extractor.extract_cases(f.getvalue(), f.name, "売出物件", ptype)
                    ss.sales.extend(cs); got += len(cs)
                except Exception as e:
                    st.error(f"{f.name}: {e}")
        st.success(f"{got}件の売出物件を抽出しました"); st.rerun()

st.markdown("**取引事例（編集可）**")
ed_t = st.data_editor(cases_to_df(ss.trades, spec), num_rows="dynamic",
                      use_container_width=True, key="ed_trades")
ss.trades = df_to_cases(ed_t, spec)

st.markdown("**売出物件（編集可）**")
ed_s = st.data_editor(cases_to_df(ss.sales, spec), num_rows="dynamic",
                      use_container_width=True, key="ed_sales")
ss.sales = df_to_cases(ed_s, spec)

with st.expander("参考：周辺相場を取得（不動産情報ライブラリ）"):
    ref_addr = st.text_input("住所", value=subj["address"], key="ref_addr")
    if st.button("📡 参考相場を取得"):
        try:
            with st.spinner("照会中..."):
                geo = geo_service.resolve(ref_addr)
                mtype = "区分マンション" if is_mansion else "土地・戸建"
                md = market_research_service.research(
                    geo.get("pref_code", ""), geo.get("muni_code", ""),
                    geo.get("lat"), geo.get("lng"), mtype)
            if md.koji_unit_price:
                st.info(f"最寄公示地価：{md.koji_unit_price:,}円/㎡（{md.koji_point_name} 約{md.koji_distance_m}m）")
            if md.comparables:
                st.dataframe(pd.DataFrame([
                    {"所在": c.address, "取引価格(万円)": c.trade_price_man,
                     "単価(円/㎡)": c.unit_price, "面積㎡": c.area, "時期": c.trade_period}
                    for c in md.comparables]), use_container_width=True)
            else:
                st.caption("参考データを取得できませんでした（住所精度・APIキーをご確認ください）。")
        except Exception as e:
            st.warning(f"参考相場の取得に失敗しました: {e}")

with st.expander("参考：商圏データを取得（政府統計 e-Stat）"):
    st.caption("世帯数・単身世帯の多さ・転入超過・空き家率など、**その値段で買う人がいるか**を"
               "裏づける公的な数字です。市区町村単位で、調査年つきで取ります。")
    area_addr = st.text_input("住所", value=subj["address"], key="area_addr")
    if st.button("📊 商圏データを取得"):
        try:
            with st.spinner("e-Stat に照会中..."):
                geo = geo_service.resolve(area_addr)
                st.session_state["area_stats"] = area_stats_service.fetch(geo.get("muni_code", ""))
        except Exception as e:
            st.session_state["area_stats"] = {"ok": False, "error": str(e)}
    stats = st.session_state.get("area_stats")
    if stats:
        if not stats.get("ok"):
            st.caption(f"取得できませんでした: {stats.get('error', '')}")
        else:
            hl = stats["highlights"]
            m = st.columns(4)
            m[0].metric("世帯数", f"{stats['values'].get('世帯数', 0):,}")
            m[1].metric("空き家率", f"{hl['空き家率']}%" if hl["空き家率"] else "—")
            m[2].metric("借家率", f"{hl['借家率']}%" if hl["借家率"] else "—")
            m[3].metric("社会増減", f"{hl['社会増減']:+,}人" if hl["社会増減"] is not None else "—")
            st.dataframe(pd.DataFrame(stats["rows"]), use_container_width=True, hide_index=True)
            st.caption("査定書の所見にそのまま貼れる形（コピーして使ってください）")
            st.code(stats["summary"], language=None)

st.divider()

# ── 3. 加点・減点ポイント ──
st.subheader("③ 加点・減点ポイント（評点）")
st.caption("要因とポイントはプルダウンから選択。土地/建物/両方の区分も選べます。"
           "合計評点は安全のため±50点（倍率50〜150%）の範囲に制限されます。")


def points_df(lst):
    if not lst:
        rows = [{"要因": None, "区分": "両方", "点": None}]
    else:
        rows = [{"要因": p.get("factor") or None, "区分": p.get("kubun", "両方"),
                 "点": (p.get("point") or None)} for p in lst]
    return pd.DataFrame(rows)


def points_cfg(factor_options):
    return {
        "要因": st.column_config.SelectboxColumn("要因", options=factor_options, required=False, width="large"),
        "区分": st.column_config.SelectboxColumn("区分", options=sc.KUBUN_OPTIONS, required=False),
        "点": st.column_config.SelectboxColumn("点", options=sc.POINT_CHOICES, required=False),
    }


pp, mm = st.columns(2)
with pp:
    st.markdown("**加点ポイント**")
    ed_p = st.data_editor(points_df(ss.plus), num_rows="dynamic", use_container_width=True,
                          key="ed_plus", column_config=points_cfg(sc.PLUS_FACTORS))
with mm:
    st.markdown("**減点ポイント**")
    ed_m = st.data_editor(points_df(ss.minus), num_rows="dynamic", use_container_width=True,
                          key="ed_minus", column_config=points_cfg(sc.MINUS_FACTORS))


def df_to_points(df):
    out = []
    for _, r in df.iterrows():
        f = r.get("要因")
        if pd.isna(f) or not str(f).strip():
            continue
        pt = r.get("点")
        pt = 0 if pd.isna(pt) else int(num(pt, 0))
        out.append({"factor": str(f).strip(), "kubun": (r.get("区分") or "両方"), "point": pt})
    return out


ss.plus = df_to_points(ed_p)
ss.minus = df_to_points(ed_m)
_net = sc.total_point(ss.plus, ss.minus)
if abs(_net) > sc.MAX_NET_POINT:
    st.warning(f"合計評点 {_net:+d} 点は範囲外のため ±{sc.MAX_NET_POINT}点に制限して計算します。")

st.divider()

# ── 4. 単価・査定計算 ──
st.subheader("④ 単価と査定計算")
st.markdown("**流通性比率（％）** — 売れ易さによる最終調整（原則±7%＝93〜107%）。"
            "2通りの算出を見比べて採用できます。")
rb1, rb2 = st.columns(2)
if rb1.button("🧮 取引事例から算出", use_container_width=True):
    ss.ryutsu_trades = ryutsu_service.from_trades(ss.trades, ss.sales)
    st.rerun()
if rb2.button("🌐 AIで総合判断（Web相場調査）", use_container_width=True):
    with st.spinner("相場を調査中..."):
        try:
            ss.ryutsu_ai = ryutsu_service.suggest_ryutsu(
                property_type=ptype, subject=subj, trades=ss.trades, sales=ss.sales)
        except Exception as e:
            st.error(str(e))
    st.rerun()

# 2案を並べて表示
ca, cb = st.columns(2)
with ca:
    st.markdown("**🧮 取引事例ベース**")
    if ss.ryutsu_trades:
        st.metric("提案比率", f"{ss.ryutsu_trades['ratio']} %", help=ss.ryutsu_trades.get("basis", ""))
        st.caption(ss.ryutsu_trades["reason"])
    else:
        st.caption("「取引事例から算出」を押すと、成約事例の単価推移から算出します。")
with cb:
    st.markdown("**🌐 AI総合判断**")
    if ss.ryutsu_ai:
        st.metric("提案比率", f"{ss.ryutsu_ai['ratio']} %")
        st.caption(ss.ryutsu_ai["reason"])
    else:
        st.caption("「AIで総合判断」を押すと、Web相場調査＋事例から提案します。")

# 採用方法を選択
opts = []
if ss.ryutsu_trades:
    opts.append("取引事例ベース")
if ss.ryutsu_ai:
    opts.append("AI総合判断")
opts.append("手動")
choice = st.radio("採用する流通性比率", opts, horizontal=True, key="ryutsu_choice")
if choice != ss.ryutsu_choice_prev:
    if choice == "取引事例ベース" and ss.ryutsu_trades:
        ss.ryutsu = ss.ryutsu_trades["ratio"]
    elif choice == "AI総合判断" and ss.ryutsu_ai:
        ss.ryutsu = ss.ryutsu_ai["ratio"]
    ss.ryutsu_choice_prev = choice
ryutsu = st.slider("流通性比率（％・微調整可）", min_value=70, max_value=120, value=int(ss.ryutsu), step=1)
ss.ryutsu = ryutsu
if choice == "取引事例ベース" and ss.ryutsu_trades:
    ss.ryutsu_reason = f"【取引事例】{ss.ryutsu_trades['reason']}"
elif choice == "AI総合判断" and ss.ryutsu_ai:
    ss.ryutsu_reason = f"【AI総合判断】{ss.ryutsu_ai['reason']}"
else:
    ss.ryutsu_reason = "手動設定"
if is_mansion:
    u1, u2 = st.columns(2)
    sugg = avg_unit(ss.trades) or avg_unit(ss.sales)
    case_unit = u1.number_input("事例単価(円/㎡)", min_value=0, step=1000, value=int(sugg),
                                help="採用取引事例の単価。空欄時は事例平均を提案。")
    calc = sc.calc_mansion(case_unit, num(subj["exclusive_area"]), ss.plus, ss.minus, ryutsu)
    u2.metric("評点計", f"{calc['point']:+d} 点")
    st.caption(f"試算価格 {calc['base']:,}円 × 流通性比率 {ryutsu}% = {calc['total']:,}円")
else:
    u1, u2, u3 = st.columns(3)
    sugg = avg_unit(ss.trades) or avg_unit(ss.sales)
    land_unit = u1.number_input("土地事例単価(円/㎡)", min_value=0, step=1000, value=int(sugg))
    building_unit = u2.number_input("再調達単価(円/㎡)", min_value=0, step=1000, value=150000,
                                    help="建物の再調達単価。木造15万円/㎡等を目安に。")
    calc = sc.calc_kodate(land_unit, num(subj["land_area"]), building_unit,
                          num(subj["building_area"]), ss.plus, ss.minus, ryutsu)
    u3.metric("土地/建物 評点", f"{calc['land_point']:+d} / {calc['building_point']:+d}")
    cc1, cc2, cc3 = st.columns(3)
    cc1.metric("土地価格(A)", f"{calc['land_value']:,} 円")
    cc2.metric("建物価格(B)", f"{calc['building_value']:,} 円")
    cc3.metric(f"×流通性比率{ryutsu}%", f"{calc['total']:,} 円")

st.markdown(f"### 自動算出の査定価格： **{calc['total']:,} 円**")
final = st.number_input("最終査定価格（手修正可・円）", min_value=0, step=10000, value=int(calc["total"]))
calc["total"] = int(final)

st.divider()

# ── 5. 査定の根拠（説明書） ──
st.subheader("⑤ 査定価格の説明書（査定の根拠）")
note = st.text_input("担当者メモ（AI生成に反映・任意）", placeholder="例：高台で日当たり・眺望良好。流通性高く105%。")
if st.button("🤖 査定の根拠をAI生成"):
    with st.spinner("生成中..."):
        try:
            ss.explanation = explanation_service.generate_explanation(
                property_type=ptype, subject=subj, trades=ss.trades, calc=calc,
                ryutsu_ratio=f"{ryutsu}%", note=note)
        except Exception as e:
            st.error(str(e))
    st.rerun()
ss.explanation = st.text_area("査定の根拠（編集可）", value=ss.explanation, height=160)

st.divider()

# ── 6. 出力 ──
st.subheader("⑥ 査定書を出力")
if not customer:
    st.info("お客様氏名を入力すると出力できます。")
else:
    company = sc.load_company()
    data = satei_report.build_report(
        property_type=ptype, subject=subj, trades=ss.trades, sales=ss.sales,
        plus=ss.plus, minus=ss.minus, units={}, calc=calc, company=company,
        customer=customer, satei_date=wareki(satei_d), expiry=wareki(expiry_d),
        explanation=ss.explanation,
        area_stats_text=(st.session_state.get("area_stats") or {}).get("summary", ""))
    label = "戸建" if not is_mansion else "マンション"
    st.download_button(
        f"📊 査定書3枚セット（{label}）をExcelでダウンロード",
        data=data,
        file_name=f"査定書_{label}_{customer}_{satei_d.strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True)
    st.caption("① 市場価格分析表 ② 価格査定書 ③ 査定価格の説明書 の3シート構成（A4縦）です。")
