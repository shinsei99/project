# -*- coding: utf-8 -*-
"""特約条項に「似た争いの実例」を付ける共有モジュール（2026-08-30）。

**何のためか**
  特約は書いたら終わりではなく、**有効性が裁判で争われる**。
  「この論点は実際に裁判になっている」と書いた本人が気づけるようにする。

**どこで使われるか**
  リポジトリ直下に置いてあるので、次の2つから同じものが使える。
    - tokuyaku-generator/app.py … 特約条項ジェネレーター（8513）
    - jyuusetsu-research/app.py … AI重説アシスタント（8536。tokuyaku_core を読んでいる）
  ＝**1回の実装で2つのアプリに効く。**

**中身の出どころ**
  RETIO（不動産適正取引推進機構）機関誌の「本号所収裁判例索引」22本から
  296件を抜き出したもの（裁判所 / 判決日 / 要旨 / 出典 / 掲載ページ）。
  生成は bookshelf/make_case_table.py。**手で編集しない**（生成し直す）。

**★これは法的助言ではない。**
  出るのは「似た論点で争いになった実例がある」という事実だけで、
  その特約が有効か無効かを判定するものではない。文言もそう書いてある。
"""
from __future__ import annotations

import json
import os
import pathlib
import re

_PATH = pathlib.Path(os.environ.get("TOKUYAKU_CASES_JSON") or
                     (pathlib.Path(__file__).resolve().parent / "tokuyaku_cases.json"))

_DATA: dict = {}
_TOPICS: dict[str, "re.Pattern"] = {}
LOAD_ERROR: str = ""

try:
    _DATA = json.loads(_PATH.read_text(encoding="utf-8"))
    _TOPICS = {k: re.compile(v) for k, v in _DATA.get("topics", {}).items()}
except FileNotFoundError:
    LOAD_ERROR = f"判例表が無い: {_PATH}"
except (OSError, ValueError) as e:
    # ★黙って「判例0件」に落ちない。読めなかったことを画面に出せるようにする
    LOAD_ERROR = f"判例表を読めなかった: {e}"


def available() -> bool:
    return bool(_DATA.get("cases"))


def meta() -> dict:
    return _DATA.get("_meta", {})


def topic_names() -> list[str]:
    return list(_TOPICS.keys())


def topics_of(text: str) -> list[str]:
    """文章に論点タグを付ける。**判例側と特約側で同じ規則**を使う（ずれると噛み合わない）。"""
    return [name for name, pat in _TOPICS.items() if pat.search(text or "")]


def topics_of_item(item: dict) -> list[str]:
    """特約カタログの1項目から論点タグを出す。

    title と hint を先に見る。hint は「原状回復 経過年数 負担割合」のような検索語なので
    論点判定に向く。**body（条文本文）は最後の手段**（長いので関係の薄い語まで拾う）。
    """
    head = f"{item.get('title', '')} {item.get('hint', '')}"
    found = topics_of(head)
    return found or topics_of(item.get("body", ""))


def for_topics(topics, limit: int = 4) -> list[dict]:
    """論点タグに当たる判例を、当たった論点が多い順・新しい順で返す。"""
    want = set(topics or [])
    if not want:
        return []
    scored = []
    for c in _DATA.get("cases", []):
        n = len(want & set(c.get("topics", [])))
        if n:
            scored.append((n, c.get("retio", ""), c))
    scored.sort(key=lambda x: (-x[0], x[1]), reverse=False)
    scored.sort(key=lambda x: (-x[0], -_issue_no(x[1])))
    return [c for _n, _r, c in scored[:limit]]


def for_item(item: dict, limit: int = 4) -> list[dict]:
    """特約カタログの1項目に対する判例。"""
    return for_topics(topics_of_item(item), limit=limit)


def for_text(text: str, limit: int = 4) -> list[dict]:
    """出来上がった特約の本文から引く（カタログ外の自由記述にも使える）。"""
    return for_topics(topics_of(text), limit=limit)


def cite(case: dict) -> str:
    """『RETIO129 東京地判 令3.12.23（ウエストロー・ジャパン p136）』の形。"""
    head = " ".join(x for x in (case.get("retio"), case.get("court"), case.get("date")) if x)
    src = case.get("source") or ""
    page = case.get("page") or ""
    tail = f"（{src} p{page}）" if src and page else (f"（{src}）" if src else "")
    return head + tail


def _issue_no(retio: str) -> int:
    m = re.search(r"(\d+)", retio or "")
    return int(m.group(1)) if m else 0


# ── 画面表示（Streamlit）───────────────────────────────────────────────────
# ★`st` を引数で受け取る。このモジュール自体は streamlit を import しない
#   （データとして他の場所からも読めるようにしておくため）。
#   2つのアプリで**同じ関数**を使う＝見え方がずれない・直すときも1か所。

def render_streamlit(st, pairs, *, title: str = "④ 似た争いの実例（判例）") -> None:
    """pairs は [(見出し, [論点…], [判例…]), …]。判例が1件も無ければ何も出さない。

    ★当たった**論点を必ず一緒に出す**。語での照合なので、
      「設備の経年劣化免責」の"設備"が「設備・修繕」に当たって大規模修繕の判例を拾う、
      といった緩い当たり方をする。どの語で当たったかが見えれば、人が的外れだと判断できる。
      隠して「関係ある判例です」という顔で出すほうが危ない。
    """
    pairs = [(lab, tp, cs) for lab, tp, cs in pairs if cs]
    st.divider()
    st.subheader(title)
    if LOAD_ERROR:
        st.warning(f"判例表を読めませんでした（{LOAD_ERROR}）。"
                   "`python3 bookshelf/make_case_table.py` で作り直せます。")
        return
    st.caption(
        f"RETIO（不動産適正取引推進機構）の「本号所収裁判例索引」から{meta().get('count', 0)}件。"
        "**その特約が有効か無効かを判定するものではありません。**"
        "「この論点は実際に争いになっている」という事実だけを出します。"
        "契約書に載せる前に、条文と事情を人が確かめてください。"
    )
    if not pairs:
        st.info("選んだ特約の論点に当たる裁判例は、手元の索引にはありませんでした。")
        return
    for label, topics, cases in pairs:
        st.markdown(f"**{label}**　`論点: {'／'.join(topics) or '—'}`")
        for c in cases:
            st.markdown(f"- {c['summary']}")
            st.caption(f"　{cite(c)}")
        st.write("")
