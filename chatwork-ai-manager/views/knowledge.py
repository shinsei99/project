"""ナレッジ管理: 索引状況・最終更新・増分リフレッシュ・文書一覧・無効化。"""
import streamlit as st

from services import config
from services import knowledge as K


def render():
    st.header("📚 ナレッジ管理")
    stats = K.stats()
    c1, c2, c3 = st.columns(3)
    c1.metric("有効文書", stats["documents"])
    c2.metric("チャンク", stats["chunks"])
    c3.metric("最終取込", K.last_refresh())

    src = config.get("knowledge_source_dir")
    st.caption(f"取込元: {src or '（未設定・secrets.tomlのknowledge_source_dir）'}")

    st.info("⚠️ Dropbox等CloudStorageの取込は、TCC権限のため /bin/bash にフルディスクアクセスが必要です"
            "（未付与ならターミナルから `python3 ingest_knowledge.py`）。取込後の検索はローカルDBのみで動きます。")

    col = st.columns(2)
    if col[0].button("🔄 増分リフレッシュ（更新分のみ取込）"):
        if not src:
            st.error("取込元が未設定です。")
        else:
            with st.spinner("取込中…（変更ファイルのみ）"):
                try:
                    res = K.ingest_folder(src, incremental=True)
                    st.success(f"取込 {res['ingested']} / 変更なし {res['unchanged']} / "
                               f"スキップ {res['skipped']} / 失敗 {res['failed']} / 無効化 {res['pruned']}")
                except OSError as e:
                    st.error(f"フォルダを読めません（FDA権限が必要）: {e}")
                except Exception as e:
                    st.error(f"取込失敗: {e}")

    st.divider()
    st.subheader("登録文書（有効版のみ）")
    docs = K.list_documents(active_only=True)
    if not docs:
        st.info("まだ文書がありません。")
        return
    # カテゴリ別に件数
    from collections import Counter
    cats = Counter(d["category"] for d in docs)
    st.caption("カテゴリ別: " + " / ".join(f"{c}:{n}" for c, n in cats.most_common()))

    q = st.text_input("文書名でフィルタ")
    shown = [d for d in docs if not q or (q in (d["title"] or ""))][:300]
    for d in shown:
        c = st.columns([5, 2, 1, 1])
        c[0].write(f"**{d['title']}**")
        c[1].caption(f"{d['category']} / v{d['version']} / {d['chunk_count']}ch")
        c[2].caption(str(d["mime"] or ""))
        if c[3].button("無効化", key=f"deact{d['id']}"):
            K.deactivate(d["id"])
            st.rerun()
    if len(docs) > len(shown):
        st.caption(f"…他 {len(docs) - len(shown)} 件（フィルタで絞り込み）")
