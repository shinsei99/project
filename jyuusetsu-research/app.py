"""AI重説調査〜Excel自動入力システム（Streamlit）。

入力（住所・登記簿PDF）→ 調査（無料データ）→ 整理（PropertyData）→ 出力（Excel/PDF）
の一方向パイプライン。完全自動ではなく「調査支援・下書き生成」を目的とする。
"""

import os
import sys

import streamlit as st
import streamlit.components.v1 as components

from models.property_data import create_property_data, merge
from services import (
    address_service,
    comment_service,
    excel_export_service,
    format_catalog,
    facility_service,
    hazard_service,
    pdf_export_service,
    population_service,
    registry_service,
    zoning_service,
)
from utils import formatter

# 直下の共通クライアント（google_maps_api.py）。キーが無ければ使わないだけ。
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import google_maps_api
except Exception:
    google_maps_api = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(BASE_DIR, "templates", "jyuusetsu_template.xlsx")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

st.set_page_config(page_title="AI重説調査システム", page_icon="🏠", layout="wide")


def run_pipeline(address, land_pdf, building_pdf):
    """入力 → 調査 → 整理 を実行し PropertyData と付随情報を返す。"""
    data = create_property_data()
    facilities = {}
    hazard_url = hazard_service.hazard_link(None, None)
    coords = None
    coords_source = ""

    # ① 住所からの自動調査
    if address:
        with st.spinner("住所を調査中（国土地理院・最寄駅）..."):
            addr_result = address_service.investigate(address)
            merge(data, addr_result["data"])
            coords = addr_result["coords"]
            coords_source = addr_result.get("coords_source", "")

        if coords:
            lat, lon = coords
            hazard_url = hazard_service.hazard_link(lat, lon)
            with st.spinner("都市計画・災害・周辺施設を調査中..."):
                merge(data, zoning_service.get_zoning(lat, lon))
                merge(data, hazard_service.get_hazard(lat, lon))
                facilities = facility_service.nearby_facilities(lat, lon)
            merge(data, population_service.get_population(address, coords))
        else:
            st.warning("住所から位置を特定できませんでした。住所表記をご確認ください。")

    # ② 登記簿 PDF 解析
    if land_pdf is not None or building_pdf is not None:
        with st.spinner("登記簿PDFを解析中..."):
            merge(data, registry_service.parse_registry(land_pdf, building_pdf))

    return data, facilities, hazard_url, coords, coords_source


def render_streetview(coords, address):
    """現地の見え方（ストリートビュー）。

    **規約**: Street View の Embed は無制限・無料だが、**印刷物には一切使えない**。
    また Google 以外の地図（地理院地図・ハザードマップ）と同一画面に並べない
    （この画面はハザードマップを"リンク"で置くだけで地図は描画していない）。
    """
    st.subheader("🛣 現地の見え方（ストリートビュー）")
    if not coords:
        st.caption("※ 住所から位置を特定できていないため表示できません。")
        return
    if google_maps_api is None or not google_maps_api.embed_key():
        st.caption(
            "※ 埋め込み用キー（直下 .env.google-maps の GOOGLE_MAPS_EMBED_KEY "
            "／無ければ GOOGLE_MAPS_WEB_KEY）が未設定のため表示していません。"
        )
        return

    lat, lon = coords
    meta = google_maps_api.streetview_metadata(lat, lon)
    if not meta:
        st.caption("※ この地点の周辺50mにストリートビューの撮影がありません。")
        return

    url = google_maps_api.streetview_embed_url(lat, lon)
    if not url:
        st.caption("※ 埋め込みURLを生成できませんでした。")
        return
    components.iframe(url, height=420)
    if not google_maps_api._load_env().get("GOOGLE_MAPS_EMBED_KEY"):
        st.caption(
            "※ 社内画面用の GOOGLE_MAPS_EMBED_KEY が未設定です。公開ページ用キーは"
            "リファラが daikyocorp.co.jp に限定されているため、ここは 403 になります"
            "（Maps Embed だけに制限したキーを作って .env.google-maps に追記してください）。"
        )
    st.caption(
        "撮影時期: {} ／ 画面で確認する用途のみ。**印刷物（チラシ・DM・重説の紙面）には使用不可**"
        "（Google Geo Guidelines）。".format(meta.get("date") or "不明")
    )


def render_section(title, fields):
    st.subheader(title)
    cols = st.columns(2)
    items = list(fields.items())
    for i, (key, value) in enumerate(items):
        with cols[i % 2]:
            st.markdown("**{}**：{}".format(key, formatter.safe(value)))


