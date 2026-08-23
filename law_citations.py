#!/usr/bin/env python3
"""生成した文章に出てくる**法令の引用が実在するか**を e-Gov で確かめる（2026-08-23 作成）。

`egov_law_api.py`（キー不要・無料）の上に乗る薄い層で、直下に1本だけ置く。
アプリ側からは次で読む:

    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import law_citations

## なぜ要るか

特約条項・覚書・重説の下書きは AI が書く。プロンプトは「法令名・条番号があれば正確に
引用する」と指示しているが、**AIの記憶に頼った引用は条番号がずれることがある**
（改正で条が繰り下がる／似た条と取り違える）。契約書に載る文章なので、
出来上がった文章から引用を拾い、**現行条文を突き合わせて人に見せる**。

判定は3つだけ:
  ✅ 実在  … その法令にその条がある（原文の冒頭と施行日を返す）
  ⚠️ 無い  … 法令は見つかったが、その条番号が無い（＝引用が怪しい）
  ❔ 不明  … 法令名が e-Gov で引けなかった（通称・略称・条例など）

**直すのは人。** この層は「合っているか」を示すだけで、文章は書き換えない。

## 拾える書き方（2026-08-23 実測）

  宅地建物取引業法第35条 / 宅建業法35条 / 民法第562条第1項 / 借地借家法第28条 /
  建築基準法第42条第2項 / 宅地建物取引業法第34条の2

「第○項」は条の中の話なので条番号だけを見る。漢数字（第三十五条）も算用数字に直す。
"""

from __future__ import annotations

import pathlib
import re
import sys
from typing import Any, Dict, List

_ROOT = pathlib.Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# 通称 → 正式名称（e-Gov は正式名称でないと引けないものがある）
ALIASES = {
    "宅建業法": "宅地建物取引業法",
    "区分所有法": "建物の区分所有等に関する法律",
    "品確法": "住宅の品質確保の促進等に関する法律",
    "消契法": "消費者契約法",
    "都計法": "都市計画法",
    "農地法": "農地法",
    "借地借家法": "借地借家法",
}

# 法令名らしい語 ＋ 第○条（の○）。「法」「令」「条例」で終わる語を拾う
_CITATION = re.compile(
    # ★ {1,30} にしてある。{2,30} だと「民法第562条」のように**2文字の法令名を取り落とす**
    #   （「民」が1文字で足りない。2026-08-23 実測）
    r"(?P<law>[一-龥ぁ-んァ-ヶA-Za-z0-9・ー]{1,30}?(?:法|法律|令|規則))"
    r"\s*(?:第)?\s*(?P<num>[0-9０-９一二三四五六七八九十百]+)"
    r"\s*条(?:\s*の\s*(?P<branch>[0-9０-９一二三四五六七八九十]+))?"
)

_KANJI = {"〇": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
          "六": 6, "七": 7, "八": 8, "九": 9}


def _to_arabic(text: str) -> str:
    """算用数字はそのまま、漢数字は数に直す（「三十五」→「35」・百まで）。"""
    text = str(text).translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    if text.isdigit():
        return text
    total, current = 0, 0
    for ch in text:
        if ch in _KANJI:
            current = _KANJI[ch]
        elif ch == "十":
            total += (current or 1) * 10
            current = 0
        elif ch == "百":
            total += (current or 1) * 100
            current = 0
    total += current
    return str(total) if total else text


def extract_citations(text: str) -> List[Dict[str, str]]:
    """文章から法令の引用を拾う（重複は1つにまとめる）。"""
    found: Dict[tuple, Dict[str, str]] = {}
    for m in _CITATION.finditer(str(text or "")):
        law = ALIASES.get(m.group("law"), m.group("law"))
        number = _to_arabic(m.group("num"))
        if m.group("branch"):
            number = "{}_{}".format(number, _to_arabic(m.group("branch")))
        key = (law, number)
        if key not in found:
            found[key] = {"law": law, "number": number, "raw": m.group(0).strip()}
    return list(found.values())


# 法令名の前にくっつきやすい助詞・区切り（この直後から法令名が始まると見て候補にする）
_BOUNDARY = "はがをにでとやもの、。・「」（）【】及びおよび並又または"


