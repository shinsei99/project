# -*- coding: utf-8 -*-
"""事業計画案ジェネレーター（不動産取得の投資収支）。

会長の既存「事業計画案」約80本の共通様式を踏襲し、
物件情報・資金条件を入力すると収支／利回り／CF／諸費用を自動計算、
Excel（元様式再現＋数式ライブ再計算）で出力する。

入力は手入力に加え、謄本・マイソク PDF を AI 読取して自動プリフィル可能
（baikai-generator の registry_parser を再利用）。
"""

import os
import re
import sys
import shutil

import streamlit as st

from services.proforma import Inputs, compute

HERE = os.path.dirname(os.path.abspath(__file__))
BAIKAI_SERVICES = os.path.join(os.path.dirname(HERE), "baikai-generator", "services")

# 直下の共有モジュール（area_stats / estat_api）を読めるようにする
_ROOT = os.path.dirname(HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

st.set_page_config(page_title="事業計画案ジェネレーター", page_icon="🏢", layout="wide")


# ---------------------------------------------------------------------------
# 謄本／マイソク PDF 解析（registry_parser 再利用）
# ---------------------------------------------------------------------------
def _get_registry_parser():
    if BAIKAI_SERVICES not in sys.path:
        sys.path.insert(0, BAIKAI_SERVICES)
    import registry_parser as rp
    rp.CLAUDE_BIN = shutil.which("claude") or rp.CLAUDE_BIN
    return rp


def _num(s) -> float:
    """文字列から最初の数値を取り出す（'330.57㎡' → 330.57, 全角対応）。"""
    if s is None:
        return 0.0
    t = str(s).translate(str.maketrans("０１２３４５６７８９．，",
                                       "0123456789.,")).replace(",", "")
    m = re.search(r"\d+(?:\.\d+)?", t)
    return float(m.group()) if m else 0.0


def _prefill_from_pdf(parsed: dict) -> dict:
    """registry_parser の出力 → フォーム初期値。"""
    pre = {}
    pre["所在地"] = parsed.get("物件所在地") or parsed.get("土地", {}).get("所在", "")
    tochi = parsed.get("土地", {})
    tatemono = parsed.get("建物", {})
    mansion = parsed.get("マンション", {})
    pre["敷地面積"] = _num(tochi.get("地積"))
    # 構造・延床・築年（建物 or マンション）
    pre["建物構造"] = tatemono.get("構造") or mansion.get("構造", "")
    pre["延床面積"] = _num(tatemono.get("延床面積") or tatemono.get("床面積")
                          or mansion.get("専有面積"))
    pre["築年"] = tatemono.get("新築年月日") or mansion.get("新築年月日", "")
    return {k: v for k, v in pre.items() if v}


def _init_state():
    if "prefill" not in st.session_state:
        st.session_state.prefill = {}


_init_state()


# ---------------------------------------------------------------------------
# 画面
# ---------------------------------------------------------------------------
st.title("🏢 事業計画案ジェネレーター")
st.caption("物件情報・資金条件を入力 → 収支・利回り・CF・諸費用を自動計算し、Excel（元様式）で出力します。金額の単位は万円。")

with st.expander("📄 謄本・マイソクPDFから自動入力（任意）", expanded=False):
    st.caption("登記簿PDF等をアップして解析すると、所在地・面積・構造・築年を下のフォームに反映します（下書き。要確認）。")
    pdfs = st.file_uploader("PDFを選択（複数可）", type=["pdf"], accept_multiple_files=True,
                            key="pdf_up")
    if st.button("PDFを解析して反映", disabled=not pdfs):
        with st.spinner("AIが解析中…（数十秒かかる場合があります）"):
            try:
                rp = _get_registry_parser()
                parsed = rp.parse_registry(pdfs)
                st.session_state.prefill = _prefill_from_pdf(parsed)
                st.success("解析しました。下のフォームに反映しています。内容を確認・修正してください。")
            except Exception as e:  # noqa: BLE001
                st.error(f"解析に失敗しました: {e}")

pf = st.session_state.prefill


def d(key, default):
    return pf.get(key, default)


# ---- 入力フォーム ----
tab1, tab2, tab3, tab4 = st.tabs(["① 物件概要", "② 資金計画・収入", "③ 支出・借入", "④ 諸費用の率"])

with tab1:
    c1, c2 = st.columns(2)
    with c1:
        物件名 = st.text_input("物件名", value="")
        所在地 = st.text_input("所在地", value=d("所在地", ""))
        敷地面積 = st.number_input("敷地面積（㎡）", min_value=0.0, value=float(d("敷地面積", 0.0)), step=0.01)
        延床面積 = st.number_input("延床面積（㎡）", min_value=0.0, value=float(d("延床面積", 0.0)), step=0.01)
        建物構造 = st.text_input("建物構造・階数", value=d("建物構造", ""), placeholder="例: RC造 地上6階")
        戸数 = st.text_input("戸数・タイプ", value="", placeholder="例: 14戸（ファミリータイプ）")
    with c2:
        駐車場 = st.text_input("駐車場", value="", placeholder="例: パーキング10台")
        築年 = st.text_input("築年", value=d("築年", ""), placeholder="例: H5年3月 / 2003")
        用途地域 = st.text_input("用途地域", value="", placeholder="例: 第1種 / 近隣商業地域")
        cc1, cc2 = st.columns(2)
        建ぺい率 = cc1.text_input("建ぺい率（％）", value="")
        容積率 = cc2.text_input("容積率（％）", value="")
        交通 = st.text_input("交通", value="", placeholder="例: 京阪野江駅 徒歩6分")
        基準日 = st.text_input("作成日", value="", placeholder="例: 2026/07/28")
    スキーム文 = st.text_area("取得スキーム文", value="上記物件を取得し、自社で運営・管理し家賃収入で借入金の返済にあたる。", height=68)

    # ── 商圏データ（政府統計 e-Stat）──────────────────────────────
    # 「この賃料で埋まるのか」を裏づける公的な数字。金融機関へ出す計画の前提に使う。
    # 計算は直下の共有モジュール area_stats.py（査定アプリ8509と同じ実体）。
    with st.expander("📊 商圏データ（政府統計 e-Stat）— 賃貸需要の裏づけ"):
        st.caption("所在地の市区町村の世帯数・単身率・転入超過・空き家率・借家率を取ります。"
                   "**調査年つきの公的データ**なので、そのまま計画書の前提に書けます。")
        if st.button("📊 所在地から取得", key="area_stats_fetch", disabled=not 所在地.strip()):
            try:
                import area_stats  # 直下の共有モジュール（査定アプリ8509と同じ実体）

                with st.spinner("e-Stat に照会中..."):
                    st.session_state["bp_area_stats"] = area_stats.fetch_by_address(所在地)
            except Exception as e:
                st.session_state["bp_area_stats"] = {"ok": False, "error": str(e)}
        stats = st.session_state.get("bp_area_stats")
        if stats:
            if not stats.get("ok"):
                st.caption("取得できませんでした: {}".format(stats.get("error", "")))
            else:
                hl = stats["highlights"]
                m = st.columns(4)
                m[0].metric("世帯数", "{:,}".format(stats["values"].get("世帯数", 0)))
                m[1].metric("借家率", "{}%".format(hl["借家率"]) if hl["借家率"] else "—")
                m[2].metric("空き家率", "{}%".format(hl["空き家率"]) if hl["空き家率"] else "—")
                m[3].metric("社会増減",
                            "{:+,}人".format(hl["社会増減"]) if hl["社会増減"] is not None else "—")
                st.caption("計画書の前提にそのまま貼れる形（コピーして使ってください）")
                st.code(stats["summary"], language=None)

with tab2:
    st.subheader("資金計画（万円）")
    c1, c2, c3 = st.columns(3)
    土地代 = c1.number_input("土地代", min_value=0.0, value=0.0, step=100.0)
    建物代 = c2.number_input("建物代", min_value=0.0, value=0.0, step=100.0)
    消費税 = c3.number_input("消費税（0で建物代×税率を自動）", min_value=0.0, value=0.0, step=10.0)
    設備代 = c1.number_input("設備代（パーキング等）", min_value=0.0, value=0.0, step=10.0)
    保証金 = c2.number_input("保証金・建設協力金（相殺）", min_value=0.0, value=0.0, step=10.0)
    借入総額 = c3.number_input("借入総額", min_value=0.0, value=0.0, step=100.0,
                             help="丸めた借入額を入力。自己資金＝総事業費−保証金−借入 で表示されます。")
    st.subheader("評価額（諸費用計算用・万円）")
    e1, e2 = st.columns(2)
    土地評価額 = e1.number_input("土地評価額", min_value=0.0, value=0.0, step=100.0)
    建物評価額 = e2.number_input("建物評価額", min_value=0.0, value=0.0, step=100.0)
    st.subheader("収入（万円）")
    i1, i2 = st.columns(2)
    月額賃料 = i1.number_input("月額賃料", min_value=0.0, value=0.0, step=1.0)
    協力金返済月 = i2.number_input("建設協力金 返済/月（控除）", min_value=0.0, value=0.0, step=1.0)

with tab3:
    st.subheader("支出（万円）")
    s1, s2, s3 = st.columns(3)
    固都税土地 = s1.number_input("固定資産税・土地（年）", min_value=0.0, value=0.0, step=1.0)
    固都税建物 = s2.number_input("固定資産税・建物（年）", min_value=0.0, value=0.0, step=1.0)
    火災保険 = s3.number_input("火災保険（年）", min_value=0.0, value=0.0, step=1.0)
    管理費月 = s1.number_input("管理費計/月（EV・清掃・受水槽・消防・電気等）", min_value=0.0, value=0.0, step=0.5)
    リフォーム代 = s2.number_input("リフォーム代（一時）", min_value=0.0, value=0.0, step=10.0)
    法人税 = s3.number_input("法人税（CF用・年）", min_value=0.0, value=0.0, step=10.0)
    st.subheader("借入・償却")
    b1, b2, b3 = st.columns(3)
    借入金利 = b1.number_input("借入金利（％）", min_value=0.0, value=0.5, step=0.05, format="%.2f")
    借入年数 = b2.number_input("借入年数（年）", min_value=1, value=10, step=1)
    法定耐用年数 = b3.number_input("法定耐用年数（RC47/鉄骨34/木22）", min_value=1, value=47, step=1)
    築年数 = b1.number_input("築年数（経過年数）", min_value=0, value=0, step=1,
                          help="償却年数 = 法定耐用年数 − 築年数（下限2年）")

with tab4:
    st.caption("house-style の既定値入り。案件に応じて調整してください。")
    r1, r2, r3 = st.columns(3)
    登免税土地率 = r1.number_input("登録免許税・土地率（％）", value=1.5, step=0.1, format="%.2f")
    登免税建物率 = r2.number_input("登録免許税・建物率（％）", value=2.0, step=0.1, format="%.2f")
    抵当権率 = r3.number_input("抵当権設定率（％）", value=0.4, step=0.05, format="%.2f")
    仲介料率 = r1.number_input("仲介料率（％）", value=3.0, step=0.1, format="%.2f")
    仲介料加算 = r2.number_input("仲介料加算（万）", value=6.0, step=1.0)
    消費税率 = r3.number_input("消費税率（％）", value=10.0, step=1.0)
    取得税土地率 = r1.number_input("不動産取得税・土地率（％）", value=3.0, step=0.1, format="%.2f")
    取得税建物率 = r2.number_input("不動産取得税・建物率（％）", value=3.0, step=0.1, format="%.2f")
    土地取得税減額 = r3.number_input("土地取得税 減額係数（1/2=0.5）", value=0.5, step=0.05, format="%.2f")
    f1, f2, f3 = st.columns(3)
    印紙 = f1.number_input("印紙（万・0で自動）", value=0.0, step=1.0,
                          help="0のとき売買価格から2024軽減税率で自動算定（例:1億超=16万）")
    司法書士その他 = f2.number_input("司法書士・その他（万）", value=20.0, step=1.0)
    予備費 = f3.number_input("予備費（万）", value=0.0, step=1.0)


inp = Inputs(
    物件名=物件名, 所在地=所在地, 敷地面積=敷地面積, 延床面積=延床面積,
    建物構造=建物構造, 戸数=戸数, 駐車場=駐車場, 築年=築年, 用途地域=用途地域,
    建ぺい率=建ぺい率, 容積率=容積率, 交通=交通, 基準日=基準日, スキーム文=スキーム文,
    土地代=土地代, 建物代=建物代, 消費税=消費税, 設備代=設備代, 保証金=保証金,
    借入総額=借入総額, 土地評価額=土地評価額, 建物評価額=建物評価額,
    借入金利=借入金利, 借入年数=int(借入年数), 月額賃料=月額賃料, 協力金返済月=協力金返済月,
    固都税土地=固都税土地, 固都税建物=固都税建物, 火災保険=火災保険, リフォーム代=リフォーム代,
    管理費月=管理費月, 法定耐用年数=int(法定耐用年数), 築年数=int(築年数), 法人税=法人税,
    登免税土地率=登免税土地率, 登免税建物率=登免税建物率, 仲介料率=仲介料率,
    仲介料加算=仲介料加算, 消費税率=消費税率, 抵当権率=抵当権率,
    取得税土地率=取得税土地率, 取得税建物率=取得税建物率, 土地取得税減額=土地取得税減額,
    印紙=印紙, 司法書士その他=司法書士その他, 予備費=予備費,
)

res = compute(inp)

# ---- 結果プレビュー ----
st.divider()
st.subheader("📊 収支サマリー")
m = st.columns(5)
m[0].metric("総事業費", f"{res['資金計画']['総事業費']:,.0f}万")
m[1].metric("借入 / 自己資金", f"{res['資金計画']['借入総額']:,.0f} / {res['資金計画']['自己資金']:,.0f}万")
m[2].metric("年収", f"{res['収入']['年収']:,.0f}万")
m[3].metric("実利回り", f"{res['利回り']['実利回り']}％")
m[4].metric("単純利回り", f"{res['利回り']['単純利回り']}％")

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown("**支出（年・万）**")
    sx = res["支出"]
    st.write(f"固都税 土地/建物: {sx['固都税土地']}/{sx['固都税建物']}")
    st.write(f"火災保険: {sx['火災保険']}　管理費(年): {sx['管理費年']}")
    st.write(f"金利(平均): {sx['金利平均']}")
    st.write(f"償却(定額 {sx['償却年数']}年): {sx['償却']}")
    st.write(f"**支出計(償却込): {sx['支出計_償却込']}**")
with c2:
    st.markdown("**利回り・返済**")
    st.write(f"実利回り: {res['利回り']['実利回り']}％")
    st.write(f"経費・金利込: {res['利回り']['経費込利回り']}％")
    st.write(f"単純利回り: {res['利回り']['単純利回り']}％")
    st.write(f"返済: 年{res['返済']['返済年']} / 月{res['返済']['返済月']}")
    st.write(f"CF 借入あり/なし: {res['CF']['借入あり']} / {res['CF']['借入なし']}")
with c3:
    st.markdown("**諸費用内訳（万）**")
    sh = res["諸費用内訳"]
    st.write(f"登免税 土地/建物: {sh['登免税土地']}/{sh['登免税建物']}")
    st.write(f"仲介料: {sh['仲介料']}　抵当権: {sh['抵当権設定']}")
    st.write(f"取得税 土地/建物: {sh['取得税土地']}/{sh['取得税建物']}")
    st.write(f"印紙/司書/予備: {sh['印紙']}/{sh['司法書士その他']}/{sh['予備費']}")
    st.write(f"**合計: {sh['合計']}**")

st.divider()
from services.excel_builder import build_workbook

buf = build_workbook(inp)
fname = f"事業計画案_{(物件名 or '物件').strip()}.xlsx"
st.download_button("⬇️ Excel（事業計画案）をダウンロード", data=buf.getvalue(),
                   file_name=fname,
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                   type="primary")
st.caption("Excelの「前提条件」シートの黄色セルを変えると、利回り・CF等がExcel上で自動再計算されます。")
