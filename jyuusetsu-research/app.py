"""AI重説調査〜Excel自動入力システム（Streamlit）。

入力（住所・登記簿PDF）→ 調査（無料データ）→ 整理（PropertyData）→ 出力（Excel/PDF）
の一方向パイプライン。完全自動ではなく「調査支援・下書き生成」を目的とする。
"""

import os
import sys

import streamlit as st
import streamlit.components.v1 as components

from models.property_data import create_property_data, extend_fields, merge
from services import (
    address_service,
    address_verify_service,
    maisoku_check_service,
    maisoku_service,
    comment_service,
    crosscheck_report_service,
    crosscheck_service,
    excel_export_service,
    format_catalog,
    facility_service,
    document_intake,
    hazard_service,
    landprice_service,
    legal_area_service,
    pdf_export_service,
    population_service,
    registry_service,
    web_law_service,
    zoning_service,
)
from utils import formatter

# 特約条項は直下の共有モジュール（8513 と同じ実体）。コピーしないこと。
try:
    import tokuyaku_core
except Exception:
    tokuyaku_core = None

# 直下の共通クライアント（google_maps_api.py）。キーが無ければ使わないだけ。
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import google_maps_api
except Exception:
    google_maps_api = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(BASE_DIR, "templates", "jyuusetsu_template.xlsx")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

# 追加資料から入る項目を PropertyData の受け入れ対象に足しておく
extend_fields(document_intake.EXTRA_FIELDS)

st.set_page_config(page_title="AI重説調査システム", page_icon="🏠", layout="wide")


def run_pipeline(address, land_pdf, building_pdf, web_law=False):
    """入力 → 調査 → 整理 を実行し PropertyData と付随情報を返す。"""
    data = create_property_data()
    facilities = {}
    hazard_url = hazard_service.hazard_link(None, None)
    hazard_detail = {}
    landprice = {}
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
                # 災害は出典と利用制限（兵庫県など）も画面に出すので detail で受ける
                hazard_detail = hazard_service.get_hazard_detail(lat, lon)
                merge(data, {k: v["値"] for k, v in hazard_detail.items()})
                facilities = facility_service.nearby_facilities(lat, lon)
                # 区域指定（地区計画・都市計画道路・急傾斜地・地すべり・自然公園・立地適正化）
                merge(data, legal_area_service.get_areas(lat, lon))
                # 近傍の標準地から公示地価。ライフラインと前面道路は**参考**（書式には入れない）
                landprice = landprice_service.get_landprice(lat, lon)
                merge(data, {"公示地価": landprice.get("公示地価", "")})
            merge(data, population_service.get_population(address, coords))
        else:
            st.warning("住所から位置を特定できませんでした。住所表記をご確認ください。")

    # ①-b Web調査での補完（任意）。
    # 防火地域・高度地区・日影規制は不動産情報ライブラリに該当レイヤが無いため、
    # ここだけは自治体の都市計画情報をWebで見にいくしかない（実測で確認済み）。
    if web_law and address:
        with st.spinner("自治体の都市計画情報をWeb調査中（最大5分）..."):
            try:
                web = web_law_service.research_web(address, data.get("用途地域", ""))
                web_law_service.merge_into_property(data, web)
                if web.get("備考"):
                    st.caption("Web調査の出典: {}".format(web["備考"]))
            except Exception as e:
                st.warning("Web調査に失敗したため、この項目は空欄のまま続けます: {}".format(e))

    # ② 登記簿 PDF 解析
    #    サイドバーで「📄 謄本を読む」を押していれば、その結果を使い回す。
    #    解析は claude CLI を通すので数十秒かかる。同じPDFを二度読ませない。
    # ④ 追加資料（任意）。サイドバーで「追加資料を読む」を押していれば、その結果を使う
    extra = st.session_state.get("extra_docs")
    if extra:
        merge(data, document_intake.flatten(extra))

    cached = st.session_state.get("registry_data")
    if cached:
        merge(data, cached)
    elif land_pdf is not None or building_pdf is not None:
        with st.spinner("登記簿PDFを解析中..."):
            merge(data, registry_service.parse_registry(land_pdf, building_pdf))

    return data, facilities, hazard_url, coords, coords_source, hazard_detail, landprice


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


