"""日報検索・集計（TASK-20260825-009）。

蓄積された `daily_reports` を「社内の業務管理データベース」として活用するための画面。
日付・氏名・キーワードで横断検索し、発言数・TODO件数などの統計を一覧とグラフで見る。
日報の作成・編集・Chatworkへの送信は「📝 業務日報」画面の役割のまま、ここは**閲覧・集計専用**。
"""
import datetime

import pandas as pd
import streamlit as st

from services import daily_report as DR
from services import daily_report_export as EX


def _local(ts: str) -> str:
    """DBは日本時間で入っているので、形を整えるだけ。

    ★2026-08-31 以前は datetime('now')＝UTC で記録していたため、ここで+9時間して
      いた。DB側を日本時間に直した（既存データも変換済み）ので、足すと二重になる。
    """
    try:
        dt = datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%m/%d %H:%M")
    except (TypeError, ValueError):
        return ts or "-"


def _row_stats(row: dict) -> dict:
    s = EX.stats_of(row)
    return {
        "発言数": s.get("messages_own", 0),
        "動いたTODO": s.get("tasks_moved", 0),
        "完了TODO": s.get("tasks_done_today", 0),
        "未完了TODO": s.get("tasks_open", 0),
    }


def render():
    st.title("📊 日報検索・集計")
    st.caption("蓄積された業務日報（📝 業務日報で作成したもの）を、日付・氏名・キーワードで横断検索し、"
               "発言数やTODO件数の統計を確認できます。作成・Chatworkへの送信は「📝 業務日報」で行います。")

    lo, hi = DR.date_range()
    if not lo:
        st.info("まだ日報がありません。「📝 業務日報」で作成すると、ここに集計が出るようになります。")
        return

    persons_all = DR.all_persons()
    lo_d = datetime.date.fromisoformat(lo)
    hi_d = datetime.date.fromisoformat(hi)
    default_from = max(lo_d, hi_d - datetime.timedelta(days=29))

    c1, c2, c3, c4 = st.columns([2, 2, 2, 3])
    date_from = c1.date_input("開始日", value=default_from, min_value=lo_d, max_value=hi_d)
    date_to = c2.date_input("終了日", value=hi_d, min_value=lo_d, max_value=hi_d)
    targets = c3.multiselect("氏名（未選択=全員）", persons_all)
    keyword = c4.text_input("キーワード（本文・要約から検索）", placeholder="例: 鍵、退去、グレイス…")

    if date_from > date_to:
        st.error("開始日が終了日より後になっています。")
        return

    rows = DR.search(date_from.isoformat(), date_to.isoformat(),
                      persons=targets or None, keyword=keyword.strip() or None)

    if not rows:
        st.warning("条件に合う日報がありません。")
        return

    df = pd.DataFrame([
        {"日付": r["report_date"], "氏名": r["person"], "要約": r["summary"] or "",
         **_row_stats(r), "更新": _local(r["updated_at"])}
        for r in rows
    ])

    st.divider()
    st.subheader("集計サマリー")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("日報件数", f"{len(df)}件")
    m2.metric("対象人数", f"{df['氏名'].nunique()}人")
    m3.metric("発言数 合計", f"{int(df['発言数'].sum())}件")
    m4.metric("完了TODO 合計", f"{int(df['完了TODO'].sum())}件")
    m5.metric("未完了TODO 合計（延べ）", f"{int(df['未完了TODO'].sum())}件")

    all_dates = [d.strftime("%Y-%m-%d")
                 for d in pd.date_range(date_from, date_to, freq="D")]

    def _daily_series(value_col: str) -> pd.Series:
        """氏名 → 日別の値のリスト（LineChartColumn用のスパークライン）。"""
        piv = df.pivot_table(index="氏名", columns="日付", values=value_col,
                              aggfunc="sum", fill_value=0)
        piv = piv.reindex(columns=all_dates, fill_value=0)
        return piv.apply(lambda row: row.tolist(), axis=1)

    st.divider()
    st.subheader("氏名別の集計")
    by_person = df.groupby("氏名")[["発言数", "動いたTODO", "完了TODO", "未完了TODO"]].sum()
    by_person.insert(0, "日報件数", df.groupby("氏名").size())
    by_person["発言数の推移"] = _daily_series("発言数")
    by_person["完了TODOの推移"] = _daily_series("完了TODO")
    by_person = by_person.sort_values("発言数", ascending=False)
    st.dataframe(
        by_person, use_container_width=True,
        column_config={
            "発言数": st.column_config.ProgressColumn(
                "発言数（合計）", format="%d件", min_value=0,
                max_value=max(1, int(by_person["発言数"].max()))),
            "完了TODO": st.column_config.ProgressColumn(
                "完了TODO（合計）", format="%d件", min_value=0,
                max_value=max(1, int(by_person["完了TODO"].max()))),
            "発言数の推移": st.column_config.LineChartColumn(
                "発言数の推移", y_min=0, help=f"{date_from}〜{date_to} の発言数を日ごとに表示"),
            "完了TODOの推移": st.column_config.LineChartColumn(
                "完了TODOの推移", y_min=0, help=f"{date_from}〜{date_to} の完了TODO数を日ごとに表示"),
        })

    st.divider()
    st.subheader("日別の推移")
    by_date = df.groupby("日付")[["発言数", "動いたTODO", "完了TODO"]].sum().sort_index(ascending=False)
    st.dataframe(
        by_date, use_container_width=True,
        column_config={
            "発言数": st.column_config.ProgressColumn(
                format="%d件", min_value=0, max_value=max(1, int(by_date["発言数"].max()))),
            "動いたTODO": st.column_config.ProgressColumn(
                format="%d件", min_value=0, max_value=max(1, int(by_date["動いたTODO"].max()))),
            "完了TODO": st.column_config.ProgressColumn(
                format="%d件", min_value=0, max_value=max(1, int(by_date["完了TODO"].max()))),
        })

    st.divider()
    st.subheader(f"一覧（{len(df)}件・新しい順）")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.caption("行を選ぶと本文を確認できます。")
    options = [f"{r['report_date']}｜{r['person']}｜{r['summary'] or '(要約なし)'}" for r in rows]
    picked = st.selectbox("本文を見る", options, index=None, placeholder="選択してください")
    if picked is not None:
        r = rows[options.index(picked)]
        with st.container(border=True):
            st.caption(f"{EX.date_label(r['report_date'])} ／ {r['person']} ／ {EX.stats_label(r)} "
                       f"／ 生成: {_local(r['updated_at'])}（{r['model']}）")
            st.markdown(r["body"])
