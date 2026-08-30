# -*- coding: utf-8 -*-
"""重要事項説明書の「記載漏れ」を点検する共有モジュール（2026-08-30）。

**何をするか**
  出来上がった重説のテキストを受け取り、**宅建業法35条1項の各号が書かれているか**を見る。
  中身が正しいかは判定しない。**「そもそも項目が抜けていないか」だけ**を機械で確かめる。
  重説は書き漏らしがそのまま説明義務違反になるので、ここが一番効く。

**出どころ（役割を分けてある）**
  - 条文（何を書くべきか）… **e-Gov法令API**。施行日つきで記録している
  - 解釈運用のどこか      … 知識索引（国交省「宅建業法の解釈・運用の考え方」）
  - 検出の手がかり        … **当社が決めた語**。条文ではない。
                            索引にある実物の重説7本で当たることを確認済み

**★これは法的助言ではない。**
  「その号に当たる語が見つからない」と言うだけで、説明義務違反だと断定するものではない。
  賃貸なら出てこない号もある（私道・ローンのあっせん・契約不適合など）。
  **人が最後に見ること。**

  生成は bookshelf/make_jyuusetsu_checklist.py。**手で編集しない。**
"""
from __future__ import annotations

import json
import os
import pathlib
import re

_PATH = pathlib.Path(os.environ.get("JYUUSETSU_CHECKLIST_JSON") or
                     (pathlib.Path(__file__).resolve().parent / "jyuusetsu_checklist.json"))

_DATA: dict = {}
LOAD_ERROR: str = ""
try:
    _DATA = json.loads(_PATH.read_text(encoding="utf-8"))
except FileNotFoundError:
    LOAD_ERROR = f"点検表が無い: {_PATH}"
except (OSError, ValueError) as e:
    LOAD_ERROR = f"点検表を読めなかった: {e}"      # ★黙って「漏れ0件」に落ちない


def available() -> bool:
    return bool(_DATA.get("items"))


def meta() -> dict:
    return _DATA.get("_meta", {})


def _sp(s: str) -> str:
    """空白を全部消す。重説PDFは折り返しで語の途中に空白が入るため。"""
    return re.sub(r"[\s　]+", "", s or "")


def check(text: str) -> dict:
    """重説の本文を見て、号ごとに「記載あり／見つからない」を返す。"""
    body = _sp(text)
    items = []
    for it in _DATA.get("items", []):
        hit = [k for k in it.get("detect", []) if k in body]
        items.append({**it, "found": bool(hit), "matched": hit})
    subs = []
    for s in _DATA.get("sub_14", []):
        hit = [k for k in s.get("detect", []) if k in body]
        subs.append({**s, "found": bool(hit), "matched": hit})
    return {"items": items, "sub_14": subs,
            "missing": [i["no"] for i in items if not i["found"]],
            "missing_14": [s["name"] for s in subs if not s["found"]]}


# ── 画面表示（Streamlit）───────────────────────────────────────────────────
# `st` を引数で受け取る（このモジュール自体は streamlit に依存しない）。

def render_streamlit(st, result: dict, *, title: str = "📋 重説の記載漏れ点検（宅建業法35条1項）") -> None:
    st.divider()
    st.subheader(title)
    if LOAD_ERROR:
        st.warning(f"点検表を読めませんでした（{LOAD_ERROR}）。"
                   "`python3 bookshelf/make_jyuusetsu_checklist.py` で作り直せます。")
        return
    m = meta()
    st.caption(
        f"条文は **e-Gov法令API**（{m.get('article','')}{m.get('caption','')}・"
        f"施行日 {m.get('enforced','?')}）。根拠のページは国交省の解釈・運用の考え方。"
        "**書かれているかを語で探しているだけ**で、中身の当否や説明義務違反を判定するものではありません。"
        "賃貸では出てこない号もあります（私道・ローンのあっせん・契約不適合など）。"
    )
    ng = [i for i in result["items"] if not i["found"]]
    if ng:
        st.warning("**見つからなかった号: " + "・".join(f"第{i['no']}号" for i in ng) + "**")
    else:
        st.success("35条1項の15号すべてについて、それらしい記載が見つかりました。")

    for it in result["items"]:
        mark = "✅" if it["found"] else "⚠️"
        g = it.get("guidance") or {}
        page = f"　`解釈運用 {g['page']}`" if g.get("page") else ""
        with st.expander(f"{mark} 第{it['no']}号　{it['text'][:44]}…{page}",
                         expanded=not it["found"]):
            st.markdown(f"**条文**: {it['text']}")
            if it["found"]:
                st.caption("見つかった語: " + "・".join(it["matched"]))
            else:
                st.caption("探した語: " + "・".join(it.get("detect", [])) +
                           "　→ どれも見当たりませんでした")
            if g.get("quote"):
                st.caption(f"解釈運用（{g.get('page','')}）: {g['quote']}")
            st.caption(f"※ この号の検出語は、索引にある実物の重説 {it.get('sample_hits', 0)}/7本 で当たりました")

    st.markdown("**第十四号の内訳（施行規則16条の4の3 — 書き漏らしが一番起きるところ）**")
    for s in result["sub_14"]:
        st.markdown(("✅ " if s["found"] else "⚠️ ") + s["name"] +
                    ("　（" + "・".join(s["matched"]) + "）" if s["found"] else "　見当たりません"))