def render_tokuyaku(data, items, style, extra):
    """④ 特約条項 — 選んだ項目の本文を生成して Word で出す（売買のみ）。

    カタログも本文生成も**直下の共有モジュールを使う**（8513 と同じ実体）。
    ここに条文の作り方を書かないこと。片方だけ直すと契約書に載る特約がずれる。

    調査済みの `PropertyData` から物件・売主を渡すので、**同じ情報を打ち直さなくてよい**。
    """
    if not items or tokuyaku_core is None:
        return

    st.subheader("📜 特約条項（{} 項目）".format(len(items)))
    ctx = {
        "property": data.get("所在地", ""),
        "seller": data.get("所有者", ""),
        "buyer": "",
    }
    st.caption(
        "物件「{}」／売主「{}」を調査結果から引き継いでいます。買主は空欄のまま生成します。".format(
            ctx["property"] or "（未取得）", ctx["seller"] or "（未取得）"
        )
    )

    if not st.button("本文を生成する（1項目あたり10〜20秒）", key="tok_gen"):
        st.caption("↑ を押すと `claude` CLI で条文を作ります。押すまでは生成しません。")
        st.divider()
        return

    clauses = []
    bar = st.progress(0.0)
    for i, it in enumerate(items, 1):
        try:
            text = tokuyaku_core.generate_clause(it, ctx, style, extra)
        except Exception as e:
            text = "（生成に失敗: {}）".format(e)
        clauses.append({"title": it["title"], "text": text})
        bar.progress(i / len(items))
    bar.empty()

    for idx, c in enumerate(clauses, 1):
        with st.container(border=True):
            st.markdown("**第{}条（{}）**".format(idx, c["title"]))
            st.write(c["text"])

    try:
        st.download_button(
            "特約条項（Word）をダウンロード",
            tokuyaku_core.build_docx(clauses, ctx),
            file_name="tokuyaku.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
    except Exception as e:
        st.error("Word の生成に失敗しました: {}".format(e))
    st.caption("※ AIが作った下書きです。必ず専門家のリーガルチェックと表記統一を行ってください。")
    st.divider()


def render_crosscheck(data, exp_pdf, con_pdf, seller_pro, address):
    """④ クロスチェック — 出来た重説・契約書を、調査結果と突き合わせて検閲する。

    元は独立アプリ `legal-crosscheck` だったものを取り込んだ。
    **行政の正解は、このアプリが調べた PropertyData をそのまま使う**
    （元アプリのモックは持ち込んでいない。理由は crosscheck_service の冒頭）。
    """
    if exp_pdf is None and con_pdf is None:
        return

    st.subheader("🔍 書類クロスチェック（重説・契約書 × 調査結果・謄本）")
    missing = crosscheck_service.missing_basis(data)
    if missing:
        st.warning(
            "次の項目は**調査で値が取れていないため判定できません**（確認不可として出ます）: "
            + "・".join(missing)
        )

    try:
        with st.spinner("重説・契約書を解析して照合中..."):
            cc = crosscheck_service.run(
                data,
                exp_pdf.getvalue() if exp_pdf else None,
                con_pdf.getvalue() if con_pdf else None,
                seller_is_pro=seller_pro,
                address=address,
            )
    except Exception as e:
        st.error("クロスチェックに失敗しました: {}".format(e))
        st.divider()
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("🔴 齟齬・リスク", "{} 件".format(cc.ng_count))
    c2.metric("🟢 一致", "{} 件".format(cc.ok_count))
    c3.metric("検査項目", "{} 件".format(len(cc.results)))

    ng_items = [r for r in cc.results if r.is_ng]
    if ng_items:
        st.error("🚨 {} 件の齟齬・リスクを検出しました。".format(len(ng_items)))
        for r in ng_items:
            with st.container(border=True):
                st.markdown("**[{}] {}**".format(r.category, r.item))
                a, b, c = st.columns(3)
                a.markdown("🌐📄 **基準**\n\n{}".format(r.admin_value or "—"))
                b.markdown("📝 **重説**\n\n{}".format(r.explanation_value or "—"))
                c.markdown("🛒 **契約書**\n\n{}".format(r.contract_value or "—"))
                st.markdown(":red[**修正指示:** {}]".format(r.advice))
    else:
        st.success("重大な齟齬は検出されませんでした（確認不可の項目は上の注意を参照）。")

    with st.expander("全チェック項目を見る（{} 件）".format(len(cc.results))):
        for r in cc.results:
            st.markdown(
                "{} **{}**（{}） … 基準: {} ／ 重説: {} ／ 契約書: {}".format(
                    r.icon, r.item, r.category,
                    r.admin_value or "—", r.explanation_value or "—", r.contract_value or "—",
                )
            )

    try:
        st.download_button(
            "検閲報告書（Excel）をダウンロード",
            crosscheck_report_service.build(cc),
            file_name="crosscheck_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    except Exception as e:
        st.error("報告書の生成に失敗しました: {}".format(e))
    st.divider()


def render_section(title, fields):
    if title:
        st.subheader(title)
    cols = st.columns(2)
    items = list(fields.items())
    for i, (key, value) in enumerate(items):
        with cols[i % 2]:
            st.markdown("**{}**：{}".format(key, formatter.safe(value)))


def render_company_editor():
    """自社（宅建業者・宅建士）情報の編集。サイドバーの中で呼ぶ。

    書式の1枚目には毎回同じことを書く欄が **A欄だけで13箇所**ある。
    ここに1回入れておけば、以後すべての書式に自動で入る（`agent_fields`）。
    値は直下の共有モジュール `company_profile` に保存する（個人情報なので gitignore）。
    """
    try:
        import company_profile
    except Exception:
        st.caption("自社情報モジュールが見つかりません（書式の業者欄は空のまま出ます）。")
        return

    profile = company_profile.load()
    lack = company_profile.missing(profile)

    # **自社が媒介か売主かで、書式の入れる欄が変わる。**
    # 宅建業者売主版は A＝売主 / B・C＝媒介 になっていて、媒介なのに A へ入れると
    # 「媒介なのに売主として署名した書面」になる（2026-08-23 実測で構造を確認）
    st.radio(
        "自社の立場",
        options=["媒介", "売主"],
        horizontal=True,
        key="self_role",
        help="媒介＝仲介として入る（既定）。売主＝自社が宅建業者として売る"
             "（このときは書式も「宅建業者売主」版を選ぶ）。"
             "他社の宅建業者が売主で自社が仲介に入るときは「媒介」です。",
    )

    title = "🏢 自社情報（書式の1枚目に毎回入る）"
    if lack:
        title += "　⚠ 要入力 {}".format(len(lack))
    with st.expander(title, expanded=False):
        st.caption(
            "商号・免許番号・宅建士名など、**物件ごとに変わらない欄**をここで1回だけ決めます。"
            "保証協会と供託所は書式に印刷済みなので入れません。"
        )
        if lack:
            st.warning("空のままだと書面が不完全になります: {}".format("・".join(lack)))

        edited = {}
        with st.form("company_profile_form"):
            for key, label, note in company_profile.FIELDS:
                edited[key] = st.text_input(
                    label, value=profile.get(key, ""), key="cp_" + key,
                    help=note or None,
                )
            paste = st.text_input(
                "（補助）免許番号を1行で貼る", value="",
                help="例: 大阪府知事(10)27334号 → 知事名・更新回数・番号に自動で分けます",
            )
            if st.form_submit_button("保存", type="primary"):
                if paste.strip():
                    parsed = company_profile.parse_license(paste)
                    if parsed:
                        edited.update(parsed)
                    else:
                        st.warning("免許番号を読み取れませんでした。3つの欄に直接入れてください。")
                company_profile.save(edited)
                st.success("保存しました。次に作る書式から反映されます。")
                st.rerun()


def render_extra_document_results():
    """追加資料から読み取った項目を、資料ごとに並べて出す。"""
    results = st.session_state.get("extra_docs") or {}
    shown = {k: v for k, v in results.items()
             if v and any(x and not key.startswith("_") for key, x in v.items())}
    if not shown:
        return
    st.subheader("📑 追加資料から読み取った項目")
    for kind, values in shown.items():
        doc = document_intake.DOC_BY_KEY[kind]
        items = {k: v for k, v in values.items() if v and not k.startswith("_")}
        if not items:
            continue
        st.markdown("**{}**".format(doc["label"]))
        render_section("", items)
    st.caption(
        "読み取った値は調査結果に取り込んでいますが、**書式のどのセルに入れるかは"
        "項目ごとの割り当てが残っています**（現状は画面表示まで）。"
    )
    st.divider()


def render_extra_documents():
    """追加資料（任意）のアップロード欄。上げた分だけ埋まる欄が増える。

    謄本だけでは埋まらない欄が重説には大量にある（区分所有の管理まわりだけで61欄）。
    **上げなければ今までどおり動く**ので、既定は畳んでおく。
    """
    uploads = {}
    with st.expander("➕ 追加資料（任意・上げた分だけ欄が埋まります）", expanded=False):
        st.caption(
            "手元にある資料を上げると、謄本では埋まらない項目を読み取ります。"
            "**読めなかった項目は空のまま**にします（推測で埋めません）。"
        )
        for doc in document_intake.DOCS:
            uploads[doc["key"]] = st.file_uploader(
                doc["label"], type=["pdf"], key="doc_" + doc["key"], help=doc["help"])
        if any(v is not None for v in uploads.values()):
            if st.button("📑 追加資料を読む", use_container_width=True):
                with st.spinner("追加資料を解析中…（1件あたり30〜60秒）"):
                    st.session_state["extra_docs"] = document_intake.parse_all(uploads)
        results = st.session_state.get("extra_docs") or {}
        for kind, values in results.items():
            label = document_intake.DOC_BY_KEY[kind]["label"]
            if values.get("_error"):
                st.warning("{}：{}".format(label, values["_error"]))
            else:
                got = len([v for k, v in values.items() if v and not k.startswith("_")])
                st.success("{}：{} 項目を読み取りました".format(label, got))
    return uploads


def render_landprice(landprice):
    """近傍の標準地（地価公示・地価調査）の情報。

    **前面道路とライフラインは「その標準地」の状況**であって当該物件のものではない。
    重説の道路欄・ライフライン欄にそのまま書くと誤りになるので、
    参考であることを明示し、書式には入れない（`公示地価` だけ PropertyData に入る）。
    """
    if not landprice or not landprice.get("公示地価"):
        return
    st.markdown("**近傍の標準地（{}）** — 公示地価 {}".format(
        landprice.get("_距離", ""), landprice.get("公示地価", "")))
    bits = [x for x in (landprice.get("_区域区分"), landprice.get("_用途地域"),
                        landprice.get("_前面道路"), landprice.get("_ライフライン")) if x]
    if bits:
        st.caption("参考（標準地の状況。**当該物件のものではない**）: " + " ／ ".join(bits))


def render_hazard_notes(hazard_detail):
    """災害情報の出典と、出典側が課している利用制限を必ず画面に出す。

    土砂災害警戒区域データは**兵庫県が「重要事項の説明等の根拠としないで下さい」と
    明記している**（当社の営業エリアが該当する）。取れた値をそのまま重説の根拠に
    できると思われては困るので、値のすぐ下に出す。
    """
    if not hazard_detail:
        return
    for key, info in hazard_detail.items():
        if info.get("注意"):
            st.warning("**{}**：{}".format(key, info["注意"]))
    if any(info.get("値") for info in hazard_detail.values()):
        sources = sorted({info["出典"] for info in hazard_detail.values() if info.get("値")})
        st.caption("出典: {}".format(" ／ ".join(sources)))
    st.caption(
        "「区域外」は**その地点のタイルに区域データがある上で外**と判定したもの。"
        "データが1件も無いときは空欄（＝判定不可）にしてある。"
        "書式へは**土砂災害の「内」だけ**自動でチェックが入る"
        "（津波は浸水想定と災害警戒区域が別制度、洪水欄は地図添付のチェックのため自動化しない）。"
    )


def main():
    st.title("🏠 AI重説調査 〜 Excel自動入力システム")
    st.caption(
        "住所と登記簿PDFから重要事項説明書のドラフトを生成する調査支援ツール。"
        "無料公開データのみ使用。最終確認は宅地建物取引士が行ってください。"
    )

    with st.sidebar:
        st.header("① 取引種別")
        deal = st.radio(
            "取引の種類",
            options=["売買", "賃貸"],
            horizontal=True,
            help="賃貸のときは特約条項とクロスチェック（どちらも売買用）を出しません。",
        )
        is_sale = deal == "売買"

        st.divider()
        st.header("② 作る書類を選ぶ")
        # 並びは **セットが先、個別追加は後**（2026-08-21 オーナー指示）。
        # 普段はセットで足りるので、それを最初に置き、追加したい人だけ下を開く。
        catalog_error = format_catalog.status_message()
        entries_selected = []
        if catalog_error:
            st.error(catalog_error)
        else:
            picked = st.session_state.setdefault("picked_formats", [])

            # ── 基本セット ────────────────────────────────────────────
            kind = st.selectbox("物件の種別",
                                options=format_catalog.PROPERTY_KINDS)
            # 売買契約書・重説は**売主の立場で条項が違う**（一般売主／宅建業者売主／
            # 消費者契約用）。媒介がほとんどなので既定は一般売主。賃貸には無関係。
            seller = "一般売主"
            if is_sale:
                seller = st.selectbox(
                    "売主の立場", options=format_catalog.SELLER_KINDS,
                    help="自社が売主のとき（買取再販など）は「宅建業者売主」を選びます。")
            preset_entries = format_catalog.preset(deal, kind, seller)
            if preset_entries:
                st.caption("基本セット：{}".format(
                    " ／ ".join(format_catalog.short_name(e) for e in preset_entries)))
                if st.button("＋ 基本セット（{}点）を入れる".format(len(preset_entries)),
                             type="primary", use_container_width=True):
                    for e in preset_entries:
                        if e["path"] not in picked:
                            picked.append(e["path"])
                    st.rerun()

            # ── 作る書類の一覧（セット＋追加ぶん）──────────────────────
            all_by_path = format_catalog.by_path()
            entries_selected = [all_by_path[p] for p in picked if p in all_by_path]
            # 取引種別を切り替えたとき、前の種別で選んだ書式が残らないようにする
            # （残ると賃貸の案件に売買の書式が混ざる）
            mismatch = [e for e in entries_selected
                        if format_catalog.deal_of(e) not in (deal, "共通")]
            if mismatch:
                for e in mismatch:
                    picked.remove(e["path"])
                entries_selected = [e for e in entries_selected if e not in mismatch]
                st.warning("取引種別が「{}」に変わったので、{} 本を選択から外しました：{}".format(
                    deal, len(mismatch),
                    "／".join(format_catalog.short_name(e) for e in mismatch)))
            if entries_selected:
                st.markdown("**作る書類 {} 本**".format(len(entries_selected)))
                for e in entries_selected:
                    c1, c2 = st.columns([6, 1])
                    c1.markdown("・{}".format(format_catalog.short_name(e)))
                    if c2.button("×", key="rm_{}".format(e["path"])):
                        picked.remove(e["path"])
                        st.rerun()
                if st.button("すべて外す", use_container_width=True):
                    picked.clear()
                    st.rerun()
            else:
                st.caption("※ まだ何も選んでいません。上のセットを入れるか、"
                           "下の「追加の書類」から1本ずつ足してください。")

            # ── 追加の書類（任意）─────────────────────────────────────
            with st.expander("➕ 追加の書類を選ぶ（覚書・解除証書・媒介契約書など）"):
                # ★①で選んだ取引種別で絞る。賃貸なのに売買の書類が並ぶと、
                #   間違った書式で作ってしまう。種別に関係ない書類は両方に出る。
                category = st.selectbox(
                    "書類の分類", options=format_catalog.categories(deal),
                    help="「{}」の書類だけを出しています。".format(deal))
                # 分類の下にもう1段ある（例: 売買契約書 → 一般売主 / 覚書・合意書 /
                # 解除証書）。出さないと契約書を選びたいのに覚書まで同じ一覧に並ぶ。
                subs = format_catalog.subcategories(category, deal)
                sub = None
                if subs:
                    choice = st.selectbox(
                        "小分類", options=subs + ["（すべて）"],
                        help="この分類のフォルダ構成です。既定は本体の書式だけを出します。")
                    sub = None if choice == "（すべて）" else choice
                entries = format_catalog.formats_in(category, deal, sub)
                # **ここは1つだけ選ぶ**。同じ小分類の中は「区分所有か土地建物か」の
                # ような排他の選択肢で、1つの物件に両方を使うことはない。
                add = st.selectbox(
                    "書式（全宅連 公式）",
                    options=entries,
                    format_func=format_catalog.label,
                    key="add_format_{}_{}".format(category, sub or "all"),
                )
                if add is not None and st.button(
                        "＋ この書式を追加", use_container_width=True):
                    if add["path"] not in picked:
                        picked.append(add["path"])
                    st.rerun()
                st.caption("{} の書類のみ：{} 分類 / いまの絞り込みで {} 本".format(
                    deal, len(format_catalog.categories(deal)), len(entries)))

        st.divider()
        st.header("③ 物件情報を入力")
        # 住所の出どころは **マイソク → 謄本 → 手入力** の順。
        # マイソクには住居表示で書かれていることが多いので最優先にする。
        # ただし地番表記のこともあるため、必ず編集できる欄に出して📮で確認させる。
        maisoku_pdf = st.file_uploader(
            "マイソク・物件概要書（PDF・任意）", type=["pdf"],
            help="住所・建物名・最寄駅を読み取って下の欄に入れます。"
                 "マイソクの住所は地番表記のこともあるので、必ず確認してください。")
        if maisoku_pdf is not None and maisoku_service.available():
            if st.button("📄 マイソクを読む（住所を取り込む）", use_container_width=True):
                with st.spinner("マイソクを解析中…（30〜60秒）"):
                    st.session_state["maisoku_data"] = \
                        maisoku_service.parse_maisoku(maisoku_pdf)
                st.session_state.pop("addr_town_v", None)
                st.session_state.pop("addr_rest_v", None)
                st.rerun()
        elif maisoku_pdf is not None:
            st.caption("※ claude CLI か共有モジュールが見つからないため解析できません。")

        # 謄本。ここを読むと登記の所在・地番が入る
        land_pdf = st.file_uploader("登記事項証明書（土地PDF）", type=["pdf"])
        building_pdf = st.file_uploader("登記事項証明書（建物PDF）", type=["pdf"])

        render_extra_documents()
        if land_pdf is not None or building_pdf is not None:
            # 解析は claude CLI を通すので数十秒かかる。**押されたときだけ**走らせ、
            # 結果を session_state に置いて、以後の再実行で読み直さない
            if st.button("📄 謄本を読む（住所を取り込む）", use_container_width=True):
                with st.spinner("登記簿PDFを解析中…（30〜60秒）"):
                    st.session_state["registry_data"] = \
                        registry_service.parse_registry(land_pdf, building_pdf)
                # 取り込んだ住所を欄に反映させるため、前の入力値を捨てる
                st.session_state.pop("addr_town_v", None)
                st.session_state.pop("addr_rest_v", None)
                st.rerun()
        # ★住所は「住居表示」として使う。**謄本には住居表示が載っていない**ので、
        #   ここが唯一の出どころ（2026-08-21 オーナー指摘）。書式の「（住居表示）」欄へ入る。
        #   謄本から取れる「所在（地番区域）」は別項目（登記所在）として「（登記簿）」欄へ入る。
        # 入力欄を2つに割る理由（2026-08-21 オーナー指示）:
        #   日本郵便のデータは**町名まで**しか無く、丁目すら持たない
        #   （実測: 534-0027 は「中野町」。「中野町一丁目」は 404）。
        #   だから「機械で確かめられる部分」と「人が入れるしかない部分」を分けて、
        #   前者は 📮 で確定させ、後者は人に入力させる。
        # ★入力の順番（2026-08-21 オーナー指示）: 先に謄本を読ませ、**分かる部分は自動で出し、
        #   足りない部分だけ人に入力させる**。謄本の「所在」には町名と丁目まで入っているので、
        #   人が足すのは実質「街区符号・住居番号」だけになる。
        reg = st.session_state.get("registry_data") or {}
        mai = st.session_state.get("maisoku_data") or {}
        # マイソクの住所があればそれを優先（住居表示で書かれていることが多い）。
        # 無ければ謄本の所在（＝地番区域。町名と丁目までは同じ）を使う。
        src_addr = mai.get("所在地") or reg.get("登記所在", "")
        reg_town, reg_chome = address_verify_service.split_for_input(src_addr)
        addr_town = st.text_input(
            "住所（町名まで・必須）",
            value=st.session_state.get("addr_town_v") or reg_town,
            key="addr_town_v",
            placeholder="例：大阪市都島区中野町",
            help="この欄は日本郵便の公式データで実在を確認します。"
                 "謄本を読み込むと自動で入ります。丁目・番・号は下の欄へ。")
        _v = address_verify_service.verify(addr_town) if addr_town else None
        if _v:
            if _v["status"] in ("一致", "町域まで一致"):
                st.success("📮 {}".format(_v["message"]))
            elif _v["status"] == "見つからない":
                st.error("📮 {}".format(_v["message"]))
            else:
                st.caption("📮 {}".format(_v["message"]))

        # 町名の欄に番地まで打たれていたら、その分をこちらの初期値にして拾い直す。
        # 謄本が読めていれば、その丁目を初期値に置く（人が足すのは街区・住居番号だけ）。
        _pref_rest = ((_v or {}).get("banchi", "") if _v else "") or reg_chome
        addr_rest = st.text_input(
            "丁目・番・号（必須）",
            value=st.session_state.get("addr_rest_v") or _pref_rest,
            key="addr_rest_v",
            placeholder="例：一丁目4番18号 ／ 1-4-18",
            help="日本郵便のデータには丁目以降が無いため、ここは機械では確認できません"
                 "（現地表示・住民票などでご確認ください）。謄本の地番とは別物です。")
        if mai:
            st.caption("マイソクから: 所在地 **{}**{}{}".format(
                mai.get("所在地") or "（取れず）",
                "／" + mai.get("建物名") if mai.get("建物名") else "",
                "　※表記は「{}」と読めました".format(mai["表記種別"])
                if mai.get("表記種別") else ""))
        if reg:
            st.caption("謄本から: 所在 **{}** ／ 地番 **{}**　※地番は住居表示とは別物です".format(
                reg.get("登記所在") or "（取れず）", reg.get("地番") or "（取れず）"))

        # 書式の「（住居表示）」欄へ入るのはこの合成結果。
        # 町名は公式表記が取れていればそれを使う（表記ゆれをここで吸収する）。
        address = address_verify_service.compose(
            (_v or {}).get("official") or addr_town, addr_rest)
        if address:
            st.caption("住居表示: **{}**".format(address))


        st.divider()
        st.header("④ 特約条項（売買・任意）")
        tok_items, tok_style, tok_extra = [], "である調（契約書標準）", ""
        if not is_sale:
            st.caption("※ 賃貸では使いません（特約カタログは売買契約用）。")
        elif tokuyaku_core is None:
            st.caption("※ 共有モジュール tokuyaku_core が読めません。")
        else:
            # CATEGORIES の要素は {no, name, items}。item 側に category を持たせるのは
            # all_items() なので、生成に渡す item は all_items() から取る
            # （generate_clause が item["category"] を使うため）。
            items_all = tokuyaku_core.all_items()
            cats = [c["name"] for c in tokuyaku_core.CATEGORIES]
            tok_cat = st.selectbox("特約のカテゴリ", options=cats, key="tok_cat")
            pool = [it for it in items_all if it.get("category") == tok_cat]
            tok_items = st.multiselect(
                "入れる特約（複数可）",
                options=pool,
                format_func=lambda it: it["title"],
                key="tok_items",
            )
            tok_style = st.selectbox("文体", options=list(tokuyaku_core.STYLE_GUIDE.keys()))
            tok_extra = st.text_area("追加の事情（任意）", height=68, key="tok_extra")
            st.caption("{} カテゴリ / このカテゴリに {} 項目".format(len(cats), len(pool)))

        st.divider()
        st.header("⑤ クロスチェック（売買・任意）")
        exp_pdf = con_pdf = None
        seller_pro = False
        if not is_sale:
            st.caption("※ 賃貸では使いません（検閲ルールは売買契約・売買重説用）。")
        else:
            st.caption(
                "出来上がった重説・契約書を入れると、調査結果・謄本と突き合わせて"
                "齟齬と法令リスクを検出します。片方だけでも実行できます。"
            )
            exp_pdf = st.file_uploader("重要事項説明書 PDF", type=["pdf"], key="cc_exp")
            con_pdf = st.file_uploader("売買契約書 PDF", type=["pdf"], key="cc_con")
            seller_pro = st.checkbox(
                "売主が宅建業者（業法40条・38条の制限を適用）", value=False
            )

        web_law = st.checkbox(
            "Web調査で法令制限を補完する（防火地域・高度地区・日影規制）",
            value=False,
            help="不動産情報ライブラリにこれらのレイヤが無いため、自治体の都市計画情報を "
                 "claude CLI の WebSearch で調べます。最大5分かかります。",
        )

        run = st.button("調査を実行", type="primary", use_container_width=True)

        st.divider()
        render_company_editor()

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

    data, facilities, hazard_url, coords, coords_source, hazard_detail, landprice = run_pipeline(
        address, land_pdf, building_pdf, web_law=web_law
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

    render_section("📐 区域指定（法令制限の下調べ）", formatter.section_areas(data))
    st.caption(
        "**自動でチェックが入るのは 急傾斜地法・地すべり等防止法・自然公園法 の3つだけ**"
        "（区域内＝その法律の制限、と言い切れるもの）。"
        "地区計画・都市計画道路・立地適正化計画は**表示のみ**で、書式のチェックは宅建士が押します"
        "（立地適正化は区域内であること自体は制限を意味しないため）。"
    )
    st.divider()

    render_section("🌊 災害情報", formatter.section_hazard(data))
    render_hazard_notes(hazard_detail)
    st.markdown("[🔗 重ねるハザードマップで該当地点を確認]({})".format(hazard_url))
    st.divider()

    render_extra_document_results()
    render_landprice(landprice)
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

    if is_sale:
        render_tokuyaku(data, tok_items, tok_style, tok_extra)
        render_crosscheck(data, exp_pdf, con_pdf, seller_pro, address)
    else:
        st.caption("※ 賃貸のため、特約条項とクロスチェック（売買用）は表示していません。")
        st.divider()

    # ===== 公式書式への流し込み =====
    # ===== マイソクの記載の照合 =====
    # マイソクは他社が作った広告資料で、誤り・古い情報・省略が混ざる。
    # **読み取った値をそのまま重説へ流すと、他社の誤りを転記してしまう**ので、
    # こちらで確かめられるものは突き合わせてから使う（2026-08-21 オーナー指示）。
    # 謄本は**内容そのものは確定**として扱う（2026-08-21 オーナー判断）。
    # 見るのは鮮度だけ。発行日が古いと、その後に売買・抵当権設定・分筆があり得る。
    _reg = st.session_state.get("registry_data") or {}
    if _reg:
        age = maisoku_check_service.registry_age(_reg)
        line = "📜 謄本の発行日: **{}**　{}".format(
            age["発行日"] or "（読み取れず）", age["説明"])
        if age["結果"] == maisoku_check_service.DIFF:
            st.warning(line)
        elif age["結果"] == maisoku_check_service.OK:
            st.success(line)
        else:
            st.info(line)
        st.caption("謄本の記載内容は確定として扱います。マイソクと食い違ったときに疑うのは"
                   "マイソクのほうです。")

    _mai = st.session_state.get("maisoku_data") or {}
    if _mai:
        rows = maisoku_check_service.check(_mai, _reg, data)
        if rows:
            st.subheader("🔎 マイソクの記載を照合しました")
            st.caption(maisoku_check_service.summary(rows)
                       + "　※マイソクは他社の資料です。🟡 は必ず人が確かめてください。")
            st.dataframe(
                [{"": r["結果"], "項目": r["項目"], "マイソクの記載": r["マイソク"],
                  "照合した相手": r["照合先"], "説明": r["説明"]} for r in rows],
                use_container_width=True, hide_index=True)
            if any(r["結果"] == maisoku_check_service.DIFF for r in rows):
                st.warning("🟡 の項目はマイソクと突き合わせた結果が食い違っています。"
                           "**そのまま書類に載せないでください。**")
        st.divider()

    st.subheader("📥 公式書式へ流し込んで書類を作る")
    if not entries_selected:
        st.error(format_catalog.status_message() or
                 "書式が選ばれていません（サイドバー②で選び、「＋ 選択に追加」を押してください）。")
    else:
        st.caption(
            "賃料・売買代金・手付金・引渡日などの取引条件は自動では入りません（どのデータにも無いため）。"
            "選択欄やチェック欄も書式の既定のまま残します。最終確認は宅地建物取引士が行ってください。"
        )
        made = []
        for e in entries_selected:
            with st.container(border=True):
                st.markdown("**{}**".format(format_catalog.short_name(e)))
                got = format_catalog.filled_fields(e, data)
                st.caption("自動で入るのは {} 項目：{}".format(
                    len(got), "・".join(got) or "（該当なし。白紙のまま出します）"))
                docs = format_catalog.document_sheets(e)
                if e.get("fanout_count") and len(docs) > 1:
                    st.info(
                        "この書式は **重要事項説明書に入力すると他の書類へ自動転記される**作りです。"
                        "1ファイルで {} 書類が同時に仕上がります：{}".format(
                            len(docs), " / ".join(docs)))
                try:
                    out = format_catalog.generate(
                        e, data, os.path.join(REPORTS_DIR, "official"),
                        role=st.session_state.get("self_role", "媒介"))
                    made.append(out)
                    mime = (
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        if out.lower().endswith(".docx")
                        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    with open(out, "rb") as f:
                        st.download_button(
                            "⬇ ダウンロード", f.read(),
                            file_name=os.path.basename(out), mime=mime,
                            key="dl_{}".format(e["path"]),
                            use_container_width=True)
                except Exception as ex:
                    st.error("流し込みに失敗しました: {}".format(ex))

        # 2本以上あるときは ZIP でまとめて渡す（1本ずつ押させない）
        if len(made) > 1:
            import io
            import zipfile
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                for path in made:
                    z.write(path, os.path.basename(path))
            st.download_button(
                "📦 {} 本まとめてダウンロード（ZIP）".format(len(made)),
                buf.getvalue(), file_name="書類一式.zip", mime="application/zip",
                type="primary", use_container_width=True)
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
