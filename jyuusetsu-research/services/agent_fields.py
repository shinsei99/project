# -*- coding: utf-8 -*-
"""書式の1枚目「宅地建物取引業者・宅地建物取引士」欄を見つけて、自社情報を入れる。

## 書式の作り（全宅連の公式書式・実測）

    宅地建物取引業者      A                         B
    主たる事務所所在地   [M13]                     [AP13]
    TEL                 [M14]                     [AP14]
    商号又は名称         [M15]                     [AP15]
    代表者の氏名         [M16]              ㊞     [AP16]        ㊞
    免許証番号           [M18] （[W18]）第 [AA18] 号
    説明をする宅地建物取引士  氏名 [M19]
    登録番号            （[N20]）第 [W20] 号
    業務に従事する事務所名 [M21]
    事務所所在地         [M22]

**A欄とB欄がある**（共同仲介のときの2社分）。自社は既定で **A欄**に入れる。

宅建業者売主版はブロックの意味が違う。**A＝売主（宅地建物取引業者）／B・C＝媒介業者**。
自社は売主になることも媒介になることもあるので、**両方のブロックを見つけておいて**、
画面で選んだ立場のほうに入れる（`detect_all`）。媒介なのに売主欄へ入れると、
**媒介なのに売主として署名した書面**になってしまう。

**座標は書式ごとに違う**（200本ある）ので持たない。次の2つで機械的に当てる。

1. 見出し行の左端の文字（「商号又は名称」「免許証番号」…）で**何の欄か**を決める
2. B の列より左か右かで **A欄かB欄か**を決める

免許証番号と登録番号だけは1行が複数のセルに割れている（括弧と「第」で区切られる）。
その行の入力欄を**左から順に**当てる。

## 供託所・保証協会は触らない

全宅連の様式は「公益社団法人 全国宅地建物取引業保証協会」「東京法務局…」が
**あらかじめ印刷されている**（実測で確認）。上書きする必要が無いので触らない。
所属地方本部の欄だけは空だが、正式名称を確認できていないので自動では入れない。
"""

import re
from typing import Dict, List, Tuple

from openpyxl.utils import column_index_from_string

_CELL = re.compile(r"([A-Z]{1,3})(\d+)$")

# 見出し → プロファイルのキー（1行に入力欄が1つのもの）
_SIMPLE = {
    "主たる事務所所在地": "所在地",
    "商号又は名称": "商号",
    "代表者の氏名": "代表者",
    "業務に従事する事務所名": "事務所名",
    "事務所所在地": "事務所所在地",
    "業務に従事する事務所名・所在地": "事務所名",
}

# 1行が複数セルに割れているもの（左から順に対応する）
_SPLIT = {
    "免許証番号": ["免許_知事名", "免許_更新回数", "免許_番号"],
    "登録番号": ["宅建士_登録先", "宅建士_登録番号"],
}

# ここまで来たら業者欄は終わり
_STOP = ("取引態様", "供託所等に関する説明", "登記記録に記録された事項")


def _norm(text: str) -> str:
    return re.sub(r"[\s　]", "", str(text or ""))


def _blocks(row_strings: Dict[int, List[Tuple[int, str]]]) -> List[dict]:
    """「A」「B」「C」の見出しから、業者ブロックの範囲を割り出す。

    書式には2つの型がある（実測）。

      (a) 一般売主版 … 1行に「A」「B」＝**媒介業者が2社**。自社は **A**
      (b) 宅建業者売主版 … 先に「A」だけの行があり、その直下が
          「取引態様: 売主（宅地建物取引業者）」。**A は売主**で、
          少し下に「B」「C」＝媒介業者。自社は **B**

    (b) で A に自社を入れると、**媒介なのに売主として署名した書面**になる。
    そこでブロックの頭3行に「売主」があるものは候補から外す。
    """
    marks: List[Tuple[int, int, str]] = []
    for row in sorted(row_strings):
        for col, text in row_strings[row]:
            if _norm(text) in ("A", "B", "C"):
                marks.append((row, col, _norm(text)))

    out: List[dict] = []
    header_rows = sorted({r for r, _c, _t in marks})
    for idx, (row, col, letter) in enumerate(marks):
        same_row = sorted(c for r, c, _t in marks if r == row and c > col)
        col_end = same_row[0] if same_row else 10 ** 6
        later = [r for r in header_rows if r > row]
        row_end = later[0] if later else row + 26
        head_text = "".join(
            t for r in range(row, min(row + 3, row_end + 1))
            for _c, t in (row_strings.get(r) or []))
        out.append({
            "letter": letter, "row": row, "row_end": row_end,
            "col": col, "col_end": col_end,
            "is_seller": "売主" in head_text,
        })
    return out