def main():
    st.title("🏠 AI重説調査 〜 Excel自動入力システム")
    st.caption(
        "住所と登記簿PDFから重要事項説明書のドラフトを生成する調査支援ツール。"
        "無料公開データのみ使用。最終確認は宅地建物取引士が行ってください。"
    )

    with st.sidebar:
        st.header("① 作る書類を選ぶ")
        catalog_error = format_catalog.status_message()
        if catalog_error:
            st.error(catalog_error)
            category, entry = None, None
        else:
            category = st.selectbox("書類の分類", options=format_catalog.categories())
            entries = format_catalog.formats_in(category)
            entry = st.selectbox(
                "書式（全宅連 公式）",
                options=entries,
                format_func=format_catalog.label,
            )
            st.caption("{} 分類 / この分類に {} 本".format(
                len(format_catalog.categories()), len(entries)))

        st.divider()
        st.header("② 物件情報を入力")
        address = st.text_input("住所（必須）", placeholder="例：東京都千代田区丸の内1-1-1")
        land_pdf = st.file_uploader("登記事項証明書（土地PDF）", type=["pdf"])
        building_pdf = st.file_uploader("登記事項証明書（建物PDF）", type=["pdf"])
        st.file_uploader("物件概要書PDF（任意・将来対応）", type=["pdf"], disabled=True)
        run = st.button("調査を実行", type="primary", use_container_width=True)

        st.divider()
        st.caption("外部データのキー（未設定の項目は空欄で継続します）")
        st.code(
            "REINFOLIB_API_KEY  # 用途地域（.streamlit/secrets.toml でも可）\n"
            "ESTAT_APP_ID       # 人口・世帯（直下 .env.estat でも可）\n"
            "GOOGLE_MAPS_*      # 座標の精度・ストリートビュー（直下 .env.google-maps）",
            language="text",
        )

    if not run:
        st.info("左の入力欄に住所を入れ、必要に応じてPDFを添付して「調査を実行」を押してください。")
        return

    if not address and land_pdf is None and building_pdf is None:
        st.error("住所、または登記簿PDFのいずれかを入力してください。")
        return

    data, facilities, hazard_url, coords, coords_source = run_pipeline(
        address, land_pdf, building_pdf
    )
    comment = comment_service.generate_comment(data)

    # ===== 結果画面 =====
    render_section("📌 基本情報", formatter.section_basic(data))
    if coords:
        st.caption(
            "座標: {:.6f}, {:.6f}（出典 {}）。用途地域・災害情報はこの地点で判定しています。".format(
                coords[0], coords[1], coords_source or "不明"
            )
        )
    st.divider()

    render_section("🏛 都市計画 / 法令制限", formatter.section_city_planning(data))
    if not data.get("用途地域"):
        st.caption("※ 用途地域はREINFOLIB_API_KEY未設定のため未取得。自治体都市計画図でご確認ください。")
    st.divider()

    render_section("🌊 災害情報", formatter.section_hazard(data))
    st.markdown("[🔗 重ねるハザードマップで該当地点を確認]({})".format(hazard_url))
    st.divider()

    render_section("🚉 周辺環境", formatter.section_environment(data))
    if facilities:
        fcols = st.columns(4)
        for i, (cat, names) in enumerate(facilities.items()):
            with fcols[i % 4]:
                st.markdown("**{}**".format(cat))
                if names:
                    for n in names:
                        st.markdown("- {}".format(n))
                else:
                    st.markdown("- （周辺に該当なし/未取得）")
    st.divider()

    render_streetview(coords, address)
    st.divider()

    render_section("📄 登記情報", formatter.section_registry(data))
    st.divider()

    st.subheader("📝 AIコメント（下書き）")
    st.write(comment)
    st.divider()

    # ===== 公式書式への流し込み =====
    st.subheader("📥 公式書式へ流し込んで書類を作る")
    if entry is None:
        st.error(format_catalog.status_message() or "書式が選ばれていません。")
    else:
        st.markdown("選択中：**{}**（{}）".format(entry["name"], category))
        got = format_catalog.filled_fields(entry, data)
        st.caption(
            "この書式に自動で入るのは {} 項目：{}".format(len(got), "・".join(got) or "（該当なし）")
        )
        docs = format_catalog.document_sheets(entry)
        if entry.get("fanout_count") and len(docs) > 1:
            st.info(
                "この書式は **重要事項説明書に入力すると他の書類へ自動転記される**作りです。"
                "1ファイルで {} 書類が同時に仕上がります：{}".format(len(docs), " / ".join(docs))
            )
        st.caption(
            "賃料・売買代金・手付金・引渡日などの取引条件は自動では入りません（どのデータにも無いため）。"
            "選択欄やチェック欄も書式の既定のまま残します。最終確認は宅地建物取引士が行ってください。"
        )
        try:
            out = format_catalog.generate(entry, data, os.path.join(REPORTS_DIR, "official"))
            mime = (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                if out.lower().endswith(".docx")
                else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            with open(out, "rb") as f:
                st.download_button(
                    "「{}」をダウンロード".format(entry["name"]),
                    f.read(),
                    file_name=os.path.basename(out),
                    mime=mime,
                    use_container_width=True,
                )
        except Exception as e:
            st.error("書式への流し込みに失敗しました: {}".format(e))
    st.divider()

    # ===== ダウンロード（汎用ドラフト） =====
    st.subheader("⬇️ 汎用ドラフトのダウンロード")
    col1, col2 = st.columns(2)
    try:
        excel_path = excel_export_service.export_excel(
            data, comment, TEMPLATE_PATH, os.path.join(REPORTS_DIR, "jyuusetsu_draft.xlsx")
        )
        with open(excel_path, "rb") as f:
            col1.download_button(
                "Excel（汎用ドラフト）をダウンロード",
                f.read(),
                file_name="jyuusetsu_draft.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
    except Exception as e:
        col1.error("Excel生成に失敗しました: {}".format(e))

    try:
        pdf_path = pdf_export_service.export_pdf(
            data, comment, os.path.join(REPORTS_DIR, "jyuusetsu_draft.pdf")
        )
        with open(pdf_path, "rb") as f:
            col2.download_button(
                "PDF（調査報告）をダウンロード",
                f.read(),
                file_name="jyuusetsu_draft.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
    except Exception as e:
        col2.error("PDF生成に失敗しました: {}".format(e))


if __name__ == "__main__":
    main()
