# -*- coding: utf-8 -*-
"""新誠プロパティマネジメントの所有物件マスターの名寄せ（2026-09-02）。

**大京商事の `properties` とは別テーブル**（`shinsei_properties`）を読む。
理由は `ingest_shinsei_properties.py` の冒頭にある——`properties` を読む場所は
6ファイル14か所に散っており、会社の列で絞る方式は**1か所の絞り忘れで壁が破れる**。
別表なら失敗しても「見つからない」という目に見える形で止まる。

入口は `gis.find_property` / `gis.match_property_in_text` の2つだけ。
そこで `company_scope.here()` が新誠なら、このモジュールへ振り替える。
"""
from __future__ import annotations

import re
import unicodedata

from db.connection import query

COMPANY = "新誠プロパティマネジメント株式会社"


def _n(s) -> str:
    return unicodedata.normalize("NFKC", str(s or ""))


def all_properties() -> list[dict]:
    return [dict(r) for r in query(
        "SELECT * FROM shinsei_properties WHERE active=1 ORDER BY no")]


def names_of(row) -> list[str]:
    """照合に使う名前（正式名＋呼び名の揺れ）。長い順。"""
    names = [row.get("name") or ""]
    names += [a.strip() for a in (row.get("aliases") or "").split("\n") if a.strip()]
    return sorted({n for n in names if n}, key=len, reverse=True)


def _contains(text: str, needle: str) -> bool:
    """`needle` が `text` に含まれるか。**数字で終わる名前は続きが数字ならハズレ**とする。

    「秋津2」は 秋津戸建て２ の呼び名だが、**加東市秋津2014番658**（グリーンログTWINの
    地番）にも文字列としては含まれてしまう。地番が書かれた文の中で「秋津2」を拾うと
    別物件に付けてしまうので、直後が数字なら一致とみなさない（2026-09-02）。
    """
    if not needle:
        return False
    end_digit = needle[-1].isdigit()
    start = 0
    while True:
        i = text.find(needle, start)
        if i < 0:
            return False
        j = i + len(needle)
        if not (end_digit and j < len(text) and text[j].isdigit()):
            return True
        start = i + 1


def match_in_text(text: str):
    """自由文の中に物件名（正式名 or 呼び名）が出てくれば、その物件を返す。

    複数当たったら**一致した名前がいちばん長いもの**を採る
    （「秋津戸建て２」と「秋津2」が両方当たる状況で短い方に倒れないように）。
    """
    t = _n(text)
    if not t:
        return None
    best = None
    for r in all_properties():
        for nm in names_of(r):
            if _contains(t, _n(nm)):
                if best is None or len(nm) > best[0]:
                    best = (len(nm), r)
                break
    return best[1] if best else None


def find(name_or_keyword: str):
    """呼び名1つから物件を特定する。完全一致 → 部分一致 → 住所の順。"""
    k = _n((name_or_keyword or "").strip())
    if not k:
        return None
    rows = all_properties()
    for r in rows:
        if any(_n(nm) == k for nm in names_of(r)):
            return r
    part = [(len(nm), r) for r in rows for nm in names_of(r) if k in _n(nm)]
    if part:
        return sorted(part, key=lambda x: x[0])[0][1]
    for r in rows:
        if k in _n(r.get("address") or ""):
            return r
    return None


_VACANT_RE = re.compile(r"空室")


def summary(row) -> str:
    """1物件を人が読む1行にする。"""
    units = [u for u in (row.get("tenant") or "").split(" / ") if u]
    vac = sum(1 for u in units if _VACANT_RE.search(u))
    live = len(units) - vac
    who = f"契約者{live}件・空き{vac}件" if units else "契約者の記載なし"
    return (f"{row['name']}（{row.get('status') or '状況不明'}）"
            f" {row.get('address') or ''} / {who}")