ROLE_BROKER = "媒介"
ROLE_SELLER = "売主"


def detect_all(row_strings: Dict[int, List[Tuple[int, str]]],
               inputs: List[Tuple[str, str]]) -> Dict[str, Dict[str, str]]:
    """立場ごとに {プロファイルのキー: セル} を返す。

        {"媒介": {...}, "売主": {...}}

    売主ブロックが無い書式（一般売主版＝売主が業者ではない）では「売主」は空になる。
    """
    by_row: Dict[int, List[Tuple[int, str]]] = {}
    for cell, _label in inputs:
        m = _CELL.match(cell)
        if not m:
            continue
        by_row.setdefault(int(m.group(2)), []).append(
            (column_index_from_string(m.group(1)), cell))

    out = {ROLE_BROKER: {}, ROLE_SELLER: {}}
    for block in _blocks(row_strings):
        role = ROLE_SELLER if block["is_seller"] else ROLE_BROKER
        if out[role]:
            continue          # その立場の1社目だけ（共同仲介の2社目は人が入れる）
        found = _scan_block(row_strings, by_row, block)
        # 商号が取れないブロックは業者欄ではない（別の「A」を拾っただけ）
        if "商号" in found:
            out[role] = found
    return out


def detect(row_strings: Dict[int, List[Tuple[int, str]]],
           inputs: List[Tuple[str, str]]) -> Dict[str, str]:
    """媒介業者としての欄（既定の立場）。"""
    return detect_all(row_strings, inputs)[ROLE_BROKER]


def _scan_block(row_strings, by_row, block) -> Dict[str, str]:
    """1つの業者ブロックの中だけを見て、見出しごとにセルを当てる。

    **1行の中で「見出し → その右にある入力欄」を対にする。**
    行の左端だけを見る作りだと、宅建業者売主版の
    「免許証番号 … ｜ 宅地建物取引士 登録番号 …」のように
    **1行に見出しが2つ以上並ぶ型**を取りこぼす（実測で取りこぼしていた）。

    括弧で割れている欄（`（ ）第 号`）は、**その行で直前に出た見出し**
    （免許証番号なのか登録番号なのか）で意味が決まる。
    """
    out: Dict[str, str] = {}
    seen_takken = False          # 宅建士の欄に入ったか（TEL が2回出てくるため）
    for row in range(block["row"], block["row_end"] + 1):
        items = sorted(row_strings.get(row) or [])
        if not items:
            continue
        head = _norm(items[0][1])
        # 「取引態様」はブロックの終わりの目印だが、宅建業者売主版では
        # 売主ブロックの2行目に出てくる。**中身を取り終えてから**打ち切る
        if any(s in head for s in _STOP) and "商号" in out:
            break

        inputs_row = sorted(by_row.get(row) or [])
        context = ""             # 直前に出た「免許証番号」/「登録番号」
        slot = 0                 # その見出しの何番目の入力欄か
        for i, (col, text) in enumerate(items):
            label = _norm(text)
            next_col = items[i + 1][0] if i + 1 < len(items) else 10 ** 6
            cells = [c for cc, c in inputs_row
                     if col < cc < next_col
                     and block["col"] <= cc < block["col_end"]]

            if "宅地建物取引士" in label:
                seen_takken = True
            if label in _SPLIT:
                context, slot = label, 0

            if not cells:
                continue
            cell = cells[0]

            if label in _SIMPLE:
                out.setdefault(_SIMPLE[label], cell)
            elif context and (label in _SPLIT or label in ("（", "）第")):
                # 「免許証番号 [知事名] （[更新]）第 [番号] 号」のように、
                # 見出し本体・（・）第 の順に入力欄が並ぶ。**出てきた順**に当てる。
                # 登録番号は本体の直後に入力欄が無く、括弧の中から始まる
                keys = _SPLIT[context]
                if slot < len(keys):
                    out.setdefault(keys[slot], cell)
                    slot += 1
            elif label == "氏名" or "宅地建物取引士" in label:
                out.setdefault("宅建士_氏名", cell)
            elif label == "TEL":
                out.setdefault("事務所TEL" if seen_takken else "TEL", cell)
    return out


def values(profile: Dict[str, str], cells: Dict[str, str]) -> Dict[str, str]:
    """{セル: 値} を作る。空の項目は書かない（書式の既定を残す）。"""
    out: Dict[str, str] = {}
    for key, cell in (cells or {}).items():
        value = str((profile or {}).get(key, "") or "").strip()
        if value:
            out[cell] = value
    return out
