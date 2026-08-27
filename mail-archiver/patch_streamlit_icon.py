#!/usr/bin/env python3
"""Streamlit の index.html <head> に apple-touch-icon を差し込む（冪等）。

なぜ要るか: iOS の「ホーム画面に追加」は <head> の apple-touch-icon しか見ない。
Streamlit は st.markdown で入れても body にしか入らず iOS が拾わない（"メ" の無地になる）。
そこで本体 index.html の head に1行足し、アイコンは静的配信（.streamlit config + static/）で出す。

site-packages の手編集は git で渡らず、Streamlit を上げると消える。だから run.sh から
毎回これを呼んで**自己修復**する。既に入っていれば何もしない。
"""
import os
import sys

LINKS = (
    '<link rel="apple-touch-icon" sizes="180x180" href="/app/static/apple-touch-icon.png" />'
    '<link rel="apple-touch-icon" href="/app/static/apple-touch-icon.png" />'
)


def main() -> int:
    try:
        import streamlit
    except Exception as e:  # noqa: BLE001
        print("streamlit が見つかりません: {}".format(e), file=sys.stderr)
        return 0  # 起動は止めない
    idx = os.path.join(os.path.dirname(streamlit.__file__), "static", "index.html")
    if not os.path.exists(idx):
        return 0
    try:
        html = open(idx, encoding="utf-8").read()
    except Exception:
        return 0
    if "apple-touch-icon" in html:
        return 0  # 既に入っている
    anchor = '<link rel="shortcut icon" href="./favicon.png" />'
    if anchor in html:
        html = html.replace(anchor, anchor + LINKS, 1)
    elif "</head>" in html:
        html = html.replace("</head>", LINKS + "</head>", 1)
    else:
        return 0
    try:
        open(idx, "w", encoding="utf-8").write(html)
        print("apple-touch-icon を index.html に挿入した")
    except PermissionError:
        print("index.html が書き込めません（権限）。アイコンは無地のままになります。", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
