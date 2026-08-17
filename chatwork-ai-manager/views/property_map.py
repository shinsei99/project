"""🗺 物件マップ画面。

生成済みの地図HTMLを一覧・表示する。地図そのものは services/gis.py が作るので、
ここは「見るところ」だけ（画面用に別のGIS処理を書かない＝共通Toolを2系統にしない）。
"""
import os

import streamlit as st
import streamlit.components.v1 as components

from db.connection import query
from services import gis
from services.agent_tools import gis_tools


def _maps():
    if not os.path.isdir(gis.MAPS_DIR):
        return []
    files = [f for f in os.listdir(gis.MAPS_DIR) if f.endswith(".html")]
    return sorted(files, key=lambda f: os.path.getmtime(os.path.join(gis.MAPS_DIR, f)),
                  reverse=True)


def render():
    st.title("🗺 物件マップ")
    st.caption("管理物件台帳（Excel）から取り込んだ物件を地図で見る。"
               "座標は国土地理院の住所検索APIで取得しDBに保存済み（毎回の外部問い合わせなし）。")

    total = query("SELECT COUNT(*) c FROM properties WHERE active=1")[0]["c"]
    geo = query("SELECT COUNT(*) c FROM properties WHERE active=1 AND lat IS NOT NULL")[0]["c"]
    c = st.columns(3)
    c[0].metric("登録物件", f"{total}件")
    c[1].metric("座標あり", f"{geo}件")
    c[2].metric("地図ファイル", f"{len(_maps())}枚")
    if total == 0:
        st.warning("物件マスタが空です。ターミナルから `python3 ingest_properties.py` を実行してください"
                   "（Dropboxの台帳を読むため、launchd常時起動からは読めません）。")
        return

    tab1, tab2, tab3 = st.tabs(["地図を見る", "地図を作る", "物件一覧"])

    with tab1:
        files = _maps()
        if not files:
            st.info("まだ地図がありません。「地図を作る」で作成してください。")
        else:
            pick = st.selectbox("地図", files, key="map_pick")
            path = os.path.join(gis.MAPS_DIR, pick)
            with open(path, encoding="utf-8") as f:
                components.html(f.read(), height=620, scrolling=False)
            st.caption(f"ファイル: `{path}`")
            with open(path, "rb") as f:
                st.download_button("この地図をダウンロード", f, file_name=pick, mime="text/html")

    with tab2:
        st.caption("条件を選んで地図を作ります。LINE/Chatworkから「○○を地図にして」と頼んでも同じものができます。")
        cls = ["(すべて)"] + [r["classification"] for r in query(
            "SELECT DISTINCT classification FROM properties WHERE active=1 "
            "AND classification IS NOT NULL ORDER BY classification")]
        cat = ["(すべて)"] + [r["category"] for r in query(
            "SELECT DISTINCT category FROM properties WHERE active=1 "
            "AND category IS NOT NULL ORDER BY category")]
        col = st.columns(3)
        v_cls = col[0].selectbox("分類", cls, key="m_cls")
        v_cat = col[1].selectbox("種別", cat, key="m_cat")
        v_area = col[2].text_input("エリア（住所の一部）", key="m_area", placeholder="例: 都島区")
        st.divider()
        st.caption("特定の物件を中心に半径で見る場合はこちら（上の条件は絞り込みとして併用されます）")
        col2 = st.columns([3, 2])
        names = [""] + [r["name"] for r in query(
            "SELECT name FROM properties WHERE active=1 AND lat IS NOT NULL ORDER BY name")]
        v_center = col2[0].selectbox("中心にする物件", names, key="m_center")
        v_radius = col2[1].number_input("半径(m)", min_value=100, max_value=20000,
                                        value=1000, step=100, key="m_radius")
        if st.button("地図を作る", type="primary"):
            res = gis_tools.gis_create_map(
                classification=None if v_cls.startswith("(") else v_cls,
                category=None if v_cat.startswith("(") else v_cat,
                area=v_area.strip() or None,
                center_property=v_center or None,
                radius_m=v_radius if v_center else None,
            )
            if res.get("ok"):
                st.success(f"{res['count']}件で作成しました: {res['filename']}")
                st.rerun()
            else:
                st.error(res.get("error"))

    with tab3:
        rows = query("SELECT name, category, classification, address, units, access, "
                     "lat, lon, geo_status FROM properties WHERE active=1 "
                     "ORDER BY classification, category, name")
        st.dataframe([dict(r) for r in rows], use_container_width=True, height=520)
        miss = [r for r in rows if r["lat"] is None]
        if miss:
            st.warning(f"座標なし {len(miss)}件。ほとんどは**台帳の住所欄が空**です"
                       "（台帳に住所を入れて `python3 ingest_properties.py` を再実行すると地図に載ります）。")