def _name_candidates(title: str) -> List[str]:
    """「重要事項の説明は宅地建物取引業法」から、法令名になりうる**後ろ側**の候補を作る。

    長いものから試し、**e-Gov の名前と完全一致した最初のもの**を採る。
    候補は (1) そのまま (2) 助詞・区切りの直後から (3) 末尾から2〜12文字
    の3通りを混ぜる。日本語は語の区切りが無いので、この3通りで実用上は足りる
    （2026-08-23 に実文で確認）。
    """
    title = str(title or "")
    seen, out = set(), []

    def add(candidate: str):
        candidate = candidate.strip()
        if len(candidate) >= 2 and candidate not in seen:
            seen.add(candidate)
            out.append(candidate)

    add(title)
    for i, ch in enumerate(title):
        if ch in _BOUNDARY:
            add(title[i + 1:])
    for length in range(min(12, len(title)), 1, -1):
        add(title[-length:])
    # 長い順（＝もっとも情報が多い候補）から試す
    return sorted(out, key=len, reverse=True)


def _law_id(egov, title: str, cache: Dict[str, Any]) -> Dict[str, str]:
    """法令名 → {law_id, law_title, enforced}。引けなければ空 dict。

    日本語には語の区切りが無いので、正規表現は「本件は宅地建物取引業法」のように
    **前の語をくっつけて拾ってしまう**（2026-08-23 実測）。頭を1文字ずつ削りながら
    e-Gov に当て、**名前が完全一致したものを採る**。結果は cache に持つので
    同じ文章の中で何度も問い合わせない。
    """
    if title in cache:
        return cache[title]

    result: Dict[str, str] = {}
    for candidate in _name_candidates(title):
        # 通称は正式名称に置き換えてから引く（「区分所有法」など）
        candidate = ALIASES.get(candidate, candidate)
        if candidate in cache:
            if cache[candidate]:
                result = cache[candidate]
                break
            continue
        try:
            hits = egov.search(candidate, limit=5)
        except Exception:
            hits = []
        # 完全一致だけを信じる（「民法」で「民法施行法」を掴まないため）
        best = next((h for h in hits if h.get("law_title") == candidate), None)
        cache[candidate] = {} if not best else {
            "law_id": best.get("law_id", ""),
            "law_title": best.get("law_title", ""),
            "enforced": best.get("amendment_enforcement_date", ""),
        }
        if cache[candidate]:
            result = cache[candidate]
            break
    cache[title] = result
    return result


def _article_label(law_title: str, number: str) -> str:
    """「34_2」→「第34条の2」のように、人が読む形の条番号にする。"""
    if "_" in str(number):
        head, branch = str(number).split("_", 1)
        return "{}第{}条の{}".format(law_title, head, branch)
    return "{}第{}条".format(law_title, number)


def verify_citations(text: str, snippet: int = 60) -> List[Dict[str, str]]:
    """文章中の引用を1件ずつ確かめる。

    各要素: {"raw", "law", "number", "status"(実在/無い/不明), "caption",
             "snippet"(原文の冒頭), "enforced"(施行日), "message"}
    """
    import egov_law_api

    out, cache = [], {}
    for cite in extract_citations(text):
        info = _law_id(egov_law_api, cite["law"], cache)
        if not info:
            out.append({**cite, "status": "不明", "caption": "", "snippet": "",
                        "enforced": "",
                        "message": "e-Gov で「{}」を引けませんでした（通称・条例の可能性）".format(cite["law"])})
            continue
        try:
            art = egov_law_api.article(info["law_id"], cite["number"])
        except Exception as e:
            out.append({**cite, "status": "不明", "caption": "", "snippet": "",
                        "enforced": info.get("enforced", ""),
                        "message": "条文の取得に失敗しました: {}".format(e)})
            continue
        if not art:
            out.append({**cite, "status": "無い", "caption": "", "snippet": "",
                        "enforced": info.get("enforced", ""),
                        "message": "{} は見つかりません（引用を確かめてください）".format(
                            _article_label(info["law_title"], cite["number"]))})
            continue
        body = re.sub(r"\s+", " ", art.get("text", "")).strip()
        cite = {**cite, "law": info["law_title"]}
        out.append({**cite, "status": "実在", "caption": art.get("caption", ""),
                    "snippet": body[:snippet] + ("…" if len(body) > snippet else ""),
                    "enforced": info.get("enforced", ""),
                    "message": "{} {}".format(
                        _article_label(info["law_title"], cite["number"]),
                        art.get("caption", ""))})
    return out


def summarize(results: List[Dict[str, str]]) -> Dict[str, int]:
    counts = {"実在": 0, "無い": 0, "不明": 0}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return counts


if __name__ == "__main__":  # python3 law_citations.py "…文章…"
    sample = sys.argv[1] if len(sys.argv) > 1 else (
        "本件は宅地建物取引業法第35条および民法第562条第1項に基づき、"
        "借地借家法第28条、建築基準法第42条第2項、宅建業法第9999条を引用する。")
    for r in verify_citations(sample):
        mark = {"実在": "✅", "無い": "⚠️", "不明": "❔"}[r["status"]]
        print("{} {:<24} {}".format(mark, r["raw"], r["message"]))
