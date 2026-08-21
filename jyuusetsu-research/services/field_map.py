"""PropertyData の項目 → 公式書式の入力欄を、見出しの文言から解決する規則。

200本の公式書式それぞれにセル座標を手で書くのは現実的でないので、
`official_format_service.scan()` が拾った入力欄の見出しに対して
**包含パターン／除外パターン**を当てて対応付ける。

除外が要る理由（実測でつまずいた点）:
  - 「所在」は物件の所在地だけでなく **宅建業者の「主たる事務所所在地」**や
    保証協会の供託所にも出てくる。除外しないと業者住所を物件所在地に書いてしまう
  - 「種類」は建物の種類のほかに **「権利の種類」**（借地権など）がある
  - 「地積」は物件表示のほかに **「地積の確定」**（実測条項）がある
  - 「建蔽率」は指定建蔽率のほかに **「建蔽率の緩和」**の欄がある

重説に記載欄が無い項目（最寄駅・駅距離・人口・世帯数・路線価・公示地価）は
ここでは扱わない。**あれは調査資料であって重要事項説明書の記載事項ではない**
（2026-08-21 に全宅連の公式書式を実測して確認）。画面に出すだけにする。
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

# (PropertyData のキー, 見出しに含まれる語, 除外語, 備考)
RULES = [
    ("所在地",   r"所在",                 r"事務所|主たる|供託|保証協会|地方本部|免許"),
    ("地番",     r"地番",                 r"家屋番号"),
    ("地目",     r"地目",                 None),
    ("地積",     r"地積",                 r"確定|実測|公簿|差異|清算"),
    ("家屋番号", r"家屋番号",             None),
    ("種類",     r"種類",                 r"権利の種類|工事|高度地区|免許|保証"),
    ("構造",     r"構造",                 r"形状|工事完了"),
    ("床面積",   r"床面積",               None),
    ("所有者",   r"登記名義人|名義人",     None),
    ("抵当権",   r"抵当権",               None),
    ("用途地域", r"用途地域",             r"特別用途|特定用途|準用途"),
    ("建ぺい率", r"指定建蔽率|指定建ぺい率", r"緩和"),
    ("容積率",   r"指定容積率",           r"特例|緩和|道路幅員"),
    ("高度地区", r"高度地区",             r"高度利用"),
    ("土砂災害", r"土砂災害警戒区域",     r"特別警戒"),
    ("津波",     r"津波災害警戒区域",     None),
    ("洪水浸水想定", r"水害ハザードマップ", None),
]

_SPACE = re.compile(r"[\s　]")


def normalize(text: str) -> str:
    """見出しの比較用。全角スペースや改行が入っている（例: 「地　　　番」）。"""
    return _SPACE.sub("", text or "")


def resolve(inputs: List[dict]) -> Dict[str, str]:
    """scan() の inputs から {PropertyData キー: セル} を作る。

    同じ見出しが複数当たる場合（土地が複数筆ある物件表示など）は
    **一番上の行のものを採る**。書式の1件目が主たる物件になっているため。
    """
    out: Dict[str, str] = {}
    for field, inc, exc in [(r[0], r[1], r[2]) for r in RULES]:
        inc_re = re.compile(inc)
        exc_re = re.compile(exc) if exc else None
        best: Optional[dict] = None
        for item in inputs:
            label = normalize(item.get("label"))
            if not inc_re.search(label):
                continue
            if exc_re and exc_re.search(label):
                continue
            if best is None:
                best = item
        if best is not None:
            out[field] = best["cell"]
    return out


def coverage(mapping: Dict[str, str]) -> str:
    """対応が取れた項目／取れなかった項目を1行で返す（点検用）。"""
    got = [r[0] for r in RULES if r[0] in mapping]
    miss = [r[0] for r in RULES if r[0] not in mapping]
    return "対応 {}/{}  未対応: {}".format(len(got), len(RULES), "・".join(miss) or "なし")
